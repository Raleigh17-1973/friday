from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Iterator
from uuid import uuid4

_log = logging.getLogger(__name__)

from packages.agents.registry import AgentRegistry
from packages.common.models import (
    ActionMode,
    ApprovalRequest,
    ChatRequest,
    MemoryCandidate,
    RiskLevel,
    RunTrace,
)
from packages.common.schemas import (
    CRITIC_REPORT_SCHEMA,
    FINAL_ANSWER_PACKAGE_SCHEMA,
    MEMORY_CANDIDATE_SCHEMA,
    PLANNER_OUTPUT_SCHEMA,
    SPECIALIST_MEMO_SCHEMA,
)
from packages.common.validation import validate_required_fields
from packages.governance.approvals import ApprovalService
from packages.governance.audit import AuditLog
from packages.governance.policy import PolicyEngine
from packages.memory.service import LayeredMemoryService
from packages.tools.policy_wrapped_tools import ToolExecutor
from packages.observability.logger import finalize_run as _obs_finalize
from workers.orchestrator.critic import run_critic
from workers.orchestrator.planner import build_plan
from workers.orchestrator.synthesizer import synthesize, synthesize_stream

if TYPE_CHECKING:
    from packages.llm.base import LLMProvider


class FridayManager:
    def __init__(
        self,
        *,
        registry: AgentRegistry,
        memory: LayeredMemoryService,
        policy: PolicyEngine,
        approvals: ApprovalService,
        audit: AuditLog,
        tool_executor: ToolExecutor | None = None,
        llm: "LLMProvider | None" = None,
    ) -> None:
        self._registry = registry
        self._memory = memory
        self._policy = policy
        self._approvals = approvals
        self._audit = audit
        self._tool_executor = tool_executor or ToolExecutor(Path.cwd())
        self._llm = llm

    def run(self, request: ChatRequest) -> dict:
        run_id = f"run_{uuid4().hex[:12]}"

        memory_bundle = self._memory.load(
            org_id=request.org_id,
            conversation_id=request.conversation_id,
            working={"user_message": request.message, "context_packet": request.context_packet},
        )
        planning_message = self._resolve_planning_message(request.message, memory_bundle.conversation)
        planning_message = self._inject_recalled_context(
            planning_message, request.org_id, request.message
        )
        plan = build_plan(planning_message, llm=self._llm)
        validate_required_fields(plan, PLANNER_OUTPUT_SCHEMA, "PlannerOutput")

        specialists = []
        for specialist_id in plan.recommended_specialists:
            s = self._registry.build_specialist(specialist_id)
            s.llm = self._llm
            specialists.append(s)

        tool_calls = self._run_context_tools(
            tool_names=plan.required_tools,
            query=request.message,
            specialists=plan.recommended_specialists,
            risk_level=plan.risk_level,
        )

        # Phase 2a: parallel specialist dispatch
        memos = self._run_specialists_parallel(specialists, plan, request.message)
        for memo in memos:
            validate_required_fields(memo, SPECIALIST_MEMO_SCHEMA, "SpecialistMemo")

        critic_report = run_critic(memos, llm=self._llm)
        validate_required_fields(critic_report, CRITIC_REPORT_SCHEMA, "CriticReport")

        final_answer = synthesize(plan, memos, critic_report, llm=self._llm)
        validate_required_fields(final_answer, FINAL_ANSWER_PACKAGE_SCHEMA, "FinalAnswerPackage")

        # Phase 2b: iterative refinement — if confidence is low and LLM is available,
        # run a second synthesis pass with the critic's objections injected more forcefully
        if (
            self._llm is not None
            and final_answer.confidence < 0.65
            and plan.output_format in ("full_deliverable", "business_case_draft")
        ):
            _log.info(
                "Confidence %.2f below threshold — running refinement pass for run %s",
                final_answer.confidence,
                run_id,
            )
            refined = synthesize(plan, memos, critic_report, llm=self._llm, refinement_pass=True)
            if refined.confidence >= final_answer.confidence:
                final_answer = refined
                validate_required_fields(final_answer, FINAL_ANSWER_PACKAGE_SCHEMA, "FinalAnswerPackage")

        requested_scopes = list(request.context_packet.get("requested_write_scopes", []))
        action_mode = ActionMode.WRITE if requested_scopes else ActionMode.READ_ONLY
        policy = self._policy.evaluate(
            action_mode=action_mode,
            requested_scopes=requested_scopes,
            risk_level=plan.risk_level,
        )

        approval = None
        if policy.requires_approval:
            approval = self._approvals.create(
                ApprovalRequest(
                    approval_id=f"appr_{uuid4().hex[:10]}",
                    run_id=run_id,
                    reason=policy.reason,
                    action_summary="Requested write-capable tool action.",
                    requested_scopes=requested_scopes,
                )
            )

        trace = RunTrace(
            run_id=run_id,
            org_id=request.org_id,
            user_id=request.user_id,
            conversation_id=request.conversation_id,
            planner=plan,
            selected_agents=[s.specialist_id for s in specialists],
            tool_calls=tool_calls,
            specialist_memos=memos,
            critic_report=critic_report,
            final_answer=final_answer,
            confidence=final_answer.confidence or 0.0,
            feedback={},
            outcome={"approval_required": bool(approval)},
        )
        self._audit.record_run(trace)

        self._memory.append_conversation(
            request.conversation_id,
            {
                "run_id": run_id,
                "user": request.message,
                "final_answer": asdict(final_answer),
                "selected_agents": trace.selected_agents,
            },
        )
        self._memory.add_episode(
            request.org_id,
            {
                "run_id": run_id,
                "problem": plan.problem_statement,
                "experts": trace.selected_agents,
                "outcome": trace.outcome,
            },
            run_id=run_id,
        )

        candidates = self._build_memory_candidates(run_id, request, trace)
        for candidate in candidates:
            self._memory.add_candidate(asdict(candidate), request.org_id)

        run_cost = _obs_finalize(run_id)
        return {
            "run_id": run_id,
            "final_answer": asdict(final_answer),
            "planner": asdict(plan),
            "tool_calls": tool_calls,
            "specialist_memos": [asdict(memo) for memo in memos],
            "critic_report": asdict(critic_report),
            "approval": asdict(approval) if approval else None,
            "memory_candidates": [asdict(candidate) for candidate in candidates],
            "memory_context": {
                "conversation_events": len(memory_bundle.conversation),
                "episodic_items": len(memory_bundle.episodic),
            },
            "observability": run_cost,
        }

    def run_streaming(self, request: "ChatRequest") -> Iterator[dict]:
        """Run the full pipeline and yield SSE-ready event dicts.

        Events:
          {"event": "status",  "label": str}           — pipeline progress
          {"event": "token",   "text": str}             — synthesis token
          {"event": "done",    "run_id": str, ...}      — structured metadata
          {"event": "error",   "message": str}          — on failure
        """
        from packages.common.models import ChatRequest  # local to avoid circular

        run_id = f"run_{uuid4().hex[:12]}"
        try:
            yield {"event": "status", "label": "Loading context"}
            memory_bundle = self._memory.load(
                org_id=request.org_id,
                conversation_id=request.conversation_id,
                working={"user_message": request.message, "context_packet": request.context_packet},
            )
            planning_message = self._resolve_planning_message(request.message, memory_bundle.conversation)
            planning_message = self._inject_recalled_context(
                planning_message, request.org_id, request.message
            )

            yield {"event": "status", "label": "Planning your request"}
            plan = build_plan(planning_message, llm=self._llm)

            specialists = []
            for specialist_id in plan.recommended_specialists:
                s = self._registry.build_specialist(specialist_id)
                s.llm = self._llm
                specialists.append(s)

            n = len(specialists)
            label = f"Consulting {n} specialist{'s' if n != 1 else ''}" if n else "Analyzing"
            yield {"event": "status", "label": label}
            memos = self._run_specialists_parallel(specialists, plan, request.message)

            yield {"event": "status", "label": "Quality review"}
            critic_report = run_critic(memos, llm=self._llm)

            yield {"event": "status", "label": "Synthesizing response"}
            full_text_parts: list[str] = []
            for token in synthesize_stream(plan, memos, critic_report, llm=self._llm):
                full_text_parts.append(token)
                yield {"event": "token", "text": token}

            full_text = "".join(full_text_parts)

            # Build a lightweight FinalAnswerPackage from streamed text for audit/memory
            from packages.common.models import FinalAnswerPackage
            experts = [m.specialist_id for m in memos]
            final_answer = FinalAnswerPackage(
                direct_answer=full_text,
                executive_summary="",
                key_assumptions=[],
                major_risks=[],
                recommended_next_steps=[],
                what_i_would_do_first=None,
                experts_consulted=experts,
                confidence=0.85 if self._llm else 0.55,
            )

            self._memory.append_conversation(
                request.conversation_id,
                {"run_id": run_id, "user": request.message, "final_answer": asdict(final_answer), "selected_agents": experts},
            )
            self._memory.add_episode(
                request.org_id,
                {"run_id": run_id, "problem": plan.problem_statement, "experts": experts, "outcome": {}},
                run_id=run_id,
            )

            yield {
                "event": "done",
                "run_id": run_id,
                "selected_agents": experts,
                "output_format": plan.output_format,
                "domains": plan.domains_involved,
                "llm_active": self._llm is not None,
            }
        except Exception as exc:
            _log.exception("Streaming run %s failed: %s", run_id, exc)
            yield {"event": "error", "message": str(exc)}

    def _run_specialists_parallel(self, specialists, plan, user_message: str) -> list:
        """Run all specialists concurrently. Falls back to sequential on error."""
        if not specialists:
            return []
        if len(specialists) == 1:
            return [specialists[0].run(plan=plan, user_message=user_message)]
        memos = [None] * len(specialists)
        try:
            with ThreadPoolExecutor(max_workers=len(specialists)) as pool:
                future_to_idx = {
                    pool.submit(s.run, plan=plan, user_message=user_message): i
                    for i, s in enumerate(specialists)
                }
                for future in as_completed(future_to_idx):
                    idx = future_to_idx[future]
                    try:
                        memos[idx] = future.result()
                    except Exception as exc:
                        _log.warning("Specialist %s failed: %s — using stub", specialists[idx].specialist_id, exc)
                        memos[idx] = specialists[idx]._run_stub(plan, user_message)
        except Exception as exc:
            _log.warning("Parallel dispatch failed (%s) — falling back to sequential", exc)
            return [s.run(plan=plan, user_message=user_message) for s in specialists]
        return [m for m in memos if m is not None]

    def _inject_recalled_context(
        self, planning_message: str, org_id: str, query: str
    ) -> str:
        """Prepend relevant memories recalled via semantic search to the planning message.

        Only injects context when there are high-confidence vector hits (similarity > 0.6)
        or keyword matches. Silently skips on any error — recall is best-effort.
        """
        try:
            recalled = self._memory.semantic_recall(org_id=org_id, query=query, top_k=3)
            if not recalled:
                return planning_message

            # Filter to meaningful results: drop near-zero keyword-fallback hits
            useful = [r for r in recalled if r.get("similarity", 1.0) == 0.0 or r.get("similarity", 0) > 0.55]
            if not useful:
                return planning_message

            snippets = "\n".join(f"- {r['content_text'][:300]}" for r in useful)
            context_block = f"\n\n---\nRelevant context recalled from prior sessions:\n{snippets}\n---"
            _log.debug("Injecting %d recalled memories into planning message", len(useful))
            return planning_message + context_block
        except Exception as exc:
            _log.debug("semantic_recall injection failed (non-fatal): %s", exc)
            return planning_message

    def _resolve_planning_message(self, latest_message: str, conversation_history: list[dict]) -> str:
        text = latest_message.strip()
        lowered = text.lower()
        if not text:
            return text

        domain_tokens = [
            "business case",
            "template",
            "project charter",
            "finance",
            "sales",
            "operations",
            "roi",
            "pricing",
            "pipeline",
            "research",
            "risk",
            "kpi",
        ]
        if any(token in lowered for token in domain_tokens):
            return text

        follow_up_markers = [
            "create it",
            "do it",
            "help me",
            "continue",
            "expand",
            "shorter",
            "rewrite",
            "use this",
            "that",
            "this",
        ]
        short_or_follow_up = len(text.split()) <= 9 or any(marker in lowered for marker in follow_up_markers)
        if not short_or_follow_up:
            return text

        prior_user = next(
            (str(event.get("user")) for event in reversed(conversation_history) if isinstance(event, dict) and event.get("user")),
            "",
        ).strip()
        if not prior_user:
            return text

        return f"{prior_user}\nFollow-up request: {text}"

    def _run_context_tools(
        self,
        *,
        tool_names: list[str],
        query: str,
        specialists: list[str],
        risk_level: RiskLevel,
    ) -> list[dict]:
        calls: list[dict] = []
        if not specialists:
            return calls

        # Manager executes context retrieval tools using policy derived from chosen specialists.
        allowed_tools = sorted(
            {tool for specialist in specialists for tool in self._registry.allowed_tools_for(specialist)}
        )
        for tool_name in tool_names:
            tool_decision = self._policy.evaluate_tool_access(
                agent_id="friday_manager",
                tool_name=tool_name,
                mode=ActionMode.READ_ONLY,
                allowed_tools=allowed_tools,
                risk_level=risk_level,
            )
            if not tool_decision.allowed:
                calls.append(
                    {
                        "tool": tool_name,
                        "mode": "read_only",
                        "ok": False,
                        "error": tool_decision.reason,
                    }
                )
                continue

            result = self._tool_executor.run(tool_name, {"query": query})
            calls.append(
                {
                    "tool": tool_name,
                    "mode": "read_only",
                    "ok": result.ok,
                    "output": result.output,
                    "error": result.error,
                }
            )

        return calls

    def _build_memory_candidates(self, run_id: str, request: ChatRequest, trace: RunTrace) -> list[MemoryCandidate]:
        candidates: list[MemoryCandidate] = [
            MemoryCandidate(
                candidate_id=f"mem_{uuid4().hex[:10]}",
                run_id=run_id,
                candidate_type="episodic_note",
                content={
                    "problem": request.message,
                    "experts": trace.selected_agents,
                    "confidence": trace.confidence,
                },
                risk_level=RiskLevel.LOW,
                auto_accepted=True,
            )
        ]

        if request.context_packet.get("communication_preference"):
            candidates.append(
                MemoryCandidate(
                    candidate_id=f"mem_{uuid4().hex[:10]}",
                    run_id=run_id,
                    candidate_type="user_preference",
                    content={"communication_preference": request.context_packet["communication_preference"]},
                    risk_level=RiskLevel.LOW,
                    auto_accepted=True,
                )
            )

        if "new agent" in request.message.lower():
            candidates.append(
                MemoryCandidate(
                    candidate_id=f"mem_{uuid4().hex[:10]}",
                    run_id=run_id,
                    candidate_type="prompt_improvement_proposal",
                    content={"proposal": "Route repeated unmet requests to agent_architect proposal workflow."},
                    risk_level=RiskLevel.MEDIUM,
                    auto_accepted=False,
                )
            )

        for candidate in candidates:
            validate_required_fields(candidate, MEMORY_CANDIDATE_SCHEMA, "MemoryCandidate")

        return candidates

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


# ---------------------------------------------------------------------------
# Provenance / consultation-history classifier
# ---------------------------------------------------------------------------

_PROVENANCE_PATTERNS = [
    "did you consult", "which agents", "who did you consult",
    "did you ask", "why didn't you", "why did you not",
    "did you use the", "did you research", "did you check with",
    "who was consulted", "what agents", "which specialists",
    "did legal", "did finance", "did hr", "did security",
    "was legal consulted", "was finance consulted",
    "did you involve", "did you loop in", "which experts",
    "what specialists", "did you use any agents", "what did you consult",
    "who did you use", "did you ask legal", "did you ask finance",
]

# Domain keywords used to detect when an agent *should* have been consulted
_DOMAIN_AGENT_MAP = {
    "legal": "legal_compliance",
    "compliance": "legal_compliance",
    "finance": "finance",
    "financial": "finance",
    "hr": "people_hr",
    "people": "people_hr",
    "security": "security_risk",
    "risk": "security_risk",
    "marketing": "marketing_brand",
    "sales": "sales_revenue",
    "operations": "operations",
    "strategy": "chief_of_staff_strategist",
    "product": "product",
    "research": "research",
    "data": "data_analytics",
    "analytics": "data_analytics",
    "pr": "public_relations",
    "public relations": "public_relations",
    "m&a": "mergers_acquisitions",
    "acquisition": "mergers_acquisitions",
    "internal comms": "internal_comms",
    "communications": "internal_comms",
    "ai strategy": "ai_strategy",
    "automation": "ai_strategy",
    "okr": "okr_coach",
}

_AGENT_DISPLAY_NAMES = {
    "legal_compliance": "Legal / Compliance",
    "finance": "Finance",
    "people_hr": "People / HR",
    "security_risk": "Security / Risk",
    "marketing_brand": "Marketing / Brand",
    "sales_revenue": "Sales / Revenue",
    "operations": "Operations",
    "chief_of_staff_strategist": "Chief of Staff / Strategist",
    "product": "Product",
    "research": "Research",
    "data_analytics": "Data / Analytics",
    "public_relations": "Public Relations",
    "mergers_acquisitions": "M&A",
    "internal_comms": "Internal Comms",
    "ai_strategy": "AI Strategy",
    "okr_coach": "OKR Coach",
    "project_manager": "Project Manager",
    "process_mapper": "Process Mapper",
    "document_specialist": "Document Specialist",
    "writer_scribe": "Writer / Scribe",
    "critic_red_team": "Critic / Red Team",
    "agent_architect": "Agent Architect",
    "customer_success_support": "Customer Success / Support",
}


def _is_provenance_question(message: str) -> bool:
    """Return True if the message is asking about prior consultation/agent usage."""
    lower = message.lower().strip()
    return any(pattern in lower for pattern in _PROVENANCE_PATTERNS)


def _build_provenance_answer(message: str, trace: "RunTrace") -> str:
    """Build a direct, factual answer about which agents were consulted."""
    consulted_ids = trace.selected_agents or []
    consulted_names = [_AGENT_DISPLAY_NAMES.get(a, a) for a in consulted_ids]

    # Detect if the user is asking about a specific domain
    msg_lower = message.lower()
    asked_about: list[str] = []
    for keyword, agent_id in _DOMAIN_AGENT_MAP.items():
        if keyword in msg_lower and agent_id not in consulted_ids:
            display = _AGENT_DISPLAY_NAMES.get(agent_id, agent_id)
            if display not in asked_about:
                asked_about.append(display)

    if consulted_names:
        consulted_str = ", ".join(consulted_names)
        answer = f"For that response, I consulted: **{consulted_str}**."
    else:
        answer = "That response was handled directly without specialist consultation."

    if asked_about:
        missed = ", ".join(asked_about)
        answer += (
            f"\n\nI did **not** consult {missed} — that was an oversight for this type of question. "
            f"I can revisit the response with {missed}'s perspective if you'd like."
        )
    elif consulted_names:
        answer += " All relevant specialists for that request were included."

    return answer


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
        # -----------------------------------------------------------------------
        # Provenance short-circuit: answer consultation-history questions
        # directly from RunTrace metadata without running the full pipeline.
        # -----------------------------------------------------------------------
        if _is_provenance_question(request.message):
            recent_trace = self._audit.get_latest_run_for_conversation(request.conversation_id)
            if recent_trace is not None:
                answer = _build_provenance_answer(request.message, recent_trace)
                from packages.common.models import FinalAnswerPackage
                provenance_answer = FinalAnswerPackage(
                    direct_answer=answer,
                    executive_summary="Consultation history retrieved from run metadata.",
                    key_assumptions=[],
                    major_risks=[],
                    recommended_next_steps=[],
                    what_i_would_do_first=None,
                    experts_consulted=recent_trace.selected_agents,
                    confidence=1.0,
                )
                self._memory.append_conversation(
                    request.conversation_id,
                    {
                        "run_id": run_id,
                        "user": request.message,
                        "final_answer": asdict(provenance_answer),
                        "selected_agents": [],
                    },
                )
                return {
                    "run_id": run_id,
                    "final_answer": asdict(provenance_answer),
                    "planner": {
                        "problem_statement": request.message,
                        "output_format": "executive_brief",
                        "domains_involved": [],
                        "recommended_specialists": [],
                        "required_tools": [],
                        "risk_level": "low",
                        "missing_information": [],
                    },
                    "tool_calls": [],
                    "specialist_memos": [],
                    "critic_report": {
                        "blind_spots": [],
                        "challenged_assumptions": [],
                        "alternative_path": "",
                        "residual_risks": [],
                        "confidence": 1.0,
                    },
                    "approval": None,
                    "memory_candidates": [],
                    "memory_context": {
                        "conversation_events": len(memory_bundle.conversation),
                        "episodic_items": len(memory_bundle.episodic),
                    },
                    "observability": {},
                    "response": answer,
                }

        planning_message = self._resolve_planning_message(request.message, memory_bundle.conversation)
        planning_message = self._inject_recalled_context(
            planning_message, request.org_id, request.message,
            episodic=memory_bundle.episodic,
            workspace_id=getattr(request, "workspace_id", None),
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

        # Phase 2b-write: execute tool_requests declared by specialists
        write_actions: list[dict] = []
        for memo in memos:
            for req in getattr(memo, "tool_requests", []):
                tool_name = req.get("tool", "")
                req_args = req.get("args", {})
                if not tool_name:
                    continue
                try:
                    result = self._tool_executor.run(tool_name, req_args)
                    write_actions.append({
                        "tool": tool_name,
                        "args": req_args,
                        "specialist": memo.specialist_id,
                        "ok": result.ok,
                        "output": result.output,
                        "error": result.error,
                    })
                    if result.ok:
                        _log.info("Write action %s succeeded: %s", tool_name, result.output)
                    else:
                        _log.warning("Write action %s failed: %s", tool_name, result.error)
                except Exception as exc:
                    _log.warning("Write action %s raised: %s", tool_name, exc)
                    write_actions.append({
                        "tool": tool_name,
                        "args": req_args,
                        "specialist": memo.specialist_id,
                        "ok": False,
                        "output": {},
                        "error": str(exc),
                    })

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
            "write_actions": write_actions,
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
                planning_message, request.org_id, request.message,
                episodic=memory_bundle.episodic,
                workspace_id=getattr(request, "workspace_id", None),
            )

            # Provenance short-circuit for streaming path
            if _is_provenance_question(request.message):
                recent_trace = self._audit.get_latest_run_for_conversation(request.conversation_id)
                if recent_trace is not None:
                    answer = _build_provenance_answer(request.message, recent_trace)
                    yield {"event": "token", "text": answer}
                    yield {
                        "event": "done",
                        "run_id": run_id,
                        "selected_agents": [],
                        "output_format": "executive_brief",
                        "domains": [],
                        "llm_active": self._llm is not None,
                    }
                    return

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

            # Execute tool_requests from specialist memos (streaming path)
            stream_write_actions: list[dict] = []
            for memo in memos:
                for req in getattr(memo, "tool_requests", []):
                    tool_name = req.get("tool", "")
                    req_args = req.get("args", {})
                    if not tool_name:
                        continue
                    try:
                        result = self._tool_executor.run(tool_name, req_args)
                        stream_write_actions.append({
                            "tool": tool_name,
                            "args": req_args,
                            "specialist": memo.specialist_id,
                            "ok": result.ok,
                            "output": result.output,
                            "error": result.error,
                        })
                    except Exception as exc:
                        _log.warning("Streaming write action %s raised: %s", tool_name, exc)
                        stream_write_actions.append({
                            "tool": tool_name,
                            "args": req_args,
                            "specialist": memo.specialist_id,
                            "ok": False,
                            "output": {},
                            "error": str(exc),
                        })

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
                "write_actions": stream_write_actions,
            }
        except Exception as exc:
            _log.exception("Streaming run %s failed: %s", run_id, exc)
            yield {"event": "error", "message": str(exc)}

    def _run_specialists_parallel(self, specialists, plan, user_message: str) -> list:
        """Run all specialists concurrently. Falls back to sequential on error.

        When ``plan.risk_level`` is HIGH, runs in tree-of-thought mode — each
        specialist generates optimistic / base / pessimistic scenarios, and the
        synthesizer selects the best-supported path.
        """
        if not specialists:
            return []
        tot_mode = plan.risk_level == RiskLevel.HIGH
        if tot_mode:
            _log.info("HIGH risk request — running %d specialists in tree-of-thought mode", len(specialists))
        if len(specialists) == 1:
            return [specialists[0].run(plan=plan, user_message=user_message, tot_mode=tot_mode)]
        memos = [None] * len(specialists)
        try:
            with ThreadPoolExecutor(max_workers=len(specialists)) as pool:
                future_to_idx = {
                    pool.submit(s.run, plan=plan, user_message=user_message, tot_mode=tot_mode): i
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
            return [s.run(plan=plan, user_message=user_message, tot_mode=tot_mode) for s in specialists]
        return [m for m in memos if m is not None]

    def record_feedback(self, run_id: str, approved: bool, notes: str = "") -> None:
        """Record user approval / rejection of a run output.

        Stores a feedback episode that the planner can use to bias future runs
        toward specialist combinations that have been approved for similar requests.
        """
        trace = self._audit.get_run(run_id)
        if trace is None:
            raise KeyError(f"run {run_id!r} not found")
        self._memory.add_episode(
            trace.org_id,
            {
                "type": "feedback",
                "run_id": run_id,
                "approved": approved,
                "notes": notes,
                "query_type": trace.planner.output_format,
                "domains": trace.planner.domains_involved,
                "specialists": trace.selected_agents,
                "confidence": trace.confidence,
                "problem_snippet": trace.planner.problem_statement[:200],
            },
            run_id=f"feedback_{run_id}",
        )
        _log.info(
            "Feedback recorded for run %s: approved=%s specialists=%s",
            run_id, approved, trace.selected_agents,
        )

    def _get_approved_hints(self, episodic: list[dict]) -> list[str]:
        """Extract approved-pattern hints from episodic memory to bias the planner."""
        hints: list[str] = []
        for item in episodic:
            if not (isinstance(item, dict) and item.get("type") == "feedback" and item.get("approved")):
                continue
            specialists = ", ".join(item.get("specialists") or [])
            qtype = item.get("query_type") or "request"
            snippet = item.get("problem_snippet") or ""
            label = f'Approved {qtype} using [{specialists}]'
            if snippet:
                label += f' — "{snippet[:100]}"'
            hints.append(label)
        return hints[:3]  # cap to avoid prompt bloat

    def _inject_recalled_context(
        self, planning_message: str, org_id: str, query: str,
        episodic: list[dict] | None = None,
        workspace_id: str | None = None,
    ) -> str:
        """Prepend relevant memories + approved-pattern hints to the planning message.

        Only injects context when there are high-confidence vector hits or
        approved episodic patterns. Silently skips on any error — recall is best-effort.
        """
        parts: list[str] = []

        # 0. Workspace context injection — when the user is operating in a specific workspace
        if workspace_id:
            try:
                from packages.workspaces import WorkspaceService
                from packages.okrs import OKRService
                from pathlib import Path
                repo_root = self._tool_executor._repo_root
                ws_svc = WorkspaceService(db_path=repo_root / "data" / "friday_workspaces.sqlite3")
                ws_summary = ws_svc.get_context_summary(workspace_id)
                if ws_summary:
                    okr_svc = OKRService(db_path=repo_root / "data" / "friday_okrs.sqlite3")
                    ws_okrs = okr_svc.list_objectives(org_id=org_id, workspace_id=workspace_id, parent_id=None)
                    okr_titles = [o.title for o in ws_okrs[:5]]
                    okr_text = ", ".join(okr_titles) if okr_titles else "none linked"
                    parts.append(
                        f"WORKSPACE CONTEXT (current workspace: {workspace_id}):\n"
                        f"{ws_summary}\n\n"
                        f"Linked OKRs: {okr_text}"
                    )
            except Exception as exc:
                _log.debug("workspace context injection failed (non-fatal): %s", exc)

        # 1. Episodic learning hints from approved past runs
        if episodic:
            approved_hints = self._get_approved_hints(episodic)
            if approved_hints:
                hints_text = "\n".join(f"- {h}" for h in approved_hints)
                parts.append(f"Prior approved patterns (use these specialist combinations for similar requests):\n{hints_text}")

        # 2. Semantic recall from vector store
        try:
            recalled = self._memory.semantic_recall(org_id=org_id, query=query, top_k=3)
            if recalled:
                useful = [r for r in recalled if r.get("similarity", 1.0) == 0.0 or r.get("similarity", 0) > 0.55]
                if useful:
                    snippets = "\n".join(f"- {r['content_text'][:300]}" for r in useful)
                    parts.append(f"Relevant context recalled from prior sessions:\n{snippets}")
                    _log.debug("Injecting %d recalled memories into planning message", len(useful))
        except Exception as exc:
            _log.debug("semantic_recall injection failed (non-fatal): %s", exc)

        if not parts:
            return planning_message
        context_block = "\n\n---\n" + "\n\n".join(parts) + "\n---"
        return planning_message + context_block

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

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

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
from workers.orchestrator.critic import run_critic
from workers.orchestrator.planner import build_plan
from workers.orchestrator.synthesizer import synthesize


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
    ) -> None:
        self._registry = registry
        self._memory = memory
        self._policy = policy
        self._approvals = approvals
        self._audit = audit
        self._tool_executor = tool_executor or ToolExecutor(Path.cwd())

    def run(self, request: ChatRequest) -> dict:
        run_id = f"run_{uuid4().hex[:12]}"

        memory_bundle = self._memory.load(
            org_id=request.org_id,
            conversation_id=request.conversation_id,
            working={"user_message": request.message, "context_packet": request.context_packet},
        )
        planning_message = self._resolve_planning_message(request.message, memory_bundle.conversation)
        plan = build_plan(planning_message)
        validate_required_fields(plan, PLANNER_OUTPUT_SCHEMA, "PlannerOutput")

        specialists = []
        for specialist_id in plan.recommended_specialists:
            specialists.append(self._registry.build_specialist(specialist_id))

        tool_calls = self._run_context_tools(
            tool_names=plan.required_tools,
            query=request.message,
            specialists=plan.recommended_specialists,
            risk_level=plan.risk_level,
        )

        memos = [specialist.run(plan=plan, user_message=request.message) for specialist in specialists]
        for memo in memos:
            validate_required_fields(memo, SPECIALIST_MEMO_SCHEMA, "SpecialistMemo")

        critic_report = run_critic(memos)
        validate_required_fields(critic_report, CRITIC_REPORT_SCHEMA, "CriticReport")

        final_answer = synthesize(plan, memos, critic_report)
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
        }

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

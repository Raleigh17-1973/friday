from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Process Mapping models ────────────────────────────────────────────────────

@dataclass
class ProcessStep:
    id: str
    name: str
    owner: str
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    sla: str = ""
    description: str = ""
    duration_estimate: str = ""
    output_artifact: str = ""


@dataclass
class ProcessDocument:
    """Normalized business process extracted from a multi-turn interview."""

    id: str
    org_id: str
    process_name: str
    trigger: str
    steps: list[ProcessStep]
    decision_points: list[dict[str, Any]]
    roles: list[str]
    tools: list[str]
    exceptions: list[dict[str, Any]]
    kpis: list[dict[str, Any]]
    mermaid_flowchart: str
    mermaid_swimlane: str
    completeness_score: float
    version: str = "1.0.0"
    status: str = "draft"          # draft | active | deprecated
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    changelog: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProcessDocument":
        steps = [ProcessStep(**s) if isinstance(s, dict) else s for s in data.get("steps", [])]
        return cls(
            id=str(data["id"]),
            org_id=str(data.get("org_id", "org-1")),
            process_name=str(data["process_name"]),
            trigger=str(data.get("trigger", "")),
            steps=steps,
            decision_points=list(data.get("decision_points", [])),
            roles=list(data.get("roles", [])),
            tools=list(data.get("tools", [])),
            exceptions=list(data.get("exceptions", [])),
            kpis=list(data.get("kpis", [])),
            mermaid_flowchart=str(data.get("mermaid_flowchart", "")),
            mermaid_swimlane=str(data.get("mermaid_swimlane", "")),
            completeness_score=float(data.get("completeness_score", 0.0)),
            version=str(data.get("version", "1.0.0")),
            status=str(data.get("status", "draft")),
            created_at=str(data.get("created_at", utc_now_iso())),
            updated_at=str(data.get("updated_at", utc_now_iso())),
            changelog=list(data.get("changelog", [])),
        )


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ActionMode(str, Enum):
    READ_ONLY = "read_only"
    WRITE = "write"


@dataclass
class ChatRequest:
    user_id: str
    org_id: str
    conversation_id: str
    message: str
    context_packet: dict[str, Any] = field(default_factory=dict)
    workspace_id: str | None = None


@dataclass
class PlannerOutput:
    problem_statement: str
    missing_information: list[str]
    domains_involved: list[str]
    recommended_specialists: list[str]
    required_tools: list[str]
    risk_level: RiskLevel
    output_format: str
    # True when foundational domain-specific discovery questions are present.
    # Generic enrichment questions (timeline, KPI) do NOT set this flag.
    requires_clarification: bool = False


@dataclass
class SpecialistMemo:
    specialist_id: str
    analysis: str
    recommendation: str
    assumptions: list[str]
    risks: list[str]
    evidence: list[str]
    confidence: float
    questions: list[str]
    # Tree-of-thought scenarios — populated only when risk_level is HIGH.
    # Keys: "optimistic", "base", "pessimistic"; each has description/outcome/probability/key_driver.
    scenarios: dict[str, Any] | None = None
    # Structured write actions the specialist requests the manager to execute after synthesis.
    # Each entry: {"tool": "okrs.create", "args": {"title": "...", ...}}
    tool_requests: list[dict] = field(default_factory=list)


@dataclass
class CriticReport:
    blind_spots: list[str]
    challenged_assumptions: list[str]
    alternative_path: str
    residual_risks: list[str]


@dataclass
class FinalAnswerPackage:
    direct_answer: str
    executive_summary: str
    key_assumptions: list[str]
    major_risks: list[str]
    recommended_next_steps: list[str]
    what_i_would_do_first: str | None = None
    experts_consulted: list[str] = field(default_factory=list)
    confidence: float | None = None
    artifacts: dict[str, str] = field(default_factory=dict)


@dataclass
class ApprovalRequest:
    approval_id: str
    run_id: str
    reason: str
    action_summary: str
    requested_scopes: list[str]
    created_at: str = field(default_factory=utc_now_iso)
    status: str = "pending"


@dataclass
class MemoryCandidate:
    candidate_id: str
    run_id: str
    candidate_type: str
    content: dict[str, Any]
    risk_level: RiskLevel
    auto_accepted: bool


@dataclass
class RunTrace:
    run_id: str
    org_id: str
    user_id: str
    conversation_id: str
    planner: PlannerOutput
    selected_agents: list[str]
    tool_calls: list[dict[str, Any]]
    specialist_memos: list[SpecialistMemo]
    critic_report: CriticReport
    final_answer: FinalAnswerPackage
    confidence: float
    feedback: dict[str, Any]
    outcome: dict[str, Any]
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunTrace":
        return cls(
            run_id=str(data["run_id"]),
            org_id=str(data["org_id"]),
            user_id=str(data["user_id"]),
            conversation_id=str(data["conversation_id"]),
            planner=PlannerOutput(
                problem_statement=str(data["planner"]["problem_statement"]),
                missing_information=list(data["planner"]["missing_information"]),
                domains_involved=list(data["planner"]["domains_involved"]),
                recommended_specialists=list(data["planner"]["recommended_specialists"]),
                required_tools=list(data["planner"]["required_tools"]),
                risk_level=RiskLevel(str(data["planner"]["risk_level"])),
                output_format=str(data["planner"]["output_format"]),
            ),
            selected_agents=list(data["selected_agents"]),
            tool_calls=list(data["tool_calls"]),
            specialist_memos=[
                SpecialistMemo(
                    specialist_id=str(memo["specialist_id"]),
                    analysis=str(memo["analysis"]),
                    recommendation=str(memo["recommendation"]),
                    assumptions=list(memo["assumptions"]),
                    risks=list(memo["risks"]),
                    evidence=list(memo["evidence"]),
                    confidence=float(memo["confidence"]),
                    questions=list(memo["questions"]),
                    scenarios=memo.get("scenarios"),
                    tool_requests=list(memo.get("tool_requests", [])),
                )
                for memo in data["specialist_memos"]
            ],
            critic_report=CriticReport(
                blind_spots=list(data["critic_report"]["blind_spots"]),
                challenged_assumptions=list(data["critic_report"]["challenged_assumptions"]),
                alternative_path=str(data["critic_report"]["alternative_path"]),
                residual_risks=list(data["critic_report"]["residual_risks"]),
            ),
            final_answer=FinalAnswerPackage(
                direct_answer=str(data["final_answer"]["direct_answer"]),
                executive_summary=str(data["final_answer"]["executive_summary"]),
                key_assumptions=list(data["final_answer"]["key_assumptions"]),
                major_risks=list(data["final_answer"]["major_risks"]),
                recommended_next_steps=list(data["final_answer"]["recommended_next_steps"]),
                what_i_would_do_first=data["final_answer"].get("what_i_would_do_first"),
                experts_consulted=list(data["final_answer"].get("experts_consulted", [])),
                confidence=float(data["final_answer"]["confidence"]) if data["final_answer"].get("confidence") is not None else None,
                artifacts=dict(data["final_answer"].get("artifacts", {})),
            ),
            confidence=float(data["confidence"]),
            feedback=dict(data["feedback"]),
            outcome=dict(data["outcome"]),
            created_at=str(data.get("created_at", utc_now_iso())),
        )

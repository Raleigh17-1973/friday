from __future__ import annotations

"""Enterprise OKR system — dataclasses for all 10 core entities.

Separation of concerns:
  Objective   = qualitative outcome ambition
  KeyResult   = measurable proof of progress
  OKRKPI      = ongoing business metric (health / steady-state)
  OKRInitiative = execution work linked to OKRs
  OKRCheckin  = management ritual record (per KR or per Objective)
  Performance review = SEPARATE SYSTEM — never stored or referenced here
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# 1. OrgNode — one level in the company hierarchy
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class OrgNode:
    node_id: str
    name: str
    node_type: str          # company | business_unit | portfolio | department | team
    org_id: str = "org-1"
    parent_id: str | None = None
    owner_user_id: str = "user-1"
    active_period_id: str | None = None
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)


# ─────────────────────────────────────────────────────────────────────────────
# 2. OKRPeriod — a planning cycle (annual or quarterly)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class OKRPeriod:
    period_id: str
    name: str               # e.g. "FY2026 Q2"
    period_type: str        # annual | quarterly
    fiscal_year: int
    org_id: str = "org-1"
    quarter: int | None = None      # 1-4; None for annual
    start_date: str = ""
    end_date: str = ""
    status: str = "draft"   # draft | active | closed | archived
    created_at: str = field(default_factory=_now)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Objective — qualitative, directional, outcome-focused
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Objective:
    objective_id: str
    period_id: str
    org_node_id: str
    title: str
    org_id: str = "org-1"
    description: str = ""
    rationale: str = ""
    objective_type: str = "committed"       # committed | aspirational
    status: str = "draft"                   # draft | active | paused | completed | archived | graded
    owner_user_id: str = "user-1"
    sponsor_user_id: str | None = None
    parent_objective_id: str | None = None
    visibility: str = "public_internal"     # public_internal | restricted
    alignment_mode: str = "inherited"       # inherited | contributed | shared
    progress_rollup_method: str = "weighted_average"
    score_final: float | None = None
    confidence_current: float = 0.7
    health_current: str = "yellow"          # green | yellow | red
    quality_score: int | None = None        # 1-10; set by OKR Writing Agent
    quality_notes: str = ""
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)


# ─────────────────────────────────────────────────────────────────────────────
# 4. KeyResult — measurable, gradeable, time-bound proof of progress
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class KeyResult:
    kr_id: str
    objective_id: str
    title: str
    org_id: str = "org-1"
    description: str = ""
    kr_type: str = "metric"             # metric | milestone | binary
    metric_name: str | None = None
    metric_definition: str | None = None
    data_source_type: str = "manual"    # manual | integration | formula | warehouse
    source_reference: str | None = None
    baseline_value: float | None = None
    target_value: float | None = None
    current_value: float | None = None
    unit: str = ""
    direction: str = "increase"         # increase | decrease | maintain | achieve
    weighting: float = 1.0
    owner_user_id: str = "user-1"
    checkin_frequency: str = "weekly"
    status: str = "active"
    score_current: float = 0.0
    score_final: float | None = None
    confidence_current: float = 0.7
    health_current: str = "yellow"      # green | yellow | red
    risk_reason: str = ""
    last_checkin_at: str | None = None
    due_date: str | None = None
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)


# ─────────────────────────────────────────────────────────────────────────────
# 5. OKRKPI — health metric; separate from OKR change priority
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class OKRKPI:
    kpi_id: str
    name: str
    org_id: str = "org-1"
    description: str = ""
    owner_user_id: str = "user-1"
    org_node_id: str | None = None
    metric_definition: str = ""
    unit: str = ""
    source_reference: str = ""
    current_value: float | None = None
    target_band_low: float | None = None
    target_band_high: float | None = None
    health_status: str = "yellow"       # green | yellow | red
    update_frequency: str = "monthly"
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)


# ─────────────────────────────────────────────────────────────────────────────
# 6. KRKPILink — junction: how a KPI relates to a KR
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class KRKPILink:
    link_id: str
    key_result_id: str
    kpi_id: str
    link_type: str = "derived_from"     # derived_from | influenced_by | guardrail
    contribution_notes: str = ""
    created_at: str = field(default_factory=_now)


# ─────────────────────────────────────────────────────────────────────────────
# 7. OKRInitiative — execution work; separate from the OKR itself
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class OKRInitiative:
    initiative_id: str
    title: str
    org_id: str = "org-1"
    description: str = ""
    owner_user_id: str = "user-1"
    status: str = "not_started"         # not_started | in_progress | done | blocked | cancelled
    linked_objective_id: str | None = None
    linked_key_result_id: str | None = None
    external_system_ref: str | None = None  # e.g. "jira:PROJ-123"
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)


# ─────────────────────────────────────────────────────────────────────────────
# 8. OKRCheckin — management ritual record (per KR or per Objective)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class OKRCheckin:
    checkin_id: str
    object_type: str        # objective | key_result
    object_id: str
    org_id: str = "org-1"
    user_id: str = "user-1"
    checkin_date: str = field(default_factory=lambda: datetime.now(timezone.utc).date().isoformat())
    current_value: float | None = None
    score_snapshot: float | None = None
    confidence_snapshot: float | None = None
    status_snapshot: str | None = None
    blockers: str = ""
    decisions_needed: str = ""
    narrative_update: str = ""
    next_steps: str = ""
    parent_checkin_id: str | None = None   # links correction → original (immutable audit chain)
    created_at: str = field(default_factory=_now)


# ─────────────────────────────────────────────────────────────────────────────
# 9. OKRDependency — explicit cross-entity dependency
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class OKRDependency:
    dependency_id: str
    source_object_type: str
    source_object_id: str
    target_object_type: str
    target_object_id: str
    dependency_type: str = "contributes_to"  # contributes_to | blocked_by | shared_commitment | informs
    severity: str = "medium"                  # low | medium | high | critical
    org_id: str = "org-1"
    created_at: str = field(default_factory=_now)


# ─────────────────────────────────────────────────────────────────────────────
# 10. MeetingArtifact — auto-generated meeting preparation packet
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class MeetingArtifact:
    artifact_id: str
    meeting_type: str       # weekly_checkin | portfolio_review | quarterly_review | planning_workshop
    org_id: str = "org-1"
    org_node_id: str | None = None
    period_id: str | None = None
    agenda_markdown: str = ""
    pre_read_markdown: str = ""
    decisions_markdown: str = ""
    followups_json: str = "[]"
    generated_at: str = field(default_factory=_now)


# ─────────────────────────────────────────────────────────────────────────────
# Validation result
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ValidationIssue:
    rule_id: str
    severity: str       # error | warning | info
    message: str
    field: str = ""
    suggestion: str = ""

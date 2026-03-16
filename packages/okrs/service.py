from __future__ import annotations

"""EnterpriseOKRService — production-grade OKR operating model.

Design principles encoded here:
  1. Objectives are qualitative, directional, outcome-focused
  2. Key Results are measurable, gradeable, time-bound
  3. KPIs are health metrics; OKRs are change priorities
  4. Committed OKRs target 1.0; trigger escalation when materially at risk
  5. Aspirational OKRs: ~0.7 score is not failure
  6. OKRs are NEVER employee performance scores — no such fields exist
  7. Scoring: metric formula | binary 0/1 | milestone rubric {0.0,0.3,0.7,1.0}
"""

import sqlite3
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from packages.okrs.models import (
    KRKPILink,
    KeyResult,
    MeetingArtifact,
    OKRKPI,
    OKRCheckin,
    OKRDependency,
    OKRInitiative,
    OKRPeriod,
    OrgNode,
    Objective,
    ValidationIssue,
)

# ── helpers ──────────────────────────────────────────────────────────────────

def _uid(prefix: str = "") -> str:
    return prefix + uuid.uuid4().hex[:10]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


# ── SQL ───────────────────────────────────────────────────────────────────────

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS org_nodes (
    node_id          TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    node_type        TEXT NOT NULL,
    parent_id        TEXT,
    owner_user_id    TEXT NOT NULL DEFAULT 'user-1',
    active_period_id TEXT,
    org_id           TEXT NOT NULL DEFAULT 'org-1',
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS okr_periods (
    period_id   TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    period_type TEXT NOT NULL,
    fiscal_year INTEGER NOT NULL,
    quarter     INTEGER,
    start_date  TEXT NOT NULL DEFAULT '',
    end_date    TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'draft',
    org_id      TEXT NOT NULL DEFAULT 'org-1',
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS objectives (
    objective_id        TEXT PRIMARY KEY,
    period_id           TEXT NOT NULL,
    org_node_id         TEXT NOT NULL,
    title               TEXT NOT NULL,
    description         TEXT DEFAULT '',
    rationale           TEXT DEFAULT '',
    objective_type      TEXT NOT NULL DEFAULT 'committed',
    status              TEXT NOT NULL DEFAULT 'draft',
    owner_user_id       TEXT NOT NULL DEFAULT 'user-1',
    sponsor_user_id     TEXT,
    parent_objective_id TEXT,
    visibility          TEXT NOT NULL DEFAULT 'public_internal',
    alignment_mode      TEXT NOT NULL DEFAULT 'inherited',
    progress_rollup_method TEXT NOT NULL DEFAULT 'weighted_average',
    score_final         REAL,
    confidence_current  REAL NOT NULL DEFAULT 0.7,
    health_current      TEXT NOT NULL DEFAULT 'yellow',
    quality_score       INTEGER,
    quality_notes       TEXT DEFAULT '',
    org_id              TEXT NOT NULL DEFAULT 'org-1',
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS key_results (
    kr_id               TEXT PRIMARY KEY,
    objective_id        TEXT NOT NULL,
    title               TEXT NOT NULL,
    description         TEXT DEFAULT '',
    kr_type             TEXT NOT NULL DEFAULT 'metric',
    metric_name         TEXT,
    metric_definition   TEXT,
    data_source_type    TEXT NOT NULL DEFAULT 'manual',
    source_reference    TEXT,
    baseline_value      REAL,
    target_value        REAL,
    current_value       REAL,
    unit                TEXT DEFAULT '',
    direction           TEXT DEFAULT 'increase',
    weighting           REAL NOT NULL DEFAULT 1.0,
    owner_user_id       TEXT NOT NULL DEFAULT 'user-1',
    checkin_frequency   TEXT NOT NULL DEFAULT 'weekly',
    status              TEXT NOT NULL DEFAULT 'active',
    score_current       REAL NOT NULL DEFAULT 0.0,
    score_final         REAL,
    confidence_current  REAL NOT NULL DEFAULT 0.7,
    health_current      TEXT NOT NULL DEFAULT 'yellow',
    risk_reason         TEXT DEFAULT '',
    last_checkin_at     TEXT,
    due_date            TEXT,
    org_id              TEXT NOT NULL DEFAULT 'org-1',
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS okr_kpis (
    kpi_id            TEXT PRIMARY KEY,
    name              TEXT NOT NULL,
    description       TEXT DEFAULT '',
    owner_user_id     TEXT NOT NULL DEFAULT 'user-1',
    org_node_id       TEXT,
    metric_definition TEXT DEFAULT '',
    unit              TEXT NOT NULL DEFAULT '',
    source_reference  TEXT DEFAULT '',
    current_value     REAL,
    target_band_low   REAL,
    target_band_high  REAL,
    health_status     TEXT DEFAULT 'yellow',
    update_frequency  TEXT DEFAULT 'monthly',
    org_id            TEXT NOT NULL DEFAULT 'org-1',
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS kr_kpi_links (
    link_id            TEXT PRIMARY KEY,
    key_result_id      TEXT NOT NULL,
    kpi_id             TEXT NOT NULL,
    link_type          TEXT NOT NULL DEFAULT 'derived_from',
    contribution_notes TEXT DEFAULT '',
    created_at         TEXT NOT NULL,
    UNIQUE(key_result_id, kpi_id, link_type)
);
CREATE TABLE IF NOT EXISTS okr_initiatives (
    initiative_id        TEXT PRIMARY KEY,
    title                TEXT NOT NULL,
    description          TEXT DEFAULT '',
    owner_user_id        TEXT NOT NULL DEFAULT 'user-1',
    status               TEXT NOT NULL DEFAULT 'not_started',
    linked_objective_id  TEXT,
    linked_key_result_id TEXT,
    external_system_ref  TEXT,
    org_id               TEXT NOT NULL DEFAULT 'org-1',
    created_at           TEXT NOT NULL,
    updated_at           TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS okr_checkins (
    checkin_id          TEXT PRIMARY KEY,
    object_type         TEXT NOT NULL,
    object_id           TEXT NOT NULL,
    user_id             TEXT NOT NULL DEFAULT 'user-1',
    checkin_date        TEXT NOT NULL,
    current_value       REAL,
    score_snapshot      REAL,
    confidence_snapshot REAL,
    status_snapshot     TEXT,
    blockers            TEXT DEFAULT '',
    decisions_needed    TEXT DEFAULT '',
    narrative_update    TEXT DEFAULT '',
    next_steps          TEXT DEFAULT '',
    org_id              TEXT NOT NULL DEFAULT 'org-1',
    parent_checkin_id   TEXT REFERENCES okr_checkins(checkin_id),
    created_at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_checkins_object
    ON okr_checkins(object_type, object_id, created_at DESC);
CREATE TABLE IF NOT EXISTS okr_dependencies (
    dependency_id      TEXT PRIMARY KEY,
    source_object_type TEXT NOT NULL,
    source_object_id   TEXT NOT NULL,
    target_object_type TEXT NOT NULL,
    target_object_id   TEXT NOT NULL,
    dependency_type    TEXT NOT NULL DEFAULT 'contributes_to',
    severity           TEXT NOT NULL DEFAULT 'medium',
    org_id             TEXT NOT NULL DEFAULT 'org-1',
    created_at         TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meeting_artifacts (
    artifact_id        TEXT PRIMARY KEY,
    meeting_type       TEXT NOT NULL,
    org_node_id        TEXT,
    period_id          TEXT,
    agenda_markdown    TEXT DEFAULT '',
    pre_read_markdown  TEXT DEFAULT '',
    decisions_markdown TEXT DEFAULT '',
    followups_json     TEXT DEFAULT '[]',
    generated_at       TEXT NOT NULL,
    org_id             TEXT NOT NULL DEFAULT 'org-1'
);
"""


class EnterpriseOKRService:
    """Full OKR operating model: org hierarchy, periods, objectives, key results,
    KPIs with guardrails, check-ins, dependencies, initiatives, meetings."""

    def __init__(self, db_path: Path | None = None) -> None:
        path = str(db_path) if db_path else ":memory:"
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_CREATE_SQL)
        self._conn.commit()
        self._seed_defaults()

    def _seed_defaults(self) -> None:
        now = _now()
        self._conn.execute(
            """INSERT OR IGNORE INTO org_nodes
               (node_id,name,node_type,parent_id,owner_user_id,active_period_id,org_id,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            ("node-company", "Company", "company", None, "user-1", None, "org-1", now, now),
        )
        self._conn.commit()

    # ── OrgNode ───────────────────────────────────────────────────────────────

    def create_org_node(self, name: str, node_type: str, org_id: str = "org-1",
                        parent_id: str | None = None, owner_user_id: str = "user-1") -> OrgNode:
        now = _now()
        node = OrgNode(node_id=_uid("node-"), name=name, node_type=node_type,
                       org_id=org_id, parent_id=parent_id, owner_user_id=owner_user_id,
                       created_at=now, updated_at=now)
        self._conn.execute(
            """INSERT INTO org_nodes (node_id,name,node_type,parent_id,owner_user_id,
               active_period_id,org_id,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)""",
            (node.node_id, node.name, node.node_type, node.parent_id, node.owner_user_id,
             node.active_period_id, node.org_id, node.created_at, node.updated_at),
        )
        self._conn.commit()
        return node

    def get_org_node(self, node_id: str) -> OrgNode | None:
        row = self._conn.execute("SELECT * FROM org_nodes WHERE node_id=?", (node_id,)).fetchone()
        return self._to_org_node(row) if row else None

    def list_org_nodes(self, org_id: str = "org-1") -> list[OrgNode]:
        rows = self._conn.execute(
            "SELECT * FROM org_nodes WHERE org_id=? ORDER BY name", (org_id,)).fetchall()
        return [self._to_org_node(r) for r in rows]

    def update_org_node(self, node_id: str, **kw: Any) -> OrgNode | None:
        allowed = {"name","node_type","parent_id","owner_user_id","active_period_id"}
        ups = {k: v for k, v in kw.items() if k in allowed}
        if not ups: return self.get_org_node(node_id)
        ups["updated_at"] = _now()
        sets = ", ".join(f"{k}=?" for k in ups)
        self._conn.execute(f"UPDATE org_nodes SET {sets} WHERE node_id=?", (*ups.values(), node_id))
        self._conn.commit()
        return self.get_org_node(node_id)

    def get_org_tree(self, org_id: str = "org-1", root_node_id: str | None = None) -> dict:
        nodes = self.list_org_nodes(org_id)
        by_id = {n.node_id: {**asdict(n), "children": []} for n in nodes}
        roots = []
        for n in nodes:
            if n.parent_id and n.parent_id in by_id:
                by_id[n.parent_id]["children"].append(by_id[n.node_id])
            else:
                roots.append(by_id[n.node_id])
        return {"nodes": roots}

    def _to_org_node(self, row: sqlite3.Row) -> OrgNode:
        d = dict(row)
        return OrgNode(**{k: d[k] for k in OrgNode.__dataclass_fields__ if k in d})

    # ── OKRPeriod ─────────────────────────────────────────────────────────────

    def create_period(self, name: str, period_type: str, fiscal_year: int,
                      quarter: int | None = None,
                      start_date: str = "", end_date: str = "",
                      org_id: str = "org-1") -> OKRPeriod:
        p = OKRPeriod(period_id=_uid("period-"), name=name, period_type=period_type,
                      fiscal_year=fiscal_year, quarter=quarter,
                      start_date=start_date, end_date=end_date,
                      org_id=org_id, created_at=_now())
        self._conn.execute(
            """INSERT INTO okr_periods (period_id,name,period_type,fiscal_year,quarter,
               start_date,end_date,status,org_id,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (p.period_id, p.name, p.period_type, p.fiscal_year, p.quarter,
             p.start_date, p.end_date, p.status, p.org_id, p.created_at),
        )
        self._conn.commit()
        return p

    def get_period(self, period_id: str) -> OKRPeriod | None:
        row = self._conn.execute("SELECT * FROM okr_periods WHERE period_id=?", (period_id,)).fetchone()
        return self._to_period(row) if row else None

    def list_periods(self, org_id: str = "org-1", status: str | None = None) -> list[OKRPeriod]:
        if status:
            rows = self._conn.execute(
                "SELECT * FROM okr_periods WHERE org_id=? AND status=? ORDER BY fiscal_year DESC, quarter DESC",
                (org_id, status)).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM okr_periods WHERE org_id=? ORDER BY fiscal_year DESC, quarter DESC",
                (org_id,)).fetchall()
        return [self._to_period(r) for r in rows]

    def update_period(self, period_id: str, **kw: Any) -> OKRPeriod | None:
        ups = {k: v for k, v in kw.items() if k in {"name","status","start_date","end_date"}}
        if not ups: return self.get_period(period_id)
        sets = ", ".join(f"{k}=?" for k in ups)
        self._conn.execute(f"UPDATE okr_periods SET {sets} WHERE period_id=?", (*ups.values(), period_id))
        self._conn.commit()
        return self.get_period(period_id)

    def activate_period(self, period_id: str) -> OKRPeriod | None:
        return self.update_period(period_id, status="active")

    def close_period(self, period_id: str) -> OKRPeriod | None:
        return self.update_period(period_id, status="closed")

    def _to_period(self, row: sqlite3.Row) -> OKRPeriod:
        d = dict(row)
        return OKRPeriod(**{k: d[k] for k in OKRPeriod.__dataclass_fields__ if k in d})

    # ── Objective ─────────────────────────────────────────────────────────────

    def create_objective(self, period_id: str, org_node_id: str, title: str,
                         objective_type: str = "committed", owner_user_id: str = "user-1",
                         org_id: str = "org-1", **kw: Any) -> Objective:
        now = _now()
        extra = {k: v for k, v in kw.items() if k in Objective.__dataclass_fields__}
        obj = Objective(objective_id=_uid("obj-"), period_id=period_id,
                        org_node_id=org_node_id, title=title, objective_type=objective_type,
                        owner_user_id=owner_user_id, org_id=org_id,
                        created_at=now, updated_at=now, **extra)
        self._conn.execute(
            """INSERT INTO objectives (objective_id,period_id,org_node_id,title,description,
               rationale,objective_type,status,owner_user_id,sponsor_user_id,
               parent_objective_id,visibility,alignment_mode,progress_rollup_method,
               score_final,confidence_current,health_current,quality_score,quality_notes,
               org_id,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (obj.objective_id, obj.period_id, obj.org_node_id, obj.title, obj.description,
             obj.rationale, obj.objective_type, obj.status, obj.owner_user_id, obj.sponsor_user_id,
             obj.parent_objective_id, obj.visibility, obj.alignment_mode,
             obj.progress_rollup_method, obj.score_final, obj.confidence_current,
             obj.health_current, obj.quality_score, obj.quality_notes,
             obj.org_id, obj.created_at, obj.updated_at),
        )
        self._conn.commit()
        return obj

    def get_objective(self, objective_id: str) -> Objective | None:
        row = self._conn.execute(
            "SELECT * FROM objectives WHERE objective_id=?", (objective_id,)).fetchone()
        return self._to_objective(row) if row else None

    def list_objectives(self, org_id: str = "org-1", org_node_id: str | None = None,
                        period_id: str | None = None, status: str | None = None,
                        objective_type: str | None = None,
                        parent_id: str | None = None) -> list[Objective]:
        clauses, params = ["org_id=?"], [org_id]
        if org_node_id: clauses.append("org_node_id=?"); params.append(org_node_id)
        if period_id: clauses.append("period_id=?"); params.append(period_id)
        if status: clauses.append("status=?"); params.append(status)
        if objective_type: clauses.append("objective_type=?"); params.append(objective_type)
        if parent_id: clauses.append("parent_objective_id=?"); params.append(parent_id)
        sql = f"SELECT * FROM objectives WHERE {' AND '.join(clauses)} ORDER BY created_at DESC"
        return [self._to_objective(r) for r in self._conn.execute(sql, params).fetchall()]

    def update_objective(self, objective_id: str, **kw: Any) -> Objective | None:
        allowed = {"title","description","rationale","objective_type","status","owner_user_id",
                   "sponsor_user_id","parent_objective_id","visibility","alignment_mode",
                   "progress_rollup_method","score_final","confidence_current","health_current",
                   "quality_score","quality_notes"}
        ups = {k: v for k, v in kw.items() if k in allowed}
        if not ups: return self.get_objective(objective_id)
        ups["updated_at"] = _now()
        sets = ", ".join(f"{k}=?" for k in ups)
        self._conn.execute(
            f"UPDATE objectives SET {sets} WHERE objective_id=?", (*ups.values(), objective_id))
        self._conn.commit()
        return self.get_objective(objective_id)

    def archive_objective(self, objective_id: str) -> Objective | None:
        return self.update_objective(objective_id, status="archived")

    def get_objective_with_details(self, objective_id: str) -> dict:
        obj = self.get_objective(objective_id)
        if not obj: return {}
        krs = self.list_key_results(objective_id)
        kr_details = []
        for kr in krs:
            d = asdict(kr)
            d["kpi_links"] = [asdict(l) for l in self.list_kr_kpi_links(kr.kr_id)]
            d["guardrail_kpis"] = [asdict(k) for k in self.get_guardrail_kpis(kr.kr_id)]
            kr_details.append(d)
        children = self._conn.execute(
            "SELECT * FROM objectives WHERE parent_objective_id=?", (objective_id,)).fetchall()
        parent = self.get_objective(obj.parent_objective_id) if obj.parent_objective_id else None
        return {
            "objective": asdict(obj),
            "key_results": kr_details,
            "checkins": [asdict(c) for c in self.list_checkins("objective", objective_id)],
            "dependencies": [asdict(d) for d in self.list_dependencies("objective", objective_id)],
            "initiatives": [asdict(i) for i in self.list_initiatives(obj.org_id, objective_id=objective_id)],
            "children": [dict(r) for r in children],
            "parent": asdict(parent) if parent else None,
            "score": self.compute_objective_score(objective_id),
        }

    def get_children(self, objective_id: str) -> list[Objective]:
        rows = self._conn.execute(
            "SELECT * FROM objectives WHERE parent_objective_id=?", (objective_id,)).fetchall()
        return [self._to_objective(r) for r in rows]

    def get_hierarchy(self, root_id: str) -> dict:
        obj = self.get_objective(root_id)
        if not obj: return {}
        result = asdict(obj)
        result["key_results"] = [asdict(kr) for kr in self.list_key_results(root_id)]
        result["children"] = [self.get_hierarchy(c.objective_id) for c in self.get_children(root_id)]
        return result

    def grade_objective(self, objective_id: str, grade: float, retrospective: str = "",
                        carry_forward: bool = False, next_period: str | None = None) -> dict:
        grade = _clamp(grade)
        label = ("Did Not Start" if grade < 0.1 else "Partial" if grade < 0.45
                 else "Good Progress" if grade < 0.75 else "Fully Achieved")
        now = _now()
        self._conn.execute(
            "UPDATE objectives SET score_final=?, status='graded', quality_notes=?, updated_at=? WHERE objective_id=?",
            (grade, retrospective, now, objective_id))
        self._conn.commit()
        result: dict = {"objective_id": objective_id, "grade": grade,
                        "grade_label": label, "retrospective": retrospective, "graded_at": now}
        if carry_forward and next_period:
            obj = self.get_objective(objective_id)
            if obj:
                carried = self.create_objective(
                    period_id=next_period, org_node_id=obj.org_node_id, title=obj.title,
                    objective_type=obj.objective_type, owner_user_id=obj.owner_user_id,
                    org_id=obj.org_id, description=obj.description,
                    rationale=f"Carried forward from {obj.period_id}. {obj.rationale}".strip(),
                    parent_objective_id=obj.parent_objective_id)
                result["carry_forward_obj_id"] = carried.objective_id
                result["carry_forward_period"] = next_period
        return result

    def _to_objective(self, row: sqlite3.Row) -> Objective:
        d = dict(row)
        return Objective(**{k: d[k] for k in Objective.__dataclass_fields__ if k in d})

    # ── Scoring ───────────────────────────────────────────────────────────────

    def compute_kr_score(self, kr_id: str) -> float:
        row = self._conn.execute("SELECT * FROM key_results WHERE kr_id=?", (kr_id,)).fetchone()
        return self._score_kr(self._to_kr(row)) if row else 0.0

    def _score_kr(self, kr: KeyResult) -> float:
        if kr.kr_type == "binary":
            if kr.current_value is not None and kr.target_value is not None:
                return 1.0 if kr.current_value >= kr.target_value else 0.0
            return 0.0
        if kr.kr_type == "milestone":
            return _clamp(kr.current_value or 0.0)
        # metric
        b = kr.baseline_value or 0.0
        t = kr.target_value
        c = kr.current_value
        if t is None or c is None: return 0.0
        denom = t - b
        if denom == 0: return 1.0 if c >= t else 0.0
        if kr.direction == "decrease":
            return _clamp((b - c) / (b - t)) if (b - t) != 0 else 0.0
        return _clamp((c - b) / denom)

    def update_kr_score(self, kr_id: str) -> KeyResult | None:
        kr = self._get_kr(kr_id)
        if not kr: return None
        score = self._score_kr(kr)
        health = self._kr_health(score, kr.confidence_current)
        self._conn.execute(
            "UPDATE key_results SET score_current=?, health_current=?, updated_at=? WHERE kr_id=?",
            (score, health, _now(), kr_id))
        self._conn.commit()
        self._recompute_obj_health(kr.objective_id)
        return self._get_kr(kr_id)

    def compute_objective_score(self, objective_id: str) -> float:
        rows = self._conn.execute(
            "SELECT score_current, weighting FROM key_results WHERE objective_id=? AND status!='archived'",
            (objective_id,)).fetchall()
        if not rows: return 0.0
        total_w = sum(r["weighting"] for r in rows)
        if total_w == 0: return 0.0
        return _clamp(sum(r["score_current"] * r["weighting"] for r in rows) / total_w)

    def _kr_health(self, score: float, confidence: float) -> str:
        if confidence >= 0.75 and score >= 0.5: return "green"
        if confidence < 0.4 or score < 0.2: return "red"
        return "yellow"

    def _obj_health(self, score: float, confidence: float) -> str:
        if confidence >= 0.75 and score >= 0.5: return "green"
        if confidence < 0.4 or score < 0.2: return "red"
        return "yellow"

    def _recompute_obj_health(self, objective_id: str) -> None:
        obj = self.get_objective(objective_id)
        if not obj: return
        score = self.compute_objective_score(objective_id)
        health = self._obj_health(score, obj.confidence_current)
        self._conn.execute(
            "UPDATE objectives SET health_current=?, updated_at=? WHERE objective_id=?",
            (health, _now(), objective_id))
        self._conn.commit()

    # ── KeyResult ─────────────────────────────────────────────────────────────

    def create_key_result(self, objective_id: str, title: str, kr_type: str = "metric",
                          owner_user_id: str = "user-1", org_id: str = "org-1",
                          **kw: Any) -> KeyResult:
        now = _now()
        extra = {k: v for k, v in kw.items() if k in KeyResult.__dataclass_fields__}
        kr = KeyResult(kr_id=_uid("kr-"), objective_id=objective_id, title=title,
                       kr_type=kr_type, owner_user_id=owner_user_id, org_id=org_id,
                       created_at=now, updated_at=now, **extra)
        self._conn.execute(
            """INSERT INTO key_results (kr_id,objective_id,title,description,kr_type,
               metric_name,metric_definition,data_source_type,source_reference,
               baseline_value,target_value,current_value,unit,direction,weighting,
               owner_user_id,checkin_frequency,status,score_current,score_final,
               confidence_current,health_current,risk_reason,last_checkin_at,due_date,
               org_id,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (kr.kr_id, kr.objective_id, kr.title, kr.description, kr.kr_type,
             kr.metric_name, kr.metric_definition, kr.data_source_type, kr.source_reference,
             kr.baseline_value, kr.target_value, kr.current_value, kr.unit, kr.direction,
             kr.weighting, kr.owner_user_id, kr.checkin_frequency, kr.status,
             kr.score_current, kr.score_final, kr.confidence_current, kr.health_current,
             kr.risk_reason, kr.last_checkin_at, kr.due_date,
             kr.org_id, kr.created_at, kr.updated_at),
        )
        self._conn.commit()
        return kr

    def _get_kr(self, kr_id: str) -> KeyResult | None:
        row = self._conn.execute("SELECT * FROM key_results WHERE kr_id=?", (kr_id,)).fetchone()
        return self._to_kr(row) if row else None

    def list_key_results(self, objective_id: str) -> list[KeyResult]:
        rows = self._conn.execute(
            "SELECT * FROM key_results WHERE objective_id=? ORDER BY created_at", (objective_id,)).fetchall()
        return [self._to_kr(r) for r in rows]

    def update_key_result(self, kr_id: str, **kw: Any) -> KeyResult | None:
        allowed = {"title","description","kr_type","metric_name","metric_definition",
                   "data_source_type","source_reference","baseline_value","target_value",
                   "current_value","unit","direction","weighting","owner_user_id",
                   "checkin_frequency","status","confidence_current","risk_reason",
                   "last_checkin_at","due_date","score_final"}
        ups = {k: v for k, v in kw.items() if k in allowed}
        if not ups: return self._get_kr(kr_id)
        ups["updated_at"] = _now()
        sets = ", ".join(f"{k}=?" for k in ups)
        self._conn.execute(f"UPDATE key_results SET {sets} WHERE kr_id=?", (*ups.values(), kr_id))
        self._conn.commit()
        return self.update_kr_score(kr_id)

    def delete_key_result(self, kr_id: str) -> bool:
        self._conn.execute(
            "UPDATE key_results SET status='archived', updated_at=? WHERE kr_id=?", (_now(), kr_id))
        self._conn.commit()
        return True

    def _to_kr(self, row: sqlite3.Row) -> KeyResult:
        d = dict(row)
        return KeyResult(**{k: d[k] for k in KeyResult.__dataclass_fields__ if k in d})

    # ── OKRKPI ────────────────────────────────────────────────────────────────

    def create_kpi(self, name: str, unit: str = "", org_id: str = "org-1",
                   org_node_id: str | None = None, **kw: Any) -> OKRKPI:
        now = _now()
        extra = {k: v for k, v in kw.items() if k in OKRKPI.__dataclass_fields__}
        kpi = OKRKPI(kpi_id=_uid("kpi-"), name=name, unit=unit, org_id=org_id,
                     org_node_id=org_node_id, created_at=now, updated_at=now, **extra)
        self._conn.execute(
            """INSERT INTO okr_kpis (kpi_id,name,description,owner_user_id,org_node_id,
               metric_definition,unit,source_reference,current_value,target_band_low,
               target_band_high,health_status,update_frequency,org_id,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (kpi.kpi_id, kpi.name, kpi.description, kpi.owner_user_id, kpi.org_node_id,
             kpi.metric_definition, kpi.unit, kpi.source_reference, kpi.current_value,
             kpi.target_band_low, kpi.target_band_high, kpi.health_status,
             kpi.update_frequency, kpi.org_id, kpi.created_at, kpi.updated_at),
        )
        self._conn.commit()
        return kpi

    def get_kpi(self, kpi_id: str) -> OKRKPI | None:
        row = self._conn.execute("SELECT * FROM okr_kpis WHERE kpi_id=?", (kpi_id,)).fetchone()
        return self._to_kpi(row) if row else None

    def list_kpis(self, org_id: str = "org-1", org_node_id: str | None = None) -> list[OKRKPI]:
        if org_node_id:
            rows = self._conn.execute(
                "SELECT * FROM okr_kpis WHERE org_id=? AND org_node_id=? ORDER BY name",
                (org_id, org_node_id)).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM okr_kpis WHERE org_id=? ORDER BY name", (org_id,)).fetchall()
        return [self._to_kpi(r) for r in rows]

    def update_kpi(self, kpi_id: str, **kw: Any) -> OKRKPI | None:
        allowed = {"name","description","owner_user_id","org_node_id","metric_definition",
                   "unit","source_reference","current_value","target_band_low","target_band_high",
                   "health_status","update_frequency"}
        ups = {k: v for k, v in kw.items() if k in allowed}
        if not ups: return self.get_kpi(kpi_id)
        ups["updated_at"] = _now()
        sets = ", ".join(f"{k}=?" for k in ups)
        self._conn.execute(f"UPDATE okr_kpis SET {sets} WHERE kpi_id=?", (*ups.values(), kpi_id))
        self._conn.commit()
        return self.get_kpi(kpi_id)

    def record_kpi_value(self, kpi_id: str, value: float) -> OKRKPI | None:
        kpi = self.get_kpi(kpi_id)
        if not kpi: return None
        health = "yellow"
        lo, hi = kpi.target_band_low, kpi.target_band_high
        if lo is not None and hi is not None:
            health = "green" if lo <= value <= hi else ("red" if value < lo * 0.9 else "yellow")
        elif lo is not None:
            health = "green" if value >= lo else ("red" if value < lo * 0.9 else "yellow")
        self._conn.execute(
            "UPDATE okr_kpis SET current_value=?, health_status=?, updated_at=? WHERE kpi_id=?",
            (value, health, _now(), kpi_id))
        self._conn.commit()
        return self.get_kpi(kpi_id)

    def _to_kpi(self, row: sqlite3.Row) -> OKRKPI:
        d = dict(row)
        return OKRKPI(**{k: d[k] for k in OKRKPI.__dataclass_fields__ if k in d})

    # ── KRKPILink ─────────────────────────────────────────────────────────────

    def link_kr_to_kpi(self, kr_id: str, kpi_id: str, link_type: str = "derived_from",
                       contribution_notes: str = "") -> KRKPILink:
        link = KRKPILink(link_id=_uid("lnk-"), key_result_id=kr_id, kpi_id=kpi_id,
                         link_type=link_type, contribution_notes=contribution_notes, created_at=_now())
        self._conn.execute(
            """INSERT OR REPLACE INTO kr_kpi_links
               (link_id,key_result_id,kpi_id,link_type,contribution_notes,created_at)
               VALUES (?,?,?,?,?,?)""",
            (link.link_id, link.key_result_id, link.kpi_id, link.link_type,
             link.contribution_notes, link.created_at))
        self._conn.commit()
        return link

    def unlink_kr_kpi(self, kr_id: str, kpi_id: str) -> bool:
        self._conn.execute(
            "DELETE FROM kr_kpi_links WHERE key_result_id=? AND kpi_id=?", (kr_id, kpi_id))
        self._conn.commit()
        return True

    def list_kr_kpi_links(self, kr_id: str) -> list[KRKPILink]:
        rows = self._conn.execute(
            "SELECT * FROM kr_kpi_links WHERE key_result_id=?", (kr_id,)).fetchall()
        return [self._to_link(r) for r in rows]

    def get_guardrail_kpis(self, kr_id: str) -> list[OKRKPI]:
        rows = self._conn.execute(
            """SELECT k.* FROM okr_kpis k JOIN kr_kpi_links l ON k.kpi_id=l.kpi_id
               WHERE l.key_result_id=? AND l.link_type='guardrail'""", (kr_id,)).fetchall()
        return [self._to_kpi(r) for r in rows]

    def _to_link(self, row: sqlite3.Row) -> KRKPILink:
        d = dict(row)
        return KRKPILink(**{k: d[k] for k in KRKPILink.__dataclass_fields__ if k in d})

    # ── OKRInitiative ─────────────────────────────────────────────────────────

    def create_initiative(self, title: str, owner_user_id: str = "user-1", org_id: str = "org-1",
                          linked_objective_id: str | None = None,
                          linked_key_result_id: str | None = None, **kw: Any) -> OKRInitiative:
        now = _now()
        extra = {k: v for k, v in kw.items() if k in OKRInitiative.__dataclass_fields__}
        init = OKRInitiative(initiative_id=_uid("init-"), title=title, owner_user_id=owner_user_id,
                             org_id=org_id, linked_objective_id=linked_objective_id,
                             linked_key_result_id=linked_key_result_id,
                             created_at=now, updated_at=now, **extra)
        self._conn.execute(
            """INSERT INTO okr_initiatives (initiative_id,title,description,owner_user_id,status,
               linked_objective_id,linked_key_result_id,external_system_ref,org_id,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (init.initiative_id, init.title, init.description, init.owner_user_id, init.status,
             init.linked_objective_id, init.linked_key_result_id, init.external_system_ref,
             init.org_id, init.created_at, init.updated_at))
        self._conn.commit()
        return init

    def list_initiatives(self, org_id: str = "org-1", objective_id: str | None = None,
                         kr_id: str | None = None) -> list[OKRInitiative]:
        clauses, params = ["org_id=?"], [org_id]
        if objective_id: clauses.append("linked_objective_id=?"); params.append(objective_id)
        if kr_id: clauses.append("linked_key_result_id=?"); params.append(kr_id)
        sql = f"SELECT * FROM okr_initiatives WHERE {' AND '.join(clauses)} ORDER BY created_at DESC"
        return [self._to_initiative(r) for r in self._conn.execute(sql, params).fetchall()]

    def update_initiative(self, initiative_id: str, **kw: Any) -> OKRInitiative | None:
        allowed = {"title","description","owner_user_id","status",
                   "linked_objective_id","linked_key_result_id","external_system_ref"}
        ups = {k: v for k, v in kw.items() if k in allowed}
        if not ups: return self._get_initiative(initiative_id)
        ups["updated_at"] = _now()
        sets = ", ".join(f"{k}=?" for k in ups)
        self._conn.execute(
            f"UPDATE okr_initiatives SET {sets} WHERE initiative_id=?", (*ups.values(), initiative_id))
        self._conn.commit()
        return self._get_initiative(initiative_id)

    def _get_initiative(self, initiative_id: str) -> OKRInitiative | None:
        row = self._conn.execute(
            "SELECT * FROM okr_initiatives WHERE initiative_id=?", (initiative_id,)).fetchone()
        return self._to_initiative(row) if row else None

    def _to_initiative(self, row: sqlite3.Row) -> OKRInitiative:
        d = dict(row)
        return OKRInitiative(**{k: d[k] for k in OKRInitiative.__dataclass_fields__ if k in d})

    # ── OKRCheckin ────────────────────────────────────────────────────────────

    def add_checkin(self, object_type: str, object_id: str, user_id: str = "user-1",
                    org_id: str = "org-1", checkin_date: str | None = None,
                    current_value: float | None = None, confidence: float | None = None,
                    blockers: str = "", decisions_needed: str = "",
                    narrative_update: str = "", next_steps: str = "",
                    parent_checkin_id: str | None = None) -> OKRCheckin:
        from datetime import date
        today = checkin_date or date.today().isoformat()
        score_snap: float | None = None
        if object_type == "key_result" and current_value is not None:
            self.update_key_result(object_id, current_value=current_value, last_checkin_at=_now())
            score_snap = self.compute_kr_score(object_id)
        if confidence is not None and object_type == "key_result":
            self._conn.execute(
                "UPDATE key_results SET confidence_current=?, updated_at=? WHERE kr_id=?",
                (confidence, _now(), object_id))
        # Migration: add parent_checkin_id column if it doesn't exist yet
        try:
            self._conn.execute("ALTER TABLE okr_checkins ADD COLUMN parent_checkin_id TEXT")
            self._conn.commit()
        except Exception:
            pass
        ci = OKRCheckin(checkin_id=_uid("ci-"), object_type=object_type, object_id=object_id,
                        user_id=user_id, org_id=org_id, checkin_date=today,
                        current_value=current_value, score_snapshot=score_snap,
                        confidence_snapshot=confidence, blockers=blockers,
                        decisions_needed=decisions_needed, narrative_update=narrative_update,
                        next_steps=next_steps, parent_checkin_id=parent_checkin_id,
                        created_at=_now())
        self._conn.execute(
            """INSERT INTO okr_checkins (checkin_id,object_type,object_id,user_id,checkin_date,
               current_value,score_snapshot,confidence_snapshot,status_snapshot,
               blockers,decisions_needed,narrative_update,next_steps,org_id,
               parent_checkin_id,created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (ci.checkin_id, ci.object_type, ci.object_id, ci.user_id, ci.checkin_date,
             ci.current_value, ci.score_snapshot, ci.confidence_snapshot, ci.status_snapshot,
             ci.blockers, ci.decisions_needed, ci.narrative_update, ci.next_steps,
             ci.org_id, ci.parent_checkin_id, ci.created_at))
        self._conn.commit()
        return ci

    def list_checkins(self, object_type: str, object_id: str, limit: int = 20) -> list[OKRCheckin]:
        rows = self._conn.execute(
            """SELECT * FROM okr_checkins WHERE object_type=? AND object_id=?
               ORDER BY created_at DESC LIMIT ?""", (object_type, object_id, limit)).fetchall()
        return [self._to_checkin(r) for r in rows]

    def list_overdue_checkins(self, org_id: str = "org-1", days: int = 10) -> list[dict]:
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = self._conn.execute(
            """SELECT * FROM key_results WHERE org_id=? AND status='active'
               AND (last_checkin_at IS NULL OR last_checkin_at < ?)
               ORDER BY last_checkin_at ASC""", (org_id, cutoff)).fetchall()
        return [dict(r) for r in rows]

    def _to_checkin(self, row: sqlite3.Row) -> OKRCheckin:
        d = dict(row)
        return OKRCheckin(**{k: d[k] for k in OKRCheckin.__dataclass_fields__ if k in d})

    # ── OKRDependency ─────────────────────────────────────────────────────────

    def create_dependency(self,
                          source_object_type: str = "", source_object_id: str = "",
                          target_object_type: str = "", target_object_id: str = "",
                          dependency_type: str = "contributes_to", severity: str = "medium",
                          org_id: str = "org-1",
                          # shorter aliases accepted from tool executor / tests
                          source_type: str = "", source_id: str = "",
                          target_type: str = "", target_id: str = "",
                          dep_type: str = "") -> OKRDependency:
        # Resolve short-form aliases
        sot = source_object_type or source_type
        soi = source_object_id or source_id
        tot = target_object_type or target_type
        toi = target_object_id or target_id
        dt = dep_type or dependency_type
        dep = OKRDependency(dependency_id=_uid("dep-"), source_object_type=sot,
                            source_object_id=soi, target_object_type=tot,
                            target_object_id=toi, dependency_type=dt,
                            severity=severity, org_id=org_id, created_at=_now())
        self._conn.execute(
            """INSERT INTO okr_dependencies (dependency_id,source_object_type,source_object_id,
               target_object_type,target_object_id,dependency_type,severity,org_id,created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (dep.dependency_id, dep.source_object_type, dep.source_object_id,
             dep.target_object_type, dep.target_object_id, dep.dependency_type,
             dep.severity, dep.org_id, dep.created_at))
        self._conn.commit()
        return dep

    def list_dependencies(self, object_type: str, object_id: str) -> list[OKRDependency]:
        rows = self._conn.execute(
            """SELECT * FROM okr_dependencies
               WHERE (source_object_type=? AND source_object_id=?)
                  OR (target_object_type=? AND target_object_id=?)
               ORDER BY created_at DESC""",
            (object_type, object_id, object_type, object_id)).fetchall()
        return [self._to_dep(r) for r in rows]

    def delete_dependency(self, dependency_id: str) -> bool:
        self._conn.execute("DELETE FROM okr_dependencies WHERE dependency_id=?", (dependency_id,))
        self._conn.commit()
        return True

    def _to_dep(self, row: sqlite3.Row) -> OKRDependency:
        d = dict(row)
        return OKRDependency(**{k: d[k] for k in OKRDependency.__dataclass_fields__ if k in d})

    # ── MeetingArtifact ───────────────────────────────────────────────────────

    def generate_meeting_artifact(self, meeting_type: str, org_id: str = "org-1",
                                  org_node_id: str | None = None,
                                  period_id: str | None = None) -> MeetingArtifact:
        agenda, pre_read = self._build_meeting_content(meeting_type, org_id, org_node_id, period_id)
        art = MeetingArtifact(artifact_id=_uid("mtg-"), meeting_type=meeting_type, org_id=org_id,
                              org_node_id=org_node_id, period_id=period_id,
                              agenda_markdown=agenda, pre_read_markdown=pre_read, generated_at=_now())
        self._conn.execute(
            """INSERT INTO meeting_artifacts (artifact_id,meeting_type,org_node_id,period_id,
               agenda_markdown,pre_read_markdown,decisions_markdown,followups_json,generated_at,org_id)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (art.artifact_id, art.meeting_type, art.org_node_id, art.period_id,
             art.agenda_markdown, art.pre_read_markdown, art.decisions_markdown,
             art.followups_json, art.generated_at, art.org_id))
        self._conn.commit()
        return art

    def list_meeting_artifacts(self, org_id: str = "org-1",
                                meeting_type: str | None = None) -> list[MeetingArtifact]:
        if meeting_type:
            rows = self._conn.execute(
                "SELECT * FROM meeting_artifacts WHERE org_id=? AND meeting_type=? ORDER BY generated_at DESC",
                (org_id, meeting_type)).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM meeting_artifacts WHERE org_id=? ORDER BY generated_at DESC",
                (org_id,)).fetchall()
        return [self._to_artifact(r) for r in rows]

    def _build_meeting_content(self, meeting_type: str, org_id: str,
                                org_node_id: str | None, period_id: str | None) -> tuple[str, str]:
        objectives = self.list_objectives(org_id=org_id, org_node_id=org_node_id, period_id=period_id)
        overdue = self.list_overdue_checkins(org_id)
        if meeting_type == "weekly_checkin":
            agenda = ("## Weekly OKR Check-in\n\n### Agenda\n1. Quick wins (5 min)\n"
                      "2. KR updates (20 min)\n3. Blockers (10 min)\n4. Actions (5 min)\n\n"
                      f"### {len(overdue)} KRs missing updates\n")
            for r in overdue[:5]:
                agenda += f"- `{r['kr_id']}`: {r['title']}\n"
            pre_read = "## Current KR Status\n\n"
            for obj in objectives[:5]:
                pre_read += f"**{obj.title}** ({obj.objective_type}) — {obj.health_current}\n"
        elif meeting_type == "portfolio_review":
            at_risk = [o for o in objectives if o.health_current in ("red","yellow")]
            agenda = ("## Monthly Portfolio Review\n\n### Agenda\n1. Portfolio health (10 min)\n"
                      "2. At-risk objectives (20 min)\n3. Dependencies (10 min)\n"
                      "4. Decisions (5 min)\n5. Actions (5 min)\n\n"
                      f"### At-risk objectives ({len(at_risk)} total)\n")
            for obj in at_risk[:10]:
                agenda += f"- **{obj.title}** — {obj.health_current} — {obj.owner_user_id}\n"
            pre_read = f"## Portfolio Snapshot\nTotal: {len(objectives)} | At risk: {len(at_risk)}\n"
        elif meeting_type == "quarterly_review":
            committed = [o for o in objectives if o.objective_type == "committed"]
            agenda = ("## Quarterly OKR Review\n\n### Agenda\n1. Final scores (20 min)\n"
                      "2. Committed misses (20 min)\n3. Aspirational review (10 min)\n"
                      "4. Carry-forward decisions (15 min)\n5. Next quarter preview (10 min)\n\n"
                      f"### Committed objectives: {len(committed)}\n")
            for obj in committed[:10]:
                score = self.compute_objective_score(obj.objective_id)
                agenda += f"- {obj.title}: {score:.0%}\n"
            pre_read = ("## Retrospective Prompts\n\nFor each committed miss:\n"
                        "- What did we commit to?\n- What happened?\n- What will we change?\n")
        else:  # planning_workshop
            agenda = ("## OKR Planning Workshop\n\n### Agenda\n1. Last quarter review (15 min)\n"
                      "2. Strategy alignment (15 min)\n3. Draft objectives (30 min)\n"
                      "4. Draft KRs (30 min)\n5. Alignment review (15 min)\n6. Publish (15 min)\n")
            pre_read = ("## OKR Quality Rules\n- Max 5 objectives per team per quarter\n"
                        "- Max 5 KRs per objective\n- Every KR must have a measurable target\n"
                        "- KRs describe outcomes, not activities\n- Committed OKRs need escalation path\n")
        return agenda, pre_read

    def _to_artifact(self, row: sqlite3.Row) -> MeetingArtifact:
        d = dict(row)
        return MeetingArtifact(**{k: d[k] for k in MeetingArtifact.__dataclass_fields__ if k in d})

    # ── Alignment graph ───────────────────────────────────────────────────────

    def get_alignment_graph(self, org_id: str = "org-1", period_id: str | None = None) -> dict:
        objectives = self.list_objectives(org_id=org_id, period_id=period_id)
        nodes, edges = [], []
        for obj in objectives:
            nodes.append({"id": obj.objective_id, "label": obj.title[:50],
                          "type": "objective", "objective_type": obj.objective_type,
                          "health": obj.health_current, "org_node_id": obj.org_node_id,
                          "score": self.compute_objective_score(obj.objective_id)})
            if obj.parent_objective_id:
                edges.append({"source": obj.parent_objective_id, "target": obj.objective_id,
                              "edge_type": "parent_child", "alignment_mode": obj.alignment_mode})
        for r in self._conn.execute("SELECT * FROM okr_dependencies WHERE org_id=?", (org_id,)).fetchall():
            edges.append({"source": r["source_object_id"], "target": r["target_object_id"],
                          "edge_type": r["dependency_type"], "severity": r["severity"]})
        return {"nodes": nodes, "edges": edges}

    # ── Dashboard aggregations ─────────────────────────────────────────────────

    def executive_dashboard(self, org_id: str = "org-1", period_id: str | None = None) -> dict:
        objectives = self.list_objectives(org_id=org_id, period_id=period_id, status="active")
        committed = [o for o in objectives if o.objective_type == "committed"]
        at_risk = [o for o in objectives if o.health_current in ("red","yellow")]
        scores = [self.compute_objective_score(o.objective_id) for o in objectives]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        return {
            "total_objectives": len(objectives), "committed_count": len(committed),
            "at_risk_count": len(at_risk), "avg_score": round(avg_score, 3),
            "committed_at_risk": [asdict(o) for o in committed if o.health_current == "red"],
            "health_breakdown": {h: sum(1 for o in objectives if o.health_current == h)
                                 for h in ("green","yellow","red")},
            "objectives": [{**asdict(o), "score": self.compute_objective_score(o.objective_id)}
                           for o in objectives],
        }

    def portfolio_dashboard(self, org_node_id: str, period_id: str | None = None) -> dict:
        objectives = self.list_objectives(org_node_id=org_node_id, period_id=period_id)
        return {
            "org_node_id": org_node_id,
            "objectives": [{**asdict(o), "score": self.compute_objective_score(o.objective_id),
                            "key_results": [asdict(kr) for kr in self.list_key_results(o.objective_id)]}
                           for o in objectives],
            "overdue_checkins": self.list_overdue_checkins(org_id="org-1")[:20],
            "health_breakdown": {h: sum(1 for o in objectives if o.health_current == h)
                                 for h in ("green","yellow","red")},
        }

    def team_dashboard(self, org_node_id: str, period_id: str | None = None) -> dict:
        objectives = self.list_objectives(org_node_id=org_node_id, period_id=period_id, status="active")
        initiatives = []
        for obj in objectives:
            initiatives.extend(self.list_initiatives(org_id="org-1", objective_id=obj.objective_id))
        return {
            "org_node_id": org_node_id,
            "objectives": [{**asdict(o), "score": self.compute_objective_score(o.objective_id),
                            "key_results": [asdict(kr) for kr in self.list_key_results(o.objective_id)]}
                           for o in objectives],
            "pending_checkins": self.list_overdue_checkins(org_id="org-1", days=7)[:10],
            "initiatives": [asdict(i) for i in initiatives[:20]],
        }

    def analytics_dashboard(self, org_id: str = "org-1") -> dict:
        kpis = self.list_kpis(org_id)
        all_krs = self._conn.execute(
            "SELECT * FROM key_results WHERE org_id=? AND status!='archived'", (org_id,)).fetchall()
        metric_krs = [r for r in all_krs if dict(r)["kr_type"] == "metric"]
        missing_baseline = [r for r in metric_krs if dict(r)["baseline_value"] is None]
        linked_ids = {r["key_result_id"] for r in
                      self._conn.execute("SELECT DISTINCT key_result_id FROM kr_kpi_links").fetchall()}
        coverage_pct = (len([r for r in metric_krs if dict(r)["kr_id"] in linked_ids])
                        / max(len(metric_krs), 1)) * 100
        return {
            "kpi_count": len(kpis), "kpis": [asdict(k) for k in kpis],
            "kr_count": len(all_krs), "metric_kr_count": len(metric_krs),
            "kpi_coverage_pct": round(coverage_pct, 1),
            "missing_baseline_count": len(missing_baseline),
            "overdue_checkins": self.list_overdue_checkins(org_id, days=14),
        }

    # ── Forecasting ───────────────────────────────────────────────────────────

    def forecast_kr_score(self, kr_id: str) -> dict:
        rows = self._conn.execute(
            """SELECT score_snapshot, created_at FROM okr_checkins
               WHERE object_type='key_result' AND object_id=? AND score_snapshot IS NOT NULL
               ORDER BY created_at DESC LIMIT 4""", (kr_id,)).fetchall()
        if len(rows) < 2:
            return {"projected_score": None, "trend": "insufficient_data", "data_points": len(rows)}
        scores = [r["score_snapshot"] for r in rows]
        velocity = (scores[0] - scores[-1]) / (len(scores) - 1)
        projected = _clamp(scores[0] + velocity * 4)
        trend = "improving" if velocity > 0.01 else "declining" if velocity < -0.01 else "stable"
        return {"projected_score": round(projected, 3), "trend": trend,
                "velocity": round(velocity, 3), "data_points": len(scores)}

    def detect_bottleneck_dependencies(self, org_id: str = "org-1") -> list[dict]:
        rows = self._conn.execute(
            """SELECT target_object_id, COUNT(*) as blocker_count FROM okr_dependencies
               WHERE org_id=? AND dependency_type='blocked_by'
               GROUP BY target_object_id HAVING COUNT(*) >= 2
               ORDER BY blocker_count DESC""", (org_id,)).fetchall()
        result = []
        for r in rows:
            obj = self.get_objective(r["target_object_id"])
            if obj:
                result.append({"objective_id": obj.objective_id, "title": obj.title,
                               "blocker_count": r["blocker_count"], "health": obj.health_current})
        return result

    def generate_confidence_matrix(self, org_id: str = "org-1", period_id: str | None = None) -> list[dict]:
        objectives = self.list_objectives(org_id=org_id, period_id=period_id, status="active")
        return [{"objective_id": o.objective_id, "title": o.title[:40],
                 "score": self.compute_objective_score(o.objective_id),
                 "confidence": o.confidence_current, "objective_type": o.objective_type,
                 "health": o.health_current} for o in objectives]

    # ── Summary ───────────────────────────────────────────────────────────────

    def okr_summary(self, org_id: str = "org-1", period_id: str | None = None) -> dict:
        objectives = self.list_objectives(org_id=org_id, period_id=period_id)
        total = len(objectives)
        avg_conf = sum(o.confidence_current for o in objectives) / max(total, 1)
        return {
            "total": total, "avg_confidence": round(avg_conf, 3),
            "committed": sum(1 for o in objectives if o.objective_type == "committed"),
            "aspirational": sum(1 for o in objectives if o.objective_type == "aspirational"),
            "by_health": {h: sum(1 for o in objectives if o.health_current == h)
                          for h in ("green","yellow","red")},
        }

    # ── Missing methods (added post-initial write) ────────────────────────────

    def get_key_result(self, kr_id: str) -> KeyResult | None:
        row = self._conn.execute("SELECT * FROM key_results WHERE kr_id=?", (kr_id,)).fetchone()
        return self._to_kr(row) if row else None

    def get_objective_hierarchy(self, objective_id: str) -> dict:
        """Return a nested dict of an objective and all its descendants."""
        def _build(obj_id: str) -> dict:
            obj = self.get_objective(obj_id)
            if not obj:
                return {}
            node = {**asdict(obj), "children": []}
            rows = self._conn.execute(
                "SELECT objective_id FROM objectives WHERE parent_objective_id=?",
                (obj_id,),
            ).fetchall()
            for r in rows:
                node["children"].append(_build(r["objective_id"]))
            return node

        return _build(objective_id)

    def get_kpi_trend(self, kpi_id: str, limit: int = 30) -> dict:
        """Return recent value history for a KPI (stub — values tracked via record_kpi_value)."""
        kpi = self.get_kpi(kpi_id)
        if not kpi:
            return {"kpi_id": kpi_id, "data_points": []}
        # In a full implementation this would query a kpi_values history table.
        # For now return current value as single data point.
        return {
            "kpi_id": kpi_id,
            "name": kpi.name,
            "unit": kpi.unit,
            "current_value": kpi.current_value,
            "target_band_low": kpi.target_band_low,
            "target_band_high": kpi.target_band_high,
            "data_points": (
                [{"value": kpi.current_value, "recorded_at": kpi.updated_at}]
                if kpi.current_value is not None else []
            ),
        }

    def get_kpi(self, kpi_id: str) -> OKRKPI | None:
        row = self._conn.execute("SELECT * FROM okr_kpis WHERE kpi_id=?", (kpi_id,)).fetchone()
        return self._to_kpi(row) if row else None

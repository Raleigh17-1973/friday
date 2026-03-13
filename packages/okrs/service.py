from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4
from datetime import datetime


@dataclass
class Objective:
    obj_id: str
    org_id: str
    workspace_id: str | None
    title: str
    description: str
    owner: str
    collaborators: list[str]
    parent_id: str | None          # For hierarchy: company -> team -> individual
    level: str                     # "company" | "team" | "individual"
    period: str                    # e.g. "2026-Q1"
    status: str                    # "active" | "on_track" | "at_risk" | "behind" | "completed" | "cancelled"
    confidence: float              # 0.0-1.0
    rationale: str                 # Why this matters
    progress: float                # Auto-computed from key results, 0.0-1.0
    linked_initiatives: list[str]  # initiative IDs
    linked_docs: list[str]         # file IDs
    created_at: str
    updated_at: str


@dataclass
class KeyResult:
    kr_id: str
    objective_id: str
    title: str
    metric_type: str               # "percentage" | "number" | "currency" | "boolean"
    baseline: float
    current_value: float
    target_value: float
    unit: str
    owner: str
    data_source: str
    update_cadence: str            # "weekly" | "monthly" | "quarterly"
    status: str                    # "active" | "on_track" | "at_risk" | "behind" | "completed"
    confidence: float              # 0.0-1.0
    due_date: str
    notes: str                     # Latest update/notes
    risk_flags: list[str]
    org_id: str
    created_at: str
    updated_at: str

    @property
    def progress(self) -> float:
        if self.target_value == self.baseline:
            return 1.0 if self.current_value >= self.target_value else 0.0
        span = self.target_value - self.baseline
        if span == 0:
            return 0.0
        return max(0.0, min(1.0, (self.current_value - self.baseline) / span))


@dataclass
class Initiative:
    initiative_id: str
    title: str
    owner: str
    objective_id: str
    kr_id: str | None
    status: str                    # "not_started" | "in_progress" | "done" | "blocked"
    due_date: str
    description: str
    org_id: str
    workspace_id: str | None
    created_at: str


@dataclass
class CheckIn:
    checkin_id: str
    objective_id: str
    author: str
    confidence: float
    status: str
    notes: str
    created_at: str
    org_id: str


class OKRService:
    """Full OKR lifecycle: objectives, key results, initiatives, check-ins."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or Path("data/okrs.db")
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS objectives (
                    obj_id TEXT PRIMARY KEY,
                    org_id TEXT NOT NULL,
                    workspace_id TEXT,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    owner TEXT NOT NULL DEFAULT '',
                    collaborators TEXT NOT NULL DEFAULT '[]',
                    parent_id TEXT,
                    level TEXT NOT NULL DEFAULT 'team',
                    period TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    confidence REAL NOT NULL DEFAULT 0.7,
                    rationale TEXT NOT NULL DEFAULT '',
                    progress REAL NOT NULL DEFAULT 0.0,
                    linked_initiatives TEXT NOT NULL DEFAULT '[]',
                    linked_docs TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS key_results (
                    kr_id TEXT PRIMARY KEY,
                    objective_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    metric_type TEXT NOT NULL DEFAULT 'number',
                    baseline REAL NOT NULL DEFAULT 0.0,
                    current_value REAL NOT NULL DEFAULT 0.0,
                    target_value REAL NOT NULL DEFAULT 1.0,
                    unit TEXT NOT NULL DEFAULT '',
                    owner TEXT NOT NULL DEFAULT '',
                    data_source TEXT NOT NULL DEFAULT '',
                    update_cadence TEXT NOT NULL DEFAULT 'monthly',
                    status TEXT NOT NULL DEFAULT 'active',
                    confidence REAL NOT NULL DEFAULT 0.7,
                    due_date TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    risk_flags TEXT NOT NULL DEFAULT '[]',
                    org_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS initiatives (
                    initiative_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    owner TEXT NOT NULL DEFAULT '',
                    objective_id TEXT NOT NULL,
                    kr_id TEXT,
                    status TEXT NOT NULL DEFAULT 'not_started',
                    due_date TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    org_id TEXT NOT NULL,
                    workspace_id TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS checkins (
                    checkin_id TEXT PRIMARY KEY,
                    objective_id TEXT NOT NULL,
                    author TEXT NOT NULL DEFAULT 'user-1',
                    confidence REAL NOT NULL DEFAULT 0.7,
                    status TEXT NOT NULL DEFAULT 'on_track',
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    org_id TEXT NOT NULL
                );
            """)

    # ---- Objectives ----
    def create_objective(
        self,
        title: str,
        period: str,
        org_id: str = "org-1",
        description: str = "",
        owner: str = "",
        level: str = "team",
        parent_id: str | None = None,
        workspace_id: str | None = None,
        collaborators: list[str] | None = None,
        rationale: str = "",
        confidence: float = 0.7,
    ) -> Objective:
        now = datetime.utcnow().isoformat() + "Z"
        obj = Objective(
            obj_id=f"obj_{uuid4().hex[:12]}",
            org_id=org_id, workspace_id=workspace_id,
            title=title, description=description, owner=owner,
            collaborators=collaborators or [], parent_id=parent_id,
            level=level, period=period, status="active",
            confidence=confidence, rationale=rationale,
            progress=0.0, linked_initiatives=[], linked_docs=[],
            created_at=now, updated_at=now,
        )
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """INSERT INTO objectives VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (obj.obj_id, obj.org_id, obj.workspace_id, obj.title, obj.description,
                 obj.owner, json.dumps(obj.collaborators), obj.parent_id, obj.level,
                 obj.period, obj.status, obj.confidence, obj.rationale, obj.progress,
                 json.dumps(obj.linked_initiatives), json.dumps(obj.linked_docs),
                 obj.created_at, obj.updated_at)
            )
        return obj

    def get_objective(self, obj_id: str) -> Objective | None:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM objectives WHERE obj_id = ?", (obj_id,)).fetchone()
        return self._row_to_objective(row) if row else None

    def update_objective(self, obj_id: str, **kwargs: Any) -> Objective | None:
        allowed = {"title", "description", "owner", "collaborators", "status",
                   "confidence", "rationale", "level", "workspace_id", "parent_id"}
        updates = {}
        for k, v in kwargs.items():
            if k not in allowed:
                continue
            if k in ("collaborators",) and isinstance(v, list):
                updates[k] = json.dumps(v)
            else:
                updates[k] = v
        if not updates:
            return self.get_objective(obj_id)
        updates["updated_at"] = datetime.utcnow().isoformat() + "Z"
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [obj_id]
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(f"UPDATE objectives SET {set_clause} WHERE obj_id = ?", values)
        return self.get_objective(obj_id)

    def list_objectives(
        self,
        org_id: str = "org-1",
        workspace_id: str | None = None,
        parent_id: str | None = "__root__",  # __root__ means top-level only
        level: str | None = None,
        period: str | None = None,
        status: str | None = None,
    ) -> list[Objective]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            q = "SELECT * FROM objectives WHERE org_id = ?"
            params: list[Any] = [org_id]
            if workspace_id is not None:
                q += " AND workspace_id = ?"
                params.append(workspace_id)
            if parent_id == "__root__":
                q += " AND parent_id IS NULL"
            elif parent_id is not None:
                q += " AND parent_id = ?"
                params.append(parent_id)
            if level:
                q += " AND level = ?"
                params.append(level)
            if period:
                q += " AND period = ?"
                params.append(period)
            if status:
                q += " AND status = ?"
                params.append(status)
            q += " ORDER BY created_at"
            rows = conn.execute(q, params).fetchall()
        return [self._row_to_objective(r) for r in rows]

    def list_all_objectives(self, org_id: str = "org-1") -> list[Objective]:
        """All objectives regardless of parent."""
        return self.list_objectives(org_id=org_id, parent_id=None)

    def get_children(self, obj_id: str, org_id: str = "org-1") -> list[Objective]:
        return self.list_objectives(org_id=org_id, parent_id=obj_id)

    def get_objective_with_details(self, obj_id: str) -> dict[str, Any]:
        obj = self.get_objective(obj_id)
        if not obj:
            return {}
        krs = self.list_key_results(obj_id)
        initiatives = self.list_initiatives(objective_id=obj_id)
        children = self.get_children(obj_id, obj.org_id)
        checkins = self.list_checkins(obj_id)
        parent = self.get_objective(obj.parent_id) if obj.parent_id else None
        from dataclasses import asdict
        return {
            "objective": asdict(obj),
            "key_results": [asdict(kr) for kr in krs],
            "initiatives": [asdict(i) for i in initiatives],
            "children": [asdict(c) for c in children],
            "checkins": [asdict(c) for c in checkins],
            "parent": asdict(parent) if parent else None,
        }

    def _recompute_progress(self, obj_id: str) -> float:
        krs = self.list_key_results(obj_id)
        if not krs:
            return 0.0
        avg = sum(kr.progress for kr in krs) / len(krs)
        now = datetime.utcnow().isoformat() + "Z"
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "UPDATE objectives SET progress = ?, updated_at = ? WHERE obj_id = ?",
                (avg, now, obj_id)
            )
        return avg

    # ---- Key Results ----
    def create_key_result(
        self,
        objective_id: str,
        title: str,
        target_value: float,
        org_id: str = "org-1",
        unit: str = "",
        baseline: float = 0.0,
        owner: str = "",
        metric_type: str = "number",
        data_source: str = "",
        update_cadence: str = "monthly",
        due_date: str = "",
        confidence: float = 0.7,
    ) -> KeyResult:
        now = datetime.utcnow().isoformat() + "Z"
        kr = KeyResult(
            kr_id=f"kr_{uuid4().hex[:12]}",
            objective_id=objective_id, title=title,
            metric_type=metric_type, baseline=baseline,
            current_value=baseline, target_value=target_value,
            unit=unit, owner=owner, data_source=data_source,
            update_cadence=update_cadence, status="active",
            confidence=confidence, due_date=due_date,
            notes="", risk_flags=[], org_id=org_id,
            created_at=now, updated_at=now,
        )
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """INSERT INTO key_results VALUES
                   (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (kr.kr_id, kr.objective_id, kr.title, kr.metric_type,
                 kr.baseline, kr.current_value, kr.target_value,
                 kr.unit, kr.owner, kr.data_source, kr.update_cadence,
                 kr.status, kr.confidence, kr.due_date, kr.notes,
                 json.dumps(kr.risk_flags), kr.org_id, kr.created_at, kr.updated_at)
            )
        return kr

    def update_key_result(self, kr_id: str, **kwargs: Any) -> KeyResult | None:
        allowed = {"current_value", "target_value", "baseline", "status", "confidence",
                   "notes", "due_date", "owner", "data_source", "risk_flags", "title"}
        updates = {}
        for k, v in kwargs.items():
            if k not in allowed:
                continue
            if k == "risk_flags" and isinstance(v, list):
                updates[k] = json.dumps(v)
            else:
                updates[k] = v
        if not updates:
            return self._get_kr(kr_id)
        updates["updated_at"] = datetime.utcnow().isoformat() + "Z"
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [kr_id]
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(f"UPDATE key_results SET {set_clause} WHERE kr_id = ?", values)
        kr = self._get_kr(kr_id)
        if kr:
            self._recompute_progress(kr.objective_id)
        return kr

    def list_key_results(self, objective_id: str) -> list[KeyResult]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM key_results WHERE objective_id = ? ORDER BY created_at",
                (objective_id,)
            ).fetchall()
        return [self._row_to_kr(r) for r in rows]

    def _get_kr(self, kr_id: str) -> KeyResult | None:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM key_results WHERE kr_id = ?", (kr_id,)).fetchone()
        return self._row_to_kr(row) if row else None

    # ---- Initiatives ----
    def create_initiative(
        self,
        title: str,
        objective_id: str,
        org_id: str = "org-1",
        owner: str = "",
        kr_id: str | None = None,
        description: str = "",
        due_date: str = "",
        workspace_id: str | None = None,
    ) -> Initiative:
        now = datetime.utcnow().isoformat() + "Z"
        init = Initiative(
            initiative_id=f"init_{uuid4().hex[:12]}",
            title=title, owner=owner, objective_id=objective_id,
            kr_id=kr_id, status="not_started", due_date=due_date,
            description=description, org_id=org_id,
            workspace_id=workspace_id, created_at=now,
        )
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO initiatives VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (init.initiative_id, init.title, init.owner, init.objective_id,
                 init.kr_id, init.status, init.due_date, init.description,
                 init.org_id, init.workspace_id, init.created_at)
            )
        return init

    def list_initiatives(self, objective_id: str | None = None, org_id: str = "org-1") -> list[Initiative]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            if objective_id:
                rows = conn.execute(
                    "SELECT * FROM initiatives WHERE objective_id = ? ORDER BY created_at",
                    (objective_id,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM initiatives WHERE org_id = ? ORDER BY created_at",
                    (org_id,)
                ).fetchall()
        return [Initiative(
            initiative_id=r["initiative_id"], title=r["title"], owner=r["owner"],
            objective_id=r["objective_id"], kr_id=r["kr_id"], status=r["status"],
            due_date=r["due_date"], description=r["description"], org_id=r["org_id"],
            workspace_id=r["workspace_id"], created_at=r["created_at"],
        ) for r in rows]

    def update_initiative(self, initiative_id: str, status: str | None = None, **kwargs: Any) -> None:
        updates: dict[str, Any] = {}
        if status:
            updates["status"] = status
        for k, v in kwargs.items():
            if k in {"title", "owner", "due_date", "description"}:
                updates[k] = v
        if not updates:
            return
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [initiative_id]
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(f"UPDATE initiatives SET {set_clause} WHERE initiative_id = ?", values)

    # ---- Check-ins ----
    def add_checkin(
        self, objective_id: str, notes: str,
        confidence: float = 0.7, status: str = "on_track",
        author: str = "user-1", org_id: str = "org-1",
    ) -> CheckIn:
        now = datetime.utcnow().isoformat() + "Z"
        checkin = CheckIn(
            checkin_id=f"ci_{uuid4().hex[:12]}",
            objective_id=objective_id, author=author,
            confidence=confidence, status=status,
            notes=notes, created_at=now, org_id=org_id,
        )
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO checkins VALUES (?,?,?,?,?,?,?,?)",
                (checkin.checkin_id, checkin.objective_id, checkin.author,
                 checkin.confidence, checkin.status, checkin.notes,
                 checkin.created_at, checkin.org_id)
            )
        # Update objective confidence and status from check-in
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "UPDATE objectives SET confidence = ?, status = ?, updated_at = ? WHERE obj_id = ?",
                (confidence, status, now, objective_id)
            )
        return checkin

    def list_checkins(self, objective_id: str) -> list[CheckIn]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM checkins WHERE objective_id = ? ORDER BY created_at DESC LIMIT 10",
                (objective_id,)
            ).fetchall()
        return [CheckIn(
            checkin_id=r["checkin_id"], objective_id=r["objective_id"],
            author=r["author"], confidence=r["confidence"], status=r["status"],
            notes=r["notes"], created_at=r["created_at"], org_id=r["org_id"],
        ) for r in rows]

    # ---- Summary ----
    def okr_summary(self, org_id: str = "org-1") -> dict[str, Any]:
        objectives = self.list_all_objectives(org_id)
        by_status: dict[str, int] = {}
        for obj in objectives:
            by_status[obj.status] = by_status.get(obj.status, 0) + 1
        return {
            "total": len(objectives),
            "by_status": by_status,
            "on_track": by_status.get("on_track", 0),
            "at_risk": by_status.get("at_risk", 0),
            "behind": by_status.get("behind", 0),
            "completed": by_status.get("completed", 0),
            "avg_confidence": sum(o.confidence for o in objectives) / max(len(objectives), 1),
        }

    # ---- Helpers ----
    def _row_to_objective(self, row) -> Objective:
        return Objective(
            obj_id=row["obj_id"], org_id=row["org_id"],
            workspace_id=row["workspace_id"], title=row["title"],
            description=row["description"], owner=row["owner"],
            collaborators=json.loads(row["collaborators"] or "[]"),
            parent_id=row["parent_id"], level=row["level"],
            period=row["period"], status=row["status"],
            confidence=row["confidence"], rationale=row["rationale"],
            progress=row["progress"],
            linked_initiatives=json.loads(row["linked_initiatives"] or "[]"),
            linked_docs=json.loads(row["linked_docs"] or "[]"),
            created_at=row["created_at"], updated_at=row["updated_at"],
        )

    def _row_to_kr(self, row) -> KeyResult:
        return KeyResult(
            kr_id=row["kr_id"], objective_id=row["objective_id"],
            title=row["title"], metric_type=row["metric_type"],
            baseline=row["baseline"], current_value=row["current_value"],
            target_value=row["target_value"], unit=row["unit"],
            owner=row["owner"], data_source=row["data_source"],
            update_cadence=row["update_cadence"], status=row["status"],
            confidence=row["confidence"], due_date=row["due_date"],
            notes=row["notes"],
            risk_flags=json.loads(row["risk_flags"] or "[]"),
            org_id=row["org_id"],
            created_at=row["created_at"], updated_at=row["updated_at"],
        )

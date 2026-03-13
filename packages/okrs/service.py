from __future__ import annotations

import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from packages.common.models import utc_now_iso


@dataclass
class Objective:
    obj_id: str
    org_id: str
    name: str
    description: str
    period: str  # e.g. "2026-Q1"
    status: str = "active"  # active, completed, cancelled
    progress: float = 0.0  # 0.0 - 1.0, auto-computed from key results
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self):
        return asdict(self)


@dataclass
class KeyResult:
    kr_id: str
    objective_id: str
    name: str
    target: float
    current: float = 0.0
    unit: str = "count"
    status: str = "active"  # active, completed, cancelled
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self):
        return asdict(self)

    @property
    def progress(self) -> float:
        if self.target == 0:
            return 0.0
        return min(self.current / self.target, 1.0)


class OKRService:
    def __init__(self, db_path: Path | None = None):
        path = str(db_path) if db_path else ":memory:"
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS objectives (
            obj_id TEXT PRIMARY KEY, org_id TEXT NOT NULL, name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '', period TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active', progress REAL NOT NULL DEFAULT 0.0,
            created_at TEXT NOT NULL)"""
        )
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS key_results (
            kr_id TEXT PRIMARY KEY, objective_id TEXT NOT NULL, name TEXT NOT NULL,
            target REAL NOT NULL, current REAL NOT NULL DEFAULT 0.0,
            unit TEXT NOT NULL DEFAULT 'count', status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL,
            FOREIGN KEY (objective_id) REFERENCES objectives(obj_id))"""
        )
        self._conn.commit()

    def create_objective(
        self,
        name: str,
        period: str,
        org_id: str = "org-1",
        description: str = "",
    ) -> Objective:
        obj = Objective(
            obj_id=f"obj_{uuid.uuid4().hex[:10]}",
            org_id=org_id,
            name=name,
            description=description,
            period=period,
        )
        self._conn.execute(
            "INSERT INTO objectives (obj_id, org_id, name, description, period, status, progress, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (obj.obj_id, obj.org_id, obj.name, obj.description, obj.period, obj.status, obj.progress, obj.created_at),
        )
        self._conn.commit()
        return obj

    def create_key_result(
        self,
        objective_id: str,
        name: str,
        target: float,
        unit: str = "count",
    ) -> KeyResult:
        kr = KeyResult(
            kr_id=f"kr_{uuid.uuid4().hex[:10]}",
            objective_id=objective_id,
            name=name,
            target=target,
            unit=unit,
        )
        self._conn.execute(
            "INSERT INTO key_results (kr_id, objective_id, name, target, current, unit, status, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (kr.kr_id, kr.objective_id, kr.name, kr.target, kr.current, kr.unit, kr.status, kr.created_at),
        )
        self._conn.commit()
        return kr

    def update_key_result_progress(self, kr_id: str, current: float) -> KeyResult | None:
        self._conn.execute(
            "UPDATE key_results SET current = ? WHERE kr_id = ?", (current, kr_id)
        )
        self._conn.commit()
        kr = self._get_key_result(kr_id)
        if kr:
            self._recompute_objective_progress(kr.objective_id)
        return kr

    def list_objectives(self, org_id: str = "org-1") -> list[Objective]:
        rows = self._conn.execute(
            "SELECT obj_id, org_id, name, description, period, status, progress, created_at FROM objectives WHERE org_id = ?",
            (org_id,),
        ).fetchall()
        return [
            Objective(
                obj_id=r[0], org_id=r[1], name=r[2], description=r[3],
                period=r[4], status=r[5], progress=r[6], created_at=r[7],
            )
            for r in rows
        ]

    def get_objective_with_key_results(self, obj_id: str) -> dict[str, Any] | None:
        r = self._conn.execute(
            "SELECT obj_id, org_id, name, description, period, status, progress, created_at FROM objectives WHERE obj_id = ?",
            (obj_id,),
        ).fetchone()
        if r is None:
            return None
        obj = Objective(
            obj_id=r[0], org_id=r[1], name=r[2], description=r[3],
            period=r[4], status=r[5], progress=r[6], created_at=r[7],
        )
        krs = self._list_key_results(obj_id)
        return {"objective": obj.to_dict(), "key_results": [kr.to_dict() for kr in krs]}

    def _get_key_result(self, kr_id: str) -> KeyResult | None:
        r = self._conn.execute(
            "SELECT kr_id, objective_id, name, target, current, unit, status, created_at FROM key_results WHERE kr_id = ?",
            (kr_id,),
        ).fetchone()
        if r is None:
            return None
        return KeyResult(
            kr_id=r[0], objective_id=r[1], name=r[2], target=r[3],
            current=r[4], unit=r[5], status=r[6], created_at=r[7],
        )

    def _list_key_results(self, objective_id: str) -> list[KeyResult]:
        rows = self._conn.execute(
            "SELECT kr_id, objective_id, name, target, current, unit, status, created_at FROM key_results WHERE objective_id = ?",
            (objective_id,),
        ).fetchall()
        return [
            KeyResult(
                kr_id=r[0], objective_id=r[1], name=r[2], target=r[3],
                current=r[4], unit=r[5], status=r[6], created_at=r[7],
            )
            for r in rows
        ]

    def _recompute_objective_progress(self, objective_id: str):
        krs = self._list_key_results(objective_id)
        if not krs:
            return
        avg_progress = sum(kr.progress for kr in krs) / len(krs)
        self._conn.execute(
            "UPDATE objectives SET progress = ? WHERE obj_id = ?",
            (avg_progress, objective_id),
        )
        self._conn.commit()

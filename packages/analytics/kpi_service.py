from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from packages.common.models import utc_now_iso


@dataclass
class KPIDefinition:
    kpi_id: str
    org_id: str
    name: str
    unit: str  # "$", "%", "count", "hours", etc.
    target: float | None = None
    frequency: str = "monthly"  # daily, weekly, monthly, quarterly
    data_source: str = "manual"  # manual, jira, salesforce, etc.
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self):
        return asdict(self)


@dataclass
class KPIDataPoint:
    kpi_id: str
    value: float
    recorded_at: str = field(default_factory=utc_now_iso)
    source: str = "manual"

    def to_dict(self):
        return asdict(self)


class KPIService:
    def __init__(self, db_path: Path | None = None):
        path = str(db_path) if db_path else ":memory:"
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS kpi_definitions (
            kpi_id TEXT PRIMARY KEY, org_id TEXT NOT NULL, name TEXT NOT NULL,
            unit TEXT NOT NULL, target REAL, frequency TEXT NOT NULL DEFAULT 'monthly',
            data_source TEXT NOT NULL DEFAULT 'manual', created_at TEXT NOT NULL)"""
        )
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS kpi_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT, kpi_id TEXT NOT NULL,
            value REAL NOT NULL, recorded_at TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'manual',
            FOREIGN KEY (kpi_id) REFERENCES kpi_definitions(kpi_id))"""
        )
        self._conn.commit()

    def create_kpi(
        self,
        name: str,
        unit: str,
        org_id: str = "org-1",
        target: float | None = None,
        frequency: str = "monthly",
        data_source: str = "manual",
    ) -> KPIDefinition:
        kpi = KPIDefinition(
            kpi_id=f"kpi_{uuid.uuid4().hex[:10]}",
            org_id=org_id,
            name=name,
            unit=unit,
            target=target,
            frequency=frequency,
            data_source=data_source,
        )
        self._conn.execute(
            "INSERT INTO kpi_definitions (kpi_id, org_id, name, unit, target, frequency, data_source, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (
                kpi.kpi_id,
                kpi.org_id,
                kpi.name,
                kpi.unit,
                kpi.target,
                kpi.frequency,
                kpi.data_source,
                kpi.created_at,
            ),
        )
        self._conn.commit()
        return kpi

    def record_data_point(
        self, kpi_id: str, value: float, source: str = "manual"
    ) -> KPIDataPoint:
        dp = KPIDataPoint(kpi_id=kpi_id, value=value, source=source)
        self._conn.execute(
            "INSERT INTO kpi_data (kpi_id, value, recorded_at, source) VALUES (?,?,?,?)",
            (dp.kpi_id, dp.value, dp.recorded_at, dp.source),
        )
        self._conn.commit()
        return dp

    def get_trend(self, kpi_id: str, limit: int = 30) -> list[KPIDataPoint]:
        rows = self._conn.execute(
            "SELECT kpi_id, value, recorded_at, source FROM kpi_data WHERE kpi_id = ? ORDER BY recorded_at DESC LIMIT ?",
            (kpi_id, limit),
        ).fetchall()
        return [
            KPIDataPoint(kpi_id=r[0], value=r[1], recorded_at=r[2], source=r[3])
            for r in rows
        ]

    def list_kpis(self, org_id: str = "org-1") -> list[KPIDefinition]:
        rows = self._conn.execute(
            "SELECT kpi_id, org_id, name, unit, target, frequency, data_source, created_at FROM kpi_definitions WHERE org_id = ?",
            (org_id,),
        ).fetchall()
        return [
            KPIDefinition(
                kpi_id=r[0],
                org_id=r[1],
                name=r[2],
                unit=r[3],
                target=r[4],
                frequency=r[5],
                data_source=r[6],
                created_at=r[7],
            )
            for r in rows
        ]

    def get_kpi(self, kpi_id: str) -> KPIDefinition | None:
        r = self._conn.execute(
            "SELECT kpi_id, org_id, name, unit, target, frequency, data_source, created_at FROM kpi_definitions WHERE kpi_id = ?",
            (kpi_id,),
        ).fetchone()
        if r is None:
            return None
        return KPIDefinition(
            kpi_id=r[0],
            org_id=r[1],
            name=r[2],
            unit=r[3],
            target=r[4],
            frequency=r[5],
            data_source=r[6],
            created_at=r[7],
        )

    def get_latest_value(self, kpi_id: str) -> float | None:
        r = self._conn.execute(
            "SELECT value FROM kpi_data WHERE kpi_id = ? ORDER BY recorded_at DESC LIMIT 1",
            (kpi_id,),
        ).fetchone()
        return r[0] if r else None

    def kpi_status(self, org_id: str = "org-1") -> list[dict]:
        """Get all KPIs with their latest values and target comparison."""
        kpis = self.list_kpis(org_id)
        results = []
        for kpi in kpis:
            latest = self.get_latest_value(kpi.kpi_id)
            on_target = None
            if latest is not None and kpi.target is not None:
                on_target = latest >= kpi.target
            results.append(
                {**kpi.to_dict(), "latest_value": latest, "on_target": on_target}
            )
        return results

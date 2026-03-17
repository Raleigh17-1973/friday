from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import sqlite3
from pathlib import Path
from datetime import datetime
from uuid import uuid4

class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

@dataclass
class Alert:
    alert_id: str
    severity: AlertSeverity
    category: str   # "kpi", "okr", "budget", "deadline"
    title: str
    body: str
    entity_id: str  # the KPI/OKR/invoice ID being flagged
    org_id: str
    created_at: str
    acknowledged: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

class ProactiveScanner:
    """Scans all live data sources for drift, risk, and deadline pressure."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or Path("data/proactive.db")
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    alert_id TEXT PRIMARY KEY,
                    severity TEXT NOT NULL,
                    category TEXT NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    org_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    acknowledged INTEGER NOT NULL DEFAULT 0,
                    metadata TEXT NOT NULL DEFAULT '{}'
                )
            """)

    def scan_kpis(self, kpis: list[dict]) -> list[Alert]:
        """Scan KPI data for threshold breaches and negative trends."""
        alerts = []
        for kpi in kpis:
            current = kpi.get("current_value")
            target = kpi.get("target_value")
            if current is None or target is None:
                continue
            # Determine direction (higher_is_better vs lower_is_better)
            higher_better = kpi.get("higher_is_better", True)
            if higher_better:
                pct = current / target if target else 0
            else:
                pct = target / current if current else 0

            if pct < 0.7:
                severity = AlertSeverity.CRITICAL
                msg = f"KPI '{kpi['name']}' is at {pct:.0%} of target — critically behind"
            elif pct < 0.85:
                severity = AlertSeverity.WARNING
                msg = f"KPI '{kpi['name']}' is at {pct:.0%} of target — needs attention"
            else:
                continue

            alert = Alert(
                alert_id=f"alert_{uuid4().hex[:12]}",
                severity=severity,
                category="kpi",
                title=msg,
                body=f"Current: {current} {kpi.get('unit', '')} | Target: {target} {kpi.get('unit', '')}",
                entity_id=kpi.get("kpi_id", ""),
                org_id=kpi.get("org_id", "org-1"),
                created_at=datetime.utcnow().isoformat() + "Z",
            )
            self._save_alert(alert)
            alerts.append(alert)
        return alerts

    def scan_okrs(self, objectives: list[dict]) -> list[Alert]:
        """Scan OKRs for stalled progress and deadline risk."""
        alerts = []
        for obj in objectives:
            progress = obj.get("progress_pct", 0)
            due_date_str = obj.get("due_date")

            # Check deadline proximity vs progress
            if due_date_str:
                try:
                    due = datetime.fromisoformat(due_date_str.replace("Z", ""))
                    days_left = (due - datetime.utcnow()).days
                    days_total = max(1, (due - datetime.utcnow()).days + 90)  # estimate 90 day cycle
                    time_elapsed_pct = 1 - (days_left / days_total)

                    if progress < time_elapsed_pct * 0.7 and days_left < 30:
                        alert = Alert(
                            alert_id=f"alert_{uuid4().hex[:12]}",
                            severity=AlertSeverity.CRITICAL,
                            category="okr",
                            title=f"OKR at risk: '{obj['title']}'",
                            body=f"{progress:.0f}% complete with {days_left} days remaining. Time elapsed suggests {time_elapsed_pct:.0%} should be done.",
                            entity_id=obj.get("objective_id", ""),
                            org_id=obj.get("org_id", "org-1"),
                            created_at=datetime.utcnow().isoformat() + "Z",
                        )
                        self._save_alert(alert)
                        alerts.append(alert)
                except (ValueError, TypeError):
                    pass
        return alerts

    def scan_budget(self, categories: list[dict]) -> list[Alert]:
        """Scan budget categories for overspend."""
        alerts = []
        for cat in categories:
            planned = cat.get("planned_amount", 0)
            actual = cat.get("actual_amount", 0)
            if planned <= 0:
                continue
            pct_used = actual / planned
            if pct_used > 1.1:
                alert = Alert(
                    alert_id=f"alert_{uuid4().hex[:12]}",
                    severity=AlertSeverity.CRITICAL,
                    category="budget",
                    title=f"Budget overspend: {cat.get('name', 'Unknown')}",
                    body=f"Spent ${actual:,.2f} vs ${planned:,.2f} planned ({pct_used:.0%})",
                    entity_id=cat.get("category_id", ""),
                    org_id=cat.get("org_id", "org-1"),
                    created_at=datetime.utcnow().isoformat() + "Z",
                )
                self._save_alert(alert)
                alerts.append(alert)
            elif pct_used > 0.85:
                alert = Alert(
                    alert_id=f"alert_{uuid4().hex[:12]}",
                    severity=AlertSeverity.WARNING,
                    category="budget",
                    title=f"Budget approaching limit: {cat.get('name', 'Unknown')}",
                    body=f"Spent ${actual:,.2f} of ${planned:,.2f} budget ({pct_used:.0%} used)",
                    entity_id=cat.get("category_id", ""),
                    org_id=cat.get("org_id", "org-1"),
                    created_at=datetime.utcnow().isoformat() + "Z",
                )
                self._save_alert(alert)
                alerts.append(alert)
        return alerts

    def list_alerts(self, org_id: str = "org-1", severity: str | None = None, limit: int = 50) -> list[Alert]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            query = "SELECT * FROM alerts WHERE org_id = ? AND acknowledged = 0"
            params: list = [org_id]
            if severity:
                query += " AND severity = ?"
                params.append(severity)
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_alert(r) for r in rows]

    def acknowledge(self, alert_id: str) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("UPDATE alerts SET acknowledged = 1 WHERE alert_id = ?", (alert_id,))

    def get_alert(self, alert_id: str) -> Alert | None:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM alerts WHERE alert_id = ?", (alert_id,)).fetchone()
        return self._row_to_alert(row) if row else None

    def _save_alert(self, alert: Alert) -> None:
        import json
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO alerts VALUES (?,?,?,?,?,?,?,?,?,?)",
                (alert.alert_id, alert.severity.value, alert.category, alert.title,
                 alert.body, alert.entity_id, alert.org_id, alert.created_at,
                 1 if alert.acknowledged else 0, json.dumps(alert.metadata))
            )

    def _row_to_alert(self, row) -> Alert:
        import json
        return Alert(
            alert_id=row["alert_id"], severity=AlertSeverity(row["severity"]),
            category=row["category"], title=row["title"], body=row["body"],
            entity_id=row["entity_id"], org_id=row["org_id"],
            created_at=row["created_at"], acknowledged=bool(row["acknowledged"]),
            metadata=json.loads(row["metadata"] or "{}"),
        )

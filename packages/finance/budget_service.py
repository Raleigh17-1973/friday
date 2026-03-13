from __future__ import annotations

import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from packages.common.models import utc_now_iso


@dataclass
class BudgetCategory:
    category_id: str
    org_id: str
    name: str
    planned_amount: float
    period: str = "monthly"  # monthly, quarterly, annual
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self):
        return asdict(self)


@dataclass
class Expense:
    expense_id: str
    category_id: str
    amount: float
    description: str
    recorded_at: str = field(default_factory=utc_now_iso)

    def to_dict(self):
        return asdict(self)


class BudgetService:
    def __init__(self, db_path: Path | None = None):
        path = str(db_path) if db_path else ":memory:"
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS budget_categories (
            category_id TEXT PRIMARY KEY, org_id TEXT NOT NULL,
            name TEXT NOT NULL, planned_amount REAL NOT NULL,
            period TEXT NOT NULL DEFAULT 'monthly', created_at TEXT NOT NULL)"""
        )
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS expenses (
            expense_id TEXT PRIMARY KEY, category_id TEXT NOT NULL,
            amount REAL NOT NULL, description TEXT NOT NULL DEFAULT '',
            recorded_at TEXT NOT NULL,
            FOREIGN KEY (category_id) REFERENCES budget_categories(category_id))"""
        )
        self._conn.commit()

    def create_category(
        self,
        name: str,
        planned_amount: float,
        org_id: str = "org-1",
        period: str = "monthly",
    ) -> BudgetCategory:
        cat = BudgetCategory(
            category_id=f"bcat_{uuid.uuid4().hex[:10]}",
            org_id=org_id,
            name=name,
            planned_amount=planned_amount,
            period=period,
        )
        self._conn.execute(
            "INSERT INTO budget_categories (category_id, org_id, name, planned_amount, period, created_at) VALUES (?,?,?,?,?,?)",
            (cat.category_id, cat.org_id, cat.name, cat.planned_amount, cat.period, cat.created_at),
        )
        self._conn.commit()
        return cat

    def record_expense(
        self, category_id: str, amount: float, description: str = ""
    ) -> Expense:
        exp = Expense(
            expense_id=f"exp_{uuid.uuid4().hex[:10]}",
            category_id=category_id,
            amount=amount,
            description=description,
        )
        self._conn.execute(
            "INSERT INTO expenses (expense_id, category_id, amount, description, recorded_at) VALUES (?,?,?,?,?)",
            (exp.expense_id, exp.category_id, exp.amount, exp.description, exp.recorded_at),
        )
        self._conn.commit()
        return exp

    def budget_status(self, org_id: str = "org-1") -> list[dict]:
        """Get each category's planned, actual, variance, and % used."""
        categories = self.list_categories(org_id)
        results = []
        for cat in categories:
            actual = self._total_expenses(cat.category_id)
            variance = cat.planned_amount - actual
            pct_used = (actual / cat.planned_amount * 100) if cat.planned_amount else 0.0
            results.append({
                **cat.to_dict(),
                "actual": actual,
                "variance": variance,
                "pct_used": round(pct_used, 1),
            })
        return results

    def list_categories(self, org_id: str = "org-1") -> list[BudgetCategory]:
        rows = self._conn.execute(
            "SELECT category_id, org_id, name, planned_amount, period, created_at FROM budget_categories WHERE org_id = ?",
            (org_id,),
        ).fetchall()
        return [
            BudgetCategory(
                category_id=r[0], org_id=r[1], name=r[2],
                planned_amount=r[3], period=r[4], created_at=r[5],
            )
            for r in rows
        ]

    def _total_expenses(self, category_id: str) -> float:
        r = self._conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE category_id = ?",
            (category_id,),
        ).fetchone()
        return r[0]

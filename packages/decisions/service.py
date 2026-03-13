from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4
from datetime import datetime


@dataclass
class Decision:
    decision_id: str
    title: str
    context: str          # What situation led to this decision
    options_considered: list[str]
    rationale: str        # Why this option was chosen
    owner: str            # Who made/owns the decision
    made_at: str
    org_id: str
    tags: list[str] = field(default_factory=list)
    outcome: str = ""     # Filled in later
    reversibility: str = "reversible"  # "reversible" | "one-way"
    confidence: float = 0.8
    related_run_id: str = ""  # Link back to Friday run that drove the decision
    metadata: dict[str, Any] = field(default_factory=dict)


class DecisionLogService:
    """Persistent log of significant organizational decisions."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or Path("data/decisions.db")
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS decisions (
                    decision_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    context TEXT NOT NULL,
                    options_considered TEXT NOT NULL DEFAULT '[]',
                    rationale TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    made_at TEXT NOT NULL,
                    org_id TEXT NOT NULL,
                    tags TEXT NOT NULL DEFAULT '[]',
                    outcome TEXT NOT NULL DEFAULT '',
                    reversibility TEXT NOT NULL DEFAULT 'reversible',
                    confidence REAL NOT NULL DEFAULT 0.8,
                    related_run_id TEXT NOT NULL DEFAULT '',
                    metadata TEXT NOT NULL DEFAULT '{}'
                )
            """)

    def log(
        self,
        title: str,
        context: str,
        rationale: str,
        owner: str,
        options_considered: list[str] | None = None,
        org_id: str = "org-1",
        tags: list[str] | None = None,
        reversibility: str = "reversible",
        confidence: float = 0.8,
        related_run_id: str = "",
    ) -> Decision:
        decision = Decision(
            decision_id=f"dec_{uuid4().hex[:12]}",
            title=title,
            context=context,
            options_considered=options_considered or [],
            rationale=rationale,
            owner=owner,
            made_at=datetime.utcnow().isoformat() + "Z",
            org_id=org_id,
            tags=tags or [],
            reversibility=reversibility,
            confidence=confidence,
            related_run_id=related_run_id,
        )
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO decisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (decision.decision_id, decision.title, decision.context,
                 json.dumps(decision.options_considered), decision.rationale,
                 decision.owner, decision.made_at, decision.org_id,
                 json.dumps(decision.tags), decision.outcome,
                 decision.reversibility, decision.confidence,
                 decision.related_run_id, json.dumps(decision.metadata)),
            )
        return decision

    def record_outcome(self, decision_id: str, outcome: str) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("UPDATE decisions SET outcome = ? WHERE decision_id = ?", (outcome, decision_id))

    def search(self, query: str, org_id: str = "org-1", limit: int = 10) -> list[Decision]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT * FROM decisions
                   WHERE org_id = ? AND (title LIKE ? OR context LIKE ? OR rationale LIKE ?)
                   ORDER BY made_at DESC LIMIT ?""",
                (org_id, f"%{query}%", f"%{query}%", f"%{query}%", limit),
            ).fetchall()
        return [self._row_to_decision(r) for r in rows]

    def list_decisions(self, org_id: str = "org-1", tag: str | None = None, limit: int = 50) -> list[Decision]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            q = "SELECT * FROM decisions WHERE org_id = ?"
            params: list = [org_id]
            if tag:
                q += " AND tags LIKE ?"
                params.append(f'%"{tag}"%')
            q += " ORDER BY made_at DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(q, params).fetchall()
        return [self._row_to_decision(r) for r in rows]

    def get(self, decision_id: str) -> Decision | None:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM decisions WHERE decision_id = ?", (decision_id,)).fetchone()
        return self._row_to_decision(row) if row else None

    def _row_to_decision(self, row) -> Decision:
        return Decision(
            decision_id=row["decision_id"], title=row["title"],
            context=row["context"],
            options_considered=json.loads(row["options_considered"] or "[]"),
            rationale=row["rationale"], owner=row["owner"],
            made_at=row["made_at"], org_id=row["org_id"],
            tags=json.loads(row["tags"] or "[]"),
            outcome=row["outcome"], reversibility=row["reversibility"],
            confidence=row["confidence"], related_run_id=row["related_run_id"],
            metadata=json.loads(row["metadata"] or "{}"),
        )

    def context_for_query(self, query: str, org_id: str = "org-1") -> str:
        """Return relevant past decisions as text for LLM injection."""
        decisions = self.search(query, org_id, limit=5)
        if not decisions:
            return ""
        lines = ["**Relevant past decisions:**"]
        for d in decisions:
            lines.append(f"- [{d.made_at[:10]}] {d.title}: {d.rationale[:120]}")
        return "\n".join(lines)

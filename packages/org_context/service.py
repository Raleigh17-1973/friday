from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4
from datetime import datetime


@dataclass
class Person:
    person_id: str
    name: str
    role: str
    department: str
    email: str = ""
    reports_to: str = ""  # person_id of manager
    org_id: str = "org-1"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategicPriority:
    priority_id: str
    title: str
    description: str
    owner: str  # person_id or name
    due_date: str
    status: str  # "active", "completed", "paused"
    org_id: str = "org-1"
    created_at: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class OrgProfile:
    org_id: str
    company_name: str
    industry: str
    stage: str  # "seed", "series_a", "growth", "enterprise"
    fiscal_year_end: str  # "12-31", "03-31", etc.
    headcount: int
    founded_year: int | None
    mission: str
    values: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)


class OrgContextService:
    """Persistent organizational memory — company profile, people, priorities."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or Path("data/org_context.db")
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS org_profiles (
                    org_id TEXT PRIMARY KEY,
                    company_name TEXT NOT NULL,
                    industry TEXT NOT NULL DEFAULT '',
                    stage TEXT NOT NULL DEFAULT 'growth',
                    fiscal_year_end TEXT NOT NULL DEFAULT '12-31',
                    headcount INTEGER NOT NULL DEFAULT 0,
                    founded_year INTEGER,
                    mission TEXT NOT NULL DEFAULT '',
                    company_values TEXT NOT NULL DEFAULT '[]',
                    metadata TEXT NOT NULL DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS people (
                    person_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    department TEXT NOT NULL,
                    email TEXT NOT NULL DEFAULT '',
                    reports_to TEXT NOT NULL DEFAULT '',
                    org_id TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS strategic_priorities (
                    priority_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    due_date TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    org_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    tags TEXT NOT NULL DEFAULT '[]'
                );
            """)

    # --- Org Profile ---
    def upsert_profile(self, profile: OrgProfile) -> OrgProfile:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO org_profiles
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (profile.org_id, profile.company_name, profile.industry,
                 profile.stage, profile.fiscal_year_end, profile.headcount,
                 profile.founded_year, profile.mission,
                 json.dumps(profile.values), json.dumps(profile.metadata)),
            )
        return profile

    def get_profile(self, org_id: str = "org-1") -> OrgProfile | None:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM org_profiles WHERE org_id = ?", (org_id,)).fetchone()
        if not row:
            return None
        return OrgProfile(
            org_id=row["org_id"], company_name=row["company_name"],
            industry=row["industry"], stage=row["stage"],
            fiscal_year_end=row["fiscal_year_end"], headcount=row["headcount"],
            founded_year=row["founded_year"], mission=row["mission"],
            values=json.loads(row["company_values"] or "[]"),
            metadata=json.loads(row["metadata"] or "{}"),
        )

    # --- People ---
    def upsert_person(self, person: Person) -> Person:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO people VALUES (?,?,?,?,?,?,?,?)",
                (person.person_id, person.name, person.role, person.department,
                 person.email, person.reports_to, person.org_id, json.dumps(person.metadata)),
            )
        return person

    def get_person(self, person_id: str) -> Person | None:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM people WHERE person_id = ?", (person_id,)).fetchone()
        if not row:
            return None
        return self._row_to_person(row)

    def list_people(self, org_id: str = "org-1", department: str | None = None) -> list[Person]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            q = "SELECT * FROM people WHERE org_id = ?"
            params: list = [org_id]
            if department:
                q += " AND department = ?"
                params.append(department)
            rows = conn.execute(q, params).fetchall()
        return [self._row_to_person(r) for r in rows]

    def org_chart(self, org_id: str = "org-1") -> dict:
        """Return hierarchical org chart as nested dict."""
        people = self.list_people(org_id)
        chart: dict[str, Any] = {"root": [], "nodes": {}}
        for p in people:
            chart["nodes"][p.person_id] = {
                "name": p.name, "role": p.role, "department": p.department,
                "reports_to": p.reports_to, "direct_reports": [],
            }
        for p in people:
            if p.reports_to and p.reports_to in chart["nodes"]:
                chart["nodes"][p.reports_to]["direct_reports"].append(p.person_id)
            elif not p.reports_to:
                chart["root"].append(p.person_id)
        return chart

    def _row_to_person(self, row) -> Person:
        return Person(
            person_id=row["person_id"], name=row["name"], role=row["role"],
            department=row["department"], email=row["email"],
            reports_to=row["reports_to"], org_id=row["org_id"],
            metadata=json.loads(row["metadata"] or "{}"),
        )

    # --- Strategic Priorities ---
    def add_priority(self, title: str, description: str, owner: str, due_date: str,
                     org_id: str = "org-1", tags: list[str] | None = None) -> StrategicPriority:
        priority = StrategicPriority(
            priority_id=f"pri_{uuid4().hex[:12]}",
            title=title, description=description, owner=owner,
            due_date=due_date, status="active", org_id=org_id,
            created_at=datetime.utcnow().isoformat() + "Z",
            tags=tags or [],
        )
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO strategic_priorities VALUES (?,?,?,?,?,?,?,?,?)",
                (priority.priority_id, priority.title, priority.description,
                 priority.owner, priority.due_date, priority.status,
                 priority.org_id, priority.created_at, json.dumps(priority.tags)),
            )
        return priority

    def list_priorities(self, org_id: str = "org-1", status: str = "active") -> list[StrategicPriority]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM strategic_priorities WHERE org_id = ? AND status = ? ORDER BY due_date",
                (org_id, status),
            ).fetchall()
        return [
            StrategicPriority(
                priority_id=r["priority_id"], title=r["title"],
                description=r["description"], owner=r["owner"],
                due_date=r["due_date"], status=r["status"],
                org_id=r["org_id"], created_at=r["created_at"],
                tags=json.loads(r["tags"] or "[]"),
            )
            for r in rows
        ]

    def build_context_summary(self, org_id: str = "org-1") -> str:
        """Build a text summary of org context for injection into LLM prompts."""
        profile = self.get_profile(org_id)
        people = self.list_people(org_id)
        priorities = self.list_priorities(org_id)

        parts = []
        if profile:
            parts.append(
                f"Company: {profile.company_name} | Industry: {profile.industry} | "
                f"Stage: {profile.stage} | Headcount: {profile.headcount}\n"
                f"Mission: {profile.mission}"
            )
        if people:
            team = ", ".join(f"{p.name} ({p.role})" for p in people[:10])
            parts.append(f"Key People: {team}")
        if priorities:
            pri_list = "; ".join(f"{p.title} [{p.status}]" for p in priorities[:5])
            parts.append(f"Strategic Priorities: {pri_list}")
        return "\n".join(parts)

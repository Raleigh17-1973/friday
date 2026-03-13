from __future__ import annotations

import json
import sqlite3
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from packages.common.models import ProcessDocument, ProcessStep, utc_now_iso


class ProcessRepository(ABC):
    @abstractmethod
    def create(self, doc: ProcessDocument) -> ProcessDocument: ...

    @abstractmethod
    def get_latest(self, process_id: str) -> ProcessDocument | None: ...

    @abstractmethod
    def get_version(self, process_id: str, version: str) -> ProcessDocument | None: ...

    @abstractmethod
    def list_versions(self, process_id: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    def list_by_org(self, org_id: str) -> list[ProcessDocument]: ...

    @abstractmethod
    def save_version(self, doc: ProcessDocument, changelog_entry: str, author: str) -> ProcessDocument: ...

    @abstractmethod
    def soft_delete(self, process_id: str) -> None: ...


class SQLiteProcessRepository(ProcessRepository):
    """SQLite-backed process document store with full version history."""

    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            db_path = Path("data/friday_processes.sqlite3")
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db: sqlite3.Connection = sqlite3.connect(str(db_path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS processes (
                process_id  TEXT PRIMARY KEY,
                org_id      TEXT NOT NULL,
                process_name TEXT NOT NULL,
                current_version TEXT NOT NULL DEFAULT '1.0.0',
                status      TEXT NOT NULL DEFAULT 'draft',
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS process_versions (
                id              TEXT PRIMARY KEY,
                process_id      TEXT NOT NULL,
                version         TEXT NOT NULL,
                full_document   TEXT NOT NULL,
                author          TEXT NOT NULL DEFAULT 'system',
                changelog_entry TEXT NOT NULL DEFAULT '',
                created_at      TEXT NOT NULL,
                FOREIGN KEY (process_id) REFERENCES processes(process_id)
            );

            CREATE INDEX IF NOT EXISTS idx_pv_process_id ON process_versions(process_id);
            CREATE INDEX IF NOT EXISTS idx_p_org_id      ON processes(org_id);
        """)
        self._db.commit()

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_doc(row: dict[str, Any]) -> ProcessDocument:
        data: dict[str, Any] = json.loads(row["full_document"])
        steps = [
            ProcessStep(**s) if isinstance(s, dict) else s
            for s in data.get("steps", [])
        ]
        return ProcessDocument(
            id=data["id"],
            org_id=data["org_id"],
            process_name=data["process_name"],
            trigger=data.get("trigger", ""),
            steps=steps,
            decision_points=data.get("decision_points", []),
            roles=data.get("roles", []),
            tools=data.get("tools", []),
            exceptions=data.get("exceptions", []),
            kpis=data.get("kpis", []),
            mermaid_flowchart=data.get("mermaid_flowchart", ""),
            mermaid_swimlane=data.get("mermaid_swimlane", ""),
            completeness_score=float(data.get("completeness_score", 0.0)),
            version=data.get("version", "1.0.0"),
            status=data.get("status", "draft"),
            created_at=data.get("created_at", utc_now_iso()),
            updated_at=data.get("updated_at", utc_now_iso()),
            changelog=data.get("changelog", []),
        )

    # ── public API ────────────────────────────────────────────────────────────

    def create(self, doc: ProcessDocument) -> ProcessDocument:
        if not doc.id:
            doc.id = f"proc_{uuid.uuid4().hex[:12]}"
        now = utc_now_iso()
        doc.created_at = now
        doc.updated_at = now
        doc.version = "1.0.0"
        doc.changelog = [{"version": "1.0.0", "date": now, "author": "system", "changes": ["Initial version"]}]

        self._db.execute(
            "INSERT INTO processes (process_id, org_id, process_name, current_version, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (doc.id, doc.org_id, doc.process_name, doc.version, doc.status, now, now),
        )
        self._db.execute(
            "INSERT INTO process_versions (id, process_id, version, full_document, author, changelog_entry, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (uuid.uuid4().hex, doc.id, doc.version, json.dumps(doc.to_dict()), "system", "Initial version", now),
        )
        self._db.commit()
        return doc

    def get_latest(self, process_id: str) -> ProcessDocument | None:
        row = self._db.execute(
            "SELECT pv.full_document FROM process_versions pv "
            "JOIN processes p ON p.process_id = pv.process_id "
            "WHERE pv.process_id = ? AND pv.version = p.current_version",
            (process_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_doc(dict(row))

    def get_version(self, process_id: str, version: str) -> ProcessDocument | None:
        row = self._db.execute(
            "SELECT full_document FROM process_versions WHERE process_id = ? AND version = ?",
            (process_id, version),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_doc(dict(row))

    def list_versions(self, process_id: str) -> list[dict[str, Any]]:
        rows = self._db.execute(
            "SELECT version, author, changelog_entry, created_at "
            "FROM process_versions WHERE process_id = ? ORDER BY created_at DESC",
            (process_id,),
        ).fetchall()
        return [
            {"version": r["version"], "author": r["author"],
             "changes": r["changelog_entry"], "date": r["created_at"]}
            for r in rows
        ]

    def list_by_org(self, org_id: str) -> list[ProcessDocument]:
        rows = self._db.execute(
            "SELECT pv.full_document FROM process_versions pv "
            "JOIN processes p ON p.process_id = pv.process_id "
            "WHERE p.org_id = ? AND pv.version = p.current_version AND p.status != 'deleted' "
            "ORDER BY p.updated_at DESC",
            (org_id,),
        ).fetchall()
        return [self._row_to_doc(dict(r)) for r in rows]

    def save_version(self, doc: ProcessDocument, changelog_entry: str, author: str) -> ProcessDocument:
        now = utc_now_iso()
        doc.updated_at = now
        doc.changelog = list(doc.changelog or [])
        doc.changelog.insert(0, {"version": doc.version, "date": now, "author": author, "changes": changelog_entry})

        self._db.execute(
            "UPDATE processes SET current_version = ?, status = ?, process_name = ?, updated_at = ? WHERE process_id = ?",
            (doc.version, doc.status, doc.process_name, now, doc.id),
        )
        self._db.execute(
            "INSERT INTO process_versions (id, process_id, version, full_document, author, changelog_entry, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (uuid.uuid4().hex, doc.id, doc.version, json.dumps(doc.to_dict()), author, changelog_entry, now),
        )
        self._db.commit()
        return doc

    def soft_delete(self, process_id: str) -> None:
        self._db.execute(
            "UPDATE processes SET status = 'deleted', updated_at = ? WHERE process_id = ?",
            (utc_now_iso(), process_id),
        )
        self._db.commit()

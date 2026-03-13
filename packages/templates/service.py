"""Template management for document generation."""
from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from packages.common.models import utc_now_iso


@dataclass
class DocumentTemplate:
    template_id: str
    org_id: str
    name: str
    description: str
    document_type: str  # "docx", "pptx", "xlsx", "pdf"
    template_path: str
    variables: list[str] = field(default_factory=list)
    category: str = "general"  # memo, report, deck, sop, invoice
    version: str = "1.0.0"
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TemplateService:
    """CRUD for document templates with seed template support."""

    def __init__(self, db_path: Path | None = None, seed_dir: Path | None = None) -> None:
        path = str(db_path) if db_path else ":memory:"
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS templates (
                template_id TEXT PRIMARY KEY,
                org_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                document_type TEXT NOT NULL,
                template_path TEXT NOT NULL,
                variables TEXT NOT NULL DEFAULT '[]',
                category TEXT NOT NULL DEFAULT 'general',
                version TEXT NOT NULL DEFAULT '1.0.0',
                created_at TEXT NOT NULL
            )"""
        )
        self._conn.commit()
        self._seed_dir = seed_dir
        if seed_dir:
            self._load_seed_templates(seed_dir)

    def _load_seed_templates(self, seed_dir: Path) -> None:
        """Load built-in templates from a seed directory if not already in DB."""
        if not seed_dir.exists():
            return
        existing = self._conn.execute("SELECT COUNT(*) FROM templates WHERE org_id = '__system__'").fetchone()[0]
        if existing > 0:
            return

        seed_templates = [
            ("Business Memo", "Professional business memorandum", "docx", "memo"),
            ("Executive Report", "Comprehensive executive report with sections", "docx", "report"),
            ("Status Update Deck", "Weekly/monthly status update presentation", "pptx", "deck"),
            ("Board Update Deck", "Quarterly board update presentation", "pptx", "deck"),
            ("SOP Document", "Standard operating procedure template", "docx", "sop"),
            ("Invoice", "Professional invoice with line items", "docx", "invoice"),
            ("Financial Model", "Budget and financial model spreadsheet", "xlsx", "spreadsheet"),
        ]

        for name, desc, doc_type, category in seed_templates:
            tpl = DocumentTemplate(
                template_id=f"tpl_{uuid.uuid4().hex[:10]}",
                org_id="__system__",
                name=name,
                description=desc,
                document_type=doc_type,
                template_path=str(seed_dir / f"{category}.{doc_type}"),
                category=category,
                variables=["title", "author", "date", "company_name"],
            )
            self._save(tpl)

    def _save(self, t: DocumentTemplate) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO templates
               (template_id, org_id, name, description, document_type, template_path, variables, category, version, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (t.template_id, t.org_id, t.name, t.description, t.document_type,
             t.template_path, json.dumps(t.variables), t.category, t.version, t.created_at),
        )
        self._conn.commit()

    def create(self, template: DocumentTemplate) -> DocumentTemplate:
        if not template.template_id:
            template.template_id = f"tpl_{uuid.uuid4().hex[:10]}"
        self._save(template)
        return template

    def get(self, template_id: str) -> DocumentTemplate | None:
        row = self._conn.execute("SELECT * FROM templates WHERE template_id = ?", (template_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_template(row)

    def list_templates(self, org_id: str = "org-1", category: str | None = None) -> list[DocumentTemplate]:
        query = "SELECT * FROM templates WHERE (org_id = ? OR org_id = '__system__')"
        params: list[Any] = [org_id]
        if category:
            query += " AND category = ?"
            params.append(category)
        query += " ORDER BY name"
        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_template(r) for r in rows]

    def list_by_type(self, document_type: str, org_id: str = "org-1") -> list[DocumentTemplate]:
        rows = self._conn.execute(
            "SELECT * FROM templates WHERE document_type = ? AND (org_id = ? OR org_id = '__system__') ORDER BY name",
            (document_type, org_id),
        ).fetchall()
        return [self._row_to_template(r) for r in rows]

    def delete(self, template_id: str) -> None:
        self._conn.execute("DELETE FROM templates WHERE template_id = ?", (template_id,))
        self._conn.commit()

    @staticmethod
    def _row_to_template(row: tuple) -> DocumentTemplate:
        return DocumentTemplate(
            template_id=row[0], org_id=row[1], name=row[2], description=row[3],
            document_type=row[4], template_path=row[5],
            variables=json.loads(row[6]) if row[6] else [],
            category=row[7], version=row[8], created_at=row[9],
        )

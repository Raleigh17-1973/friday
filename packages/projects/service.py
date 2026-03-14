from __future__ import annotations

import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from packages.common.models import utc_now_iso


@dataclass
class Project:
    project_id: str
    workspace_id: str
    name: str
    description: str = ""
    color: str = "#6366f1"
    icon: str = "📁"
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict:
        return asdict(self)


class ProjectService:
    def __init__(self, db_path: Path | None = None) -> None:
        path = str(db_path) if db_path else ":memory:"
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS projects (
                project_id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                color TEXT NOT NULL DEFAULT '#6366f1',
                icon TEXT NOT NULL DEFAULT '📁',
                created_at TEXT NOT NULL
            )"""
        )
        self._conn.commit()

    def create(
        self,
        workspace_id: str,
        name: str,
        description: str = "",
        color: str = "#6366f1",
        icon: str = "📁",
    ) -> Project:
        project = Project(
            project_id=f"proj_{uuid.uuid4().hex[:10]}",
            workspace_id=workspace_id,
            name=name,
            description=description,
            color=color,
            icon=icon,
        )
        self._conn.execute(
            "INSERT INTO projects (project_id, workspace_id, name, description, color, icon, created_at) VALUES (?,?,?,?,?,?,?)",
            (project.project_id, project.workspace_id, project.name, project.description, project.color, project.icon, project.created_at),
        )
        self._conn.commit()
        return project

    def list(self, workspace_id: str) -> list[Project]:
        rows = self._conn.execute(
            "SELECT project_id, workspace_id, name, description, color, icon, created_at FROM projects WHERE workspace_id = ? ORDER BY created_at ASC",
            (workspace_id,),
        ).fetchall()
        return [Project(project_id=r[0], workspace_id=r[1], name=r[2], description=r[3], color=r[4], icon=r[5], created_at=r[6]) for r in rows]

    def get(self, project_id: str) -> Project | None:
        r = self._conn.execute(
            "SELECT project_id, workspace_id, name, description, color, icon, created_at FROM projects WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        if r is None:
            return None
        return Project(project_id=r[0], workspace_id=r[1], name=r[2], description=r[3], color=r[4], icon=r[5], created_at=r[6])

    def update(self, project_id: str, **kwargs) -> Project | None:
        project = self.get(project_id)
        if project is None:
            return None
        allowed = {"name", "description", "color", "icon"}
        for k, v in kwargs.items():
            if k in allowed and v is not None:
                setattr(project, k, v)
        self._conn.execute(
            "UPDATE projects SET name=?, description=?, color=?, icon=? WHERE project_id=?",
            (project.name, project.description, project.color, project.icon, project_id),
        )
        self._conn.commit()
        return project

    def delete(self, project_id: str) -> None:
        self._conn.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))
        self._conn.commit()

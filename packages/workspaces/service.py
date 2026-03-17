from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4
from datetime import datetime


@dataclass
class Workspace:
    workspace_id: str
    name: str
    slug: str           # URL-safe, unique per org
    description: str
    icon: str           # emoji e.g. "🚀"
    color: str          # hex e.g. "#0f5cc0"
    type: str           # "company" | "team" | "client" | "initiative" | "confidential" | "personal"
    owner: str          # user_id
    org_id: str
    visibility: str     # "open" | "closed" | "private"
    default_view: str   # "chat" | "okrs" | "documents" | "overview"
    archived: bool
    created_at: str
    updated_at: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkspaceMember:
    member_id: str
    workspace_id: str
    user_id: str
    role: str           # "owner" | "editor" | "viewer"
    joined_at: str


@dataclass
class WorkspaceLink:
    link_id: str
    workspace_id: str
    entity_type: str    # "conversation" | "document" | "okr" | "artifact"
    entity_id: str
    created_at: str


class WorkspaceService:
    """Workspace management — create, list, member management, entity linking."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or Path("data/workspaces.db")
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._seed_default()

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS workspaces (
                    workspace_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    slug TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    icon TEXT NOT NULL DEFAULT '🏢',
                    color TEXT NOT NULL DEFAULT '#0f5cc0',
                    type TEXT NOT NULL DEFAULT 'team',
                    owner TEXT NOT NULL DEFAULT 'user-1',
                    org_id TEXT NOT NULL DEFAULT 'org-1',
                    visibility TEXT NOT NULL DEFAULT 'open',
                    default_view TEXT NOT NULL DEFAULT 'overview',
                    archived INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}'
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_workspace_slug ON workspaces (org_id, slug);
                CREATE TABLE IF NOT EXISTS workspace_members (
                    member_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'editor',
                    joined_at TEXT NOT NULL,
                    UNIQUE (workspace_id, user_id)
                );
                CREATE TABLE IF NOT EXISTS workspace_links (
                    link_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE (workspace_id, entity_type, entity_id)
                );
            """)

    def _seed_default(self) -> None:
        """Create the default workspace if it doesn't exist."""
        with sqlite3.connect(self._db_path) as conn:
            exists = conn.execute(
                "SELECT 1 FROM workspaces WHERE slug = 'default' AND org_id = 'org-1'"
            ).fetchone()
            if not exists:
                now = datetime.utcnow().isoformat() + "Z"
                conn.execute(
                    """INSERT OR IGNORE INTO workspaces
                       (workspace_id, name, slug, description, icon, color, type,
                        owner, org_id, visibility, default_view, archived, created_at, updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    ("ws_default", "Default", "default",
                     "General workspace for all conversations and documents",
                     "🏢", "#0f5cc0", "company", "user-1", "org-1",
                     "open", "overview", 0, now, now)
                )

    # ---- CRUD ----
    def create(
        self,
        name: str,
        org_id: str = "org-1",
        owner: str = "user-1",
        type: str = "team",
        description: str = "",
        icon: str = "🏢",
        color: str = "#0f5cc0",
        visibility: str = "open",
        default_view: str = "overview",
    ) -> Workspace:
        slug = self._slugify(name)
        # Ensure slug uniqueness
        with sqlite3.connect(self._db_path) as conn:
            existing = conn.execute(
                "SELECT slug FROM workspaces WHERE org_id = ? AND slug LIKE ?",
                (org_id, f"{slug}%")
            ).fetchall()
        if existing:
            slug = f"{slug}-{len(existing)}"

        now = datetime.utcnow().isoformat() + "Z"
        workspace = Workspace(
            workspace_id=f"ws_{uuid4().hex[:12]}",
            name=name, slug=slug, description=description,
            icon=icon, color=color, type=type, owner=owner,
            org_id=org_id, visibility=visibility, default_view=default_view,
            archived=False, created_at=now, updated_at=now,
        )
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """INSERT INTO workspaces
                   (workspace_id,name,slug,description,icon,color,type,owner,org_id,
                    visibility,default_view,archived,created_at,updated_at,metadata)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (workspace.workspace_id, workspace.name, workspace.slug,
                 workspace.description, workspace.icon, workspace.color,
                 workspace.type, workspace.owner, workspace.org_id,
                 workspace.visibility, workspace.default_view,
                 1 if workspace.archived else 0,
                 workspace.created_at, workspace.updated_at,
                 json.dumps(workspace.metadata))
            )
            # Auto-add owner as member
            conn.execute(
                "INSERT OR IGNORE INTO workspace_members (member_id,workspace_id,user_id,role,joined_at) VALUES (?,?,?,?,?)",
                (f"wm_{uuid4().hex[:12]}", workspace.workspace_id, owner, "owner", now)
            )
        return workspace

    def get(self, workspace_id: str) -> Workspace | None:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM workspaces WHERE workspace_id = ?", (workspace_id,)
            ).fetchone()
        return self._row_to_workspace(row) if row else None

    def get_for_org(self, workspace_id: str, org_id: str) -> Workspace | None:
        workspace = self.get(workspace_id)
        if workspace is None or workspace.org_id != org_id:
            return None
        return workspace

    def get_by_slug(self, org_id: str, slug: str) -> Workspace | None:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM workspaces WHERE org_id = ? AND slug = ?", (org_id, slug)
            ).fetchone()
        return self._row_to_workspace(row) if row else None

    def list(self, org_id: str = "org-1", archived: bool = False) -> list[Workspace]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM workspaces WHERE org_id = ? AND archived = ? ORDER BY created_at",
                (org_id, 1 if archived else 0)
            ).fetchall()
        return [self._row_to_workspace(r) for r in rows]

    def update(self, workspace_id: str, **kwargs: Any) -> Workspace | None:
        allowed = {"name", "description", "icon", "color", "type", "visibility", "default_view"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return self.get(workspace_id)
        updates["updated_at"] = datetime.utcnow().isoformat() + "Z"
        if "name" in updates:
            updates["slug"] = self._slugify(updates["name"])
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [workspace_id]
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(f"UPDATE workspaces SET {set_clause} WHERE workspace_id = ?", values)
        return self.get(workspace_id)

    def update_for_org(self, workspace_id: str, org_id: str, **kwargs: Any) -> Workspace | None:
        if self.get_for_org(workspace_id, org_id) is None:
            return None
        return self.update(workspace_id, **kwargs)

    def archive(self, workspace_id: str) -> None:
        now = datetime.utcnow().isoformat() + "Z"
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "UPDATE workspaces SET archived = 1, updated_at = ? WHERE workspace_id = ?",
                (now, workspace_id)
            )

    def archive_for_org(self, workspace_id: str, org_id: str) -> bool:
        if self.get_for_org(workspace_id, org_id) is None:
            return False
        self.archive(workspace_id)
        return True

    # ---- Members ----
    def add_member(self, workspace_id: str, user_id: str, role: str = "editor") -> WorkspaceMember:
        now = datetime.utcnow().isoformat() + "Z"
        member = WorkspaceMember(
            member_id=f"wm_{uuid4().hex[:12]}",
            workspace_id=workspace_id, user_id=user_id,
            role=role, joined_at=now,
        )
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO workspace_members (member_id,workspace_id,user_id,role,joined_at) VALUES (?,?,?,?,?)",
                (member.member_id, member.workspace_id, member.user_id, member.role, member.joined_at)
            )
        return member

    def add_member_for_org(self, workspace_id: str, org_id: str, user_id: str, role: str = "editor") -> WorkspaceMember | None:
        if self.get_for_org(workspace_id, org_id) is None:
            return None
        return self.add_member(workspace_id, user_id, role)

    def remove_member(self, workspace_id: str, user_id: str) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "DELETE FROM workspace_members WHERE workspace_id = ? AND user_id = ?",
                (workspace_id, user_id)
            )

    def remove_member_for_org(self, workspace_id: str, org_id: str, user_id: str) -> bool:
        if self.get_for_org(workspace_id, org_id) is None:
            return False
        self.remove_member(workspace_id, user_id)
        return True

    def list_members(self, workspace_id: str) -> list[WorkspaceMember]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM workspace_members WHERE workspace_id = ? ORDER BY joined_at",
                (workspace_id,)
            ).fetchall()
        return [WorkspaceMember(
            member_id=r["member_id"], workspace_id=r["workspace_id"],
            user_id=r["user_id"], role=r["role"], joined_at=r["joined_at"]
        ) for r in rows]

    def list_members_for_org(self, workspace_id: str, org_id: str) -> list[WorkspaceMember]:
        if self.get_for_org(workspace_id, org_id) is None:
            return []
        return self.list_members(workspace_id)

    # ---- Entity Links ----
    def link_entity(self, workspace_id: str, entity_type: str, entity_id: str) -> WorkspaceLink:
        now = datetime.utcnow().isoformat() + "Z"
        link = WorkspaceLink(
            link_id=f"wl_{uuid4().hex[:12]}",
            workspace_id=workspace_id, entity_type=entity_type,
            entity_id=entity_id, created_at=now,
        )
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO workspace_links (link_id,workspace_id,entity_type,entity_id,created_at) VALUES (?,?,?,?,?)",
                (link.link_id, link.workspace_id, link.entity_type, link.entity_id, link.created_at)
            )
        return link

    def link_entity_for_org(self, workspace_id: str, org_id: str, entity_type: str, entity_id: str) -> WorkspaceLink | None:
        if self.get_for_org(workspace_id, org_id) is None:
            return None
        return self.link_entity(workspace_id, entity_type, entity_id)

    def unlink_entity(self, workspace_id: str, entity_type: str, entity_id: str) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "DELETE FROM workspace_links WHERE workspace_id = ? AND entity_type = ? AND entity_id = ?",
                (workspace_id, entity_type, entity_id)
            )

    def list_linked(self, workspace_id: str, entity_type: str | None = None) -> list[WorkspaceLink]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            if entity_type:
                rows = conn.execute(
                    "SELECT * FROM workspace_links WHERE workspace_id = ? AND entity_type = ? ORDER BY created_at DESC",
                    (workspace_id, entity_type)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM workspace_links WHERE workspace_id = ? ORDER BY created_at DESC",
                    (workspace_id,)
                ).fetchall()
        return [WorkspaceLink(
            link_id=r["link_id"], workspace_id=r["workspace_id"],
            entity_type=r["entity_type"], entity_id=r["entity_id"],
            created_at=r["created_at"]
        ) for r in rows]

    def list_linked_for_org(self, workspace_id: str, org_id: str, entity_type: str | None = None) -> list[WorkspaceLink]:
        if self.get_for_org(workspace_id, org_id) is None:
            return []
        return self.list_linked(workspace_id, entity_type)

    def get_context_summary(self, workspace_id: str) -> str:
        """Build text summary for LLM injection."""
        ws = self.get(workspace_id)
        if not ws:
            return ""
        members = self.list_members(workspace_id)
        links = self.list_linked(workspace_id)
        link_counts = {}
        for link in links:
            link_counts[link.entity_type] = link_counts.get(link.entity_type, 0) + 1
        link_str = ", ".join(f"{v} {k}(s)" for k, v in link_counts.items())
        member_str = f"{len(members)} member(s)"
        return (
            f"Workspace: {ws.name} ({ws.type}) | {member_str} | "
            f"Linked: {link_str or 'none'} | Visibility: {ws.visibility}"
        )

    def get_overview(self, workspace_id: str) -> dict[str, Any]:
        """Full overview for frontend workspace home page."""
        ws = self.get(workspace_id)
        if not ws:
            return {}
        members = self.list_members(workspace_id)
        links = self.list_linked(workspace_id)
        by_type: dict[str, list[str]] = {}
        for link in links:
            by_type.setdefault(link.entity_type, []).append(link.entity_id)
        from dataclasses import asdict
        return {
            "workspace": asdict(ws),
            "members": [{"user_id": m.user_id, "role": m.role} for m in members],
            "linked_conversations": by_type.get("conversation", []),
            "linked_documents": by_type.get("document", []),
            "linked_okrs": by_type.get("okr", []),
            "linked_artifacts": by_type.get("artifact", []),
        }

    def _slugify(self, name: str) -> str:
        slug = name.lower().strip()
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        slug = slug.strip("-")
        return slug[:50]

    def _row_to_workspace(self, row) -> Workspace:
        return Workspace(
            workspace_id=row["workspace_id"], name=row["name"],
            slug=row["slug"], description=row["description"],
            icon=row["icon"], color=row["color"], type=row["type"],
            owner=row["owner"], org_id=row["org_id"],
            visibility=row["visibility"], default_view=row["default_view"],
            archived=bool(row["archived"]),
            created_at=row["created_at"], updated_at=row["updated_at"],
            metadata=json.loads(row["metadata"] or "{}"),
        )

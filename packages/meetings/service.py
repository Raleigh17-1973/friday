from __future__ import annotations
import json
import sqlite3
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4
from datetime import datetime


@dataclass
class ActionItem:
    item_id: str
    meeting_id: str
    description: str
    owner: str
    due_date: str
    status: str = "open"  # "open" | "done" | "blocked"
    org_id: str = "org-1"
    created_at: str = ""


@dataclass
class MeetingNote:
    note_id: str
    meeting_id: str
    raw_text: str          # Original notes/transcript
    structured_summary: str
    decisions_made: list[str]
    action_items: list[ActionItem]
    attendees: list[str]
    topics_discussed: list[str]
    org_id: str
    created_at: str


@dataclass
class Meeting:
    meeting_id: str
    title: str
    scheduled_at: str
    duration_minutes: int
    attendees: list[str]
    agenda: list[str]
    status: str = "scheduled"  # "scheduled" | "completed" | "cancelled"
    notes_id: str = ""
    org_id: str = "org-1"
    created_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class MeetingService:
    """Full meeting lifecycle: schedule → notes → action items → tickets."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or Path("data/meetings.db")
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS meetings (
                    meeting_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    scheduled_at TEXT NOT NULL,
                    duration_minutes INTEGER NOT NULL DEFAULT 60,
                    attendees TEXT NOT NULL DEFAULT '[]',
                    agenda TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT 'scheduled',
                    notes_id TEXT NOT NULL DEFAULT '',
                    org_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS meeting_notes (
                    note_id TEXT PRIMARY KEY,
                    meeting_id TEXT NOT NULL,
                    raw_text TEXT NOT NULL,
                    structured_summary TEXT NOT NULL DEFAULT '',
                    decisions_made TEXT NOT NULL DEFAULT '[]',
                    attendees TEXT NOT NULL DEFAULT '[]',
                    topics_discussed TEXT NOT NULL DEFAULT '[]',
                    org_id TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS action_items (
                    item_id TEXT PRIMARY KEY,
                    meeting_id TEXT NOT NULL,
                    description TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    due_date TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open',
                    org_id TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
            """)

    def create_meeting(self, title: str, scheduled_at: str, attendees: list[str],
                       agenda: list[str], duration_minutes: int = 60,
                       org_id: str = "org-1") -> Meeting:
        meeting = Meeting(
            meeting_id=f"mtg_{uuid4().hex[:12]}",
            title=title, scheduled_at=scheduled_at,
            duration_minutes=duration_minutes,
            attendees=attendees, agenda=agenda,
            org_id=org_id, created_at=datetime.utcnow().isoformat() + "Z",
        )
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO meetings VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (meeting.meeting_id, meeting.title, meeting.scheduled_at,
                 meeting.duration_minutes, json.dumps(meeting.attendees),
                 json.dumps(meeting.agenda), meeting.status, meeting.notes_id,
                 meeting.org_id, meeting.created_at, json.dumps(meeting.metadata))
            )
        return meeting

    def process_notes(self, meeting_id: str, raw_text: str,
                      org_id: str = "org-1") -> MeetingNote:
        """Parse raw meeting notes into structured format with action items."""
        # Extract action items using pattern matching
        action_items = self._extract_action_items(raw_text, meeting_id, org_id)

        # Extract decisions (lines with "decided", "agreed", "approved", "will")
        decisions = []
        for line in raw_text.split('\n'):
            line = line.strip()
            if any(kw in line.lower() for kw in ['decided', 'agreed', 'approved', 'resolved', 'confirmed']):
                if len(line) > 10:
                    decisions.append(line)

        # Extract topics (lines starting with # or ## or being short bold phrases)
        topics = []
        for line in raw_text.split('\n'):
            line = line.strip()
            if line.startswith('#'):
                topics.append(line.lstrip('#').strip())
            elif len(line) < 60 and line and not line.startswith('-') and not line.startswith('*'):
                topics.append(line)
        topics = topics[:10]

        # Build structured summary
        summary_parts = []
        if decisions:
            summary_parts.append(f"Decisions: {'; '.join(decisions[:3])}")
        if action_items:
            owners = list(set(a.owner for a in action_items if a.owner != "TBD"))
            summary_parts.append(f"{len(action_items)} action items assigned to: {', '.join(owners[:5])}")
        structured_summary = " | ".join(summary_parts) if summary_parts else raw_text[:200]

        note = MeetingNote(
            note_id=f"note_{uuid4().hex[:12]}",
            meeting_id=meeting_id,
            raw_text=raw_text,
            structured_summary=structured_summary,
            decisions_made=decisions[:10],
            action_items=action_items,
            attendees=[],
            topics_discussed=topics,
            org_id=org_id,
            created_at=datetime.utcnow().isoformat() + "Z",
        )

        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO meeting_notes VALUES (?,?,?,?,?,?,?,?,?)",
                (note.note_id, note.meeting_id, note.raw_text,
                 note.structured_summary, json.dumps(note.decisions_made),
                 json.dumps(note.attendees), json.dumps(note.topics_discussed),
                 note.org_id, note.created_at)
            )
            # Save action items
            for item in action_items:
                conn.execute(
                    "INSERT INTO action_items VALUES (?,?,?,?,?,?,?,?)",
                    (item.item_id, item.meeting_id, item.description,
                     item.owner, item.due_date, item.status, item.org_id, item.created_at)
                )
            # Update meeting status
            conn.execute(
                "UPDATE meetings SET status = 'completed', notes_id = ? WHERE meeting_id = ?",
                (note.note_id, meeting_id)
            )
        return note

    def _extract_action_items(self, text: str, meeting_id: str, org_id: str) -> list[ActionItem]:
        """Extract action items from meeting notes using pattern matching."""
        items = []
        patterns = [
            # "Action: [owner] will [do thing] by [date]"
            r'(?:action|todo|task|follow.?up)[:\s]+([^\n]{10,120})',
            # "- [ ] [owner]: [task]"
            r'\[\s*\]\s*([^\n]{10,100})',
            # "@name will [do thing]"
            r'@(\w+)\s+will\s+([^\n]{10,80})',
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                description = match.group(0).strip()
                if len(description) < 10:
                    continue

                # Try to extract owner from description
                owner = "TBD"
                owner_match = re.search(r'@(\w+)|(\w+)\s+will\b', description, re.IGNORECASE)
                if owner_match:
                    owner = (owner_match.group(1) or owner_match.group(2) or "TBD").strip()

                # Try to extract due date
                due_date = ""
                date_match = re.search(
                    r'by\s+(\d{4}-\d{2}-\d{2}|next\s+\w+|end\s+of\s+\w+|\w+\s+\d{1,2})',
                    description, re.IGNORECASE
                )
                if date_match:
                    due_date = date_match.group(1)

                if description not in [i.description for i in items]:
                    items.append(ActionItem(
                        item_id=f"ai_{uuid4().hex[:12]}",
                        meeting_id=meeting_id,
                        description=description[:200],
                        owner=owner,
                        due_date=due_date,
                        org_id=org_id,
                        created_at=datetime.utcnow().isoformat() + "Z",
                    ))
        return items[:20]  # cap at 20 items

    def list_meetings(self, org_id: str = "org-1", status: str | None = None,
                      limit: int = 20) -> list[Meeting]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            q = "SELECT * FROM meetings WHERE org_id = ?"
            params: list = [org_id]
            if status:
                q += " AND status = ?"
                params.append(status)
            q += " ORDER BY scheduled_at DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(q, params).fetchall()
        return [self._row_to_meeting(r) for r in rows]

    def list_action_items(self, org_id: str = "org-1", status: str = "open",
                          owner: str | None = None) -> list[ActionItem]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            q = "SELECT * FROM action_items WHERE org_id = ? AND status = ?"
            params: list = [org_id, status]
            if owner:
                q += " AND owner LIKE ?"
                params.append(f"%{owner}%")
            rows = conn.execute(q, params).fetchall()
        return [ActionItem(
            item_id=r["item_id"], meeting_id=r["meeting_id"],
            description=r["description"], owner=r["owner"],
            due_date=r["due_date"], status=r["status"],
            org_id=r["org_id"], created_at=r["created_at"],
        ) for r in rows]

    def complete_action_item(self, item_id: str) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("UPDATE action_items SET status = 'done' WHERE item_id = ?", (item_id,))

    def get_notes(self, meeting_id: str) -> MeetingNote | None:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM meeting_notes WHERE meeting_id = ?", (meeting_id,)
            ).fetchone()
        if not row:
            return None
        items = self.list_action_items_for_meeting(meeting_id, row["org_id"])
        return MeetingNote(
            note_id=row["note_id"], meeting_id=row["meeting_id"],
            raw_text=row["raw_text"], structured_summary=row["structured_summary"],
            decisions_made=json.loads(row["decisions_made"] or "[]"),
            action_items=items,
            attendees=json.loads(row["attendees"] or "[]"),
            topics_discussed=json.loads(row["topics_discussed"] or "[]"),
            org_id=row["org_id"], created_at=row["created_at"],
        )

    def list_action_items_for_meeting(self, meeting_id: str, org_id: str) -> list[ActionItem]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM action_items WHERE meeting_id = ?", (meeting_id,)
            ).fetchall()
        return [ActionItem(
            item_id=r["item_id"], meeting_id=r["meeting_id"],
            description=r["description"], owner=r["owner"],
            due_date=r["due_date"], status=r["status"],
            org_id=r["org_id"], created_at=r["created_at"],
        ) for r in rows]

    def _row_to_meeting(self, row) -> Meeting:
        return Meeting(
            meeting_id=row["meeting_id"], title=row["title"],
            scheduled_at=row["scheduled_at"],
            duration_minutes=row["duration_minutes"],
            attendees=json.loads(row["attendees"] or "[]"),
            agenda=json.loads(row["agenda"] or "[]"),
            status=row["status"], notes_id=row["notes_id"],
            org_id=row["org_id"], created_at=row["created_at"],
            metadata=json.loads(row["metadata"] or "{}"),
        )

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from datetime import datetime
from uuid import uuid4

@dataclass
class MeetingBrief:
    brief_id: str
    meeting_title: str
    meeting_time: str
    attendees: list[str]
    agenda_items: list[str]
    relevant_docs: list[dict]  # [{"title": ..., "url": ..., "type": ...}]
    prior_action_items: list[str]
    key_context: str  # synthesized background text
    suggested_objectives: list[str]
    org_id: str
    created_at: str

class MeetingBriefService:
    """Generates structured pre-meeting briefs."""

    def generate_brief(
        self,
        meeting_title: str,
        meeting_time: str,
        attendees: list[str],
        agenda_items: list[str],
        org_id: str = "org-1",
        context: dict[str, Any] | None = None,
    ) -> MeetingBrief:
        """Generate a meeting brief with agenda, prior items, and suggested objectives."""
        ctx = context or {}

        # Synthesize key context from available data
        key_context_parts = []
        if ctx.get("recent_decisions"):
            key_context_parts.append(f"Recent decisions: {'; '.join(ctx['recent_decisions'][:3])}")
        if ctx.get("open_action_items"):
            key_context_parts.append(f"Open items from prior meetings: {'; '.join(ctx['open_action_items'][:5])}")
        if ctx.get("relevant_metrics"):
            metrics = ctx["relevant_metrics"]
            key_context_parts.append(f"Key metrics: {'; '.join([f'{k}: {v}' for k, v in metrics.items()])}")

        key_context = "\n".join(key_context_parts) if key_context_parts else (
            f"Meeting: {meeting_title}\nAttendees: {', '.join(attendees)}"
        )

        # Generate suggested objectives based on agenda
        suggested_objectives = []
        for item in agenda_items:
            if "review" in item.lower():
                suggested_objectives.append(f"Align on status of: {item}")
            elif "decision" in item.lower() or "approve" in item.lower():
                suggested_objectives.append(f"Reach decision on: {item}")
            else:
                suggested_objectives.append(f"Clarify next steps for: {item}")

        if not suggested_objectives:
            suggested_objectives = [
                "Define clear action items with owners and deadlines",
                "Confirm alignment on priorities",
                "Surface any blockers or risks",
            ]

        return MeetingBrief(
            brief_id=f"brief_{uuid4().hex[:12]}",
            meeting_title=meeting_title,
            meeting_time=meeting_time,
            attendees=attendees,
            agenda_items=agenda_items,
            relevant_docs=ctx.get("relevant_docs", []),
            prior_action_items=ctx.get("open_action_items", []),
            key_context=key_context,
            suggested_objectives=suggested_objectives,
            org_id=org_id,
            created_at=datetime.utcnow().isoformat() + "Z",
        )

    def brief_to_markdown(self, brief: MeetingBrief) -> str:
        """Render a brief as a formatted markdown document."""
        lines = [
            f"# Meeting Brief: {brief.meeting_title}",
            f"**Time:** {brief.meeting_time}  |  **Attendees:** {', '.join(brief.attendees)}",
            "",
            "## Agenda",
        ]
        for i, item in enumerate(brief.agenda_items, 1):
            lines.append(f"{i}. {item}")

        if brief.prior_action_items:
            lines.extend(["", "## Open Action Items from Prior Meetings"])
            for item in brief.prior_action_items:
                lines.append(f"- [ ] {item}")

        if brief.key_context:
            lines.extend(["", "## Key Context", brief.key_context])

        if brief.relevant_docs:
            lines.extend(["", "## Relevant Documents"])
            for doc in brief.relevant_docs:
                lines.append(f"- [{doc.get('title', 'Untitled')}]({doc.get('url', '#')})")

        lines.extend(["", "## Suggested Meeting Objectives"])
        for obj in brief.suggested_objectives:
            lines.append(f"- {obj}")

        return "\n".join(lines)

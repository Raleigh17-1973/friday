from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from datetime import datetime
from uuid import uuid4

@dataclass
class WeeklyDigest:
    digest_id: str
    week_ending: str
    org_id: str
    kpi_summary: list[dict]   # [{"name": ..., "value": ..., "vs_target": ..., "trend": ...}]
    okr_highlights: list[dict]  # [{"title": ..., "progress": ..., "status": ...}]
    alerts_summary: dict        # {"critical": N, "warning": N, "info": N}
    decisions_made: list[str]
    top_risks: list[str]
    wins: list[str]
    next_week_focus: list[str]
    created_at: str

class DigestService:
    """Generates weekly and periodic operational digests."""

    def generate_weekly(
        self,
        kpis: list[dict],
        objectives: list[dict],
        alerts: list[dict],
        decisions: list[dict],
        org_id: str = "org-1",
    ) -> WeeklyDigest:
        # Summarize KPIs
        kpi_summary = []
        for kpi in kpis[:8]:
            current = kpi.get("current_value", 0)
            target = kpi.get("target_value", 1)
            vs_target = f"{(current/target*100):.0f}%" if target else "N/A"
            kpi_summary.append({
                "name": kpi.get("name", ""),
                "value": f"{current} {kpi.get('unit', '')}".strip(),
                "vs_target": vs_target,
                "status": kpi.get("status", "unknown"),
            })

        # Highlight OKRs
        okr_highlights = []
        for obj in objectives[:5]:
            okr_highlights.append({
                "title": obj.get("title", ""),
                "progress": f"{obj.get('progress_pct', 0):.0f}%",
                "status": obj.get("status", "in_progress"),
            })

        # Alert counts
        alert_counts = {"critical": 0, "warning": 0, "info": 0}
        for a in alerts:
            sev = a.get("severity", "info")
            if sev in alert_counts:
                alert_counts[sev] += 1

        # Extract decisions text
        decisions_made = [d.get("title", "") for d in decisions[:5]]

        # Build top risks from critical alerts
        top_risks = [a.get("title", "") for a in alerts if a.get("severity") == "critical"][:3]

        return WeeklyDigest(
            digest_id=f"digest_{uuid4().hex[:12]}",
            week_ending=datetime.utcnow().isoformat()[:10],
            org_id=org_id,
            kpi_summary=kpi_summary,
            okr_highlights=okr_highlights,
            alerts_summary=alert_counts,
            decisions_made=decisions_made,
            top_risks=top_risks,
            wins=[f"OKR on track: {o['title']}" for o in objectives if o.get("status") == "on_track"][:3],
            next_week_focus=top_risks[:3] if top_risks else ["Review OKR progress"],
            created_at=datetime.utcnow().isoformat() + "Z",
        )

    def digest_to_markdown(self, digest: WeeklyDigest) -> str:
        lines = [
            f"# Weekly Digest — Week Ending {digest.week_ending}",
            "",
            "## KPI Dashboard",
            "| Metric | Value | vs Target | Status |",
            "|--------|-------|-----------|--------|",
        ]
        for kpi in digest.kpi_summary:
            lines.append(f"| {kpi['name']} | {kpi['value']} | {kpi['vs_target']} | {kpi['status']} |")

        lines.extend(["", "## OKR Progress"])
        for okr in digest.okr_highlights:
            lines.append(f"- **{okr['title']}**: {okr['progress']} ({okr['status']})")

        if digest.wins:
            lines.extend(["", "## 🎉 Wins This Week"])
            for win in digest.wins:
                lines.append(f"- {win}")

        if digest.top_risks:
            lines.extend(["", "## ⚠️ Top Risks"])
            for risk in digest.top_risks:
                lines.append(f"- {risk}")

        alert_s = digest.alerts_summary
        lines.extend(["", f"**Alerts:** {alert_s.get('critical', 0)} critical · {alert_s.get('warning', 0)} warning · {alert_s.get('info', 0)} info"])

        if digest.next_week_focus:
            lines.extend(["", "## Next Week Focus"])
            for focus in digest.next_week_focus:
                lines.append(f"- {focus}")

        return "\n".join(lines)

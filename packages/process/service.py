from __future__ import annotations

import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

from packages.common.models import ApprovalRequest, ProcessDocument, ProcessStep, utc_now_iso
from packages.governance.approvals import ApprovalService
from packages.governance.policy import PolicyEngine
from packages.process.repository import SQLiteProcessRepository


def _build_mermaid(doc: ProcessDocument) -> str:
    """Generate a Mermaid graph TD flowchart from a ProcessDocument's steps and decision_points."""
    lines: list[str] = ["graph TD"]

    # Build a lookup: step id → node id (s1, s2, ...)
    step_node: dict[str, str] = {}
    for i, step in enumerate(doc.steps):
        node_id = f"s{i + 1}"
        step_node[step.id] = node_id if step.id else node_id

    trigger_text = (doc.trigger or "Process starts")[:50].replace('"', "'")
    lines.append(f'    START(["{trigger_text}"]) --> s1')

    for i, step in enumerate(doc.steps):
        node_id = f"s{i + 1}"
        step_label = (step.name or f"Step {i + 1}")[:40].replace('"', "'")
        if step.owner:
            owner_str = step.owner[:25].replace('"', "'")
            label = f"{step_label}\\n{owner_str}"
        else:
            label = step_label
        lines.append(f'    {node_id}["{label}"]')

    # Decision points — wire them in as {condition?} gateways if they reference step ids
    decision_nodes: list[str] = []
    for j, dp in enumerate(doc.decision_points or []):
        cond = (dp.get("condition") or f"Decision {j + 1}")[:40].replace('"', "'")
        d_node = f"d{j + 1}"
        lines.append(f'    {d_node}{{"{cond}?"}}')
        paths: dict[str, str] = dp.get("paths") or {}
        for label, target in paths.items():
            # target may be a step id or free text
            target_node = step_node.get(target, f"s{target}" if target.isdigit() else None)
            if target_node:
                lines.append(f'    {d_node} -->|{label}| {target_node}')
        decision_nodes.append(d_node)

    # Simple sequential connections between steps
    for i in range(len(doc.steps) - 1):
        lines.append(f'    s{i + 1} --> s{i + 2}')

    # Last step → END
    last = f"s{len(doc.steps)}" if doc.steps else "START"
    lines.append(f'    {last} --> END(["Process Complete"])')

    return "\n".join(lines)


def _bump_version(version: str, bump: str) -> str:
    """Increment a semver string. bump = 'major' | 'minor' | 'patch'."""
    parts = version.split(".")
    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def _completeness_score(doc: ProcessDocument) -> float:
    """Score 0.0–1.0 based on how many key fields are populated."""
    checks = [
        bool(doc.trigger),
        len(doc.steps) >= 3,
        len(doc.decision_points) >= 1,
        len(doc.roles) >= 1,
        len(doc.kpis) >= 1,
        len(doc.exceptions) >= 1,
    ]
    return round(sum(checks) / len(checks), 2)


class ProcessService:
    """CRUD + versioning for ProcessDocument objects."""

    def __init__(
        self,
        db_path: Path | None = None,
        approval_service: ApprovalService | None = None,
    ) -> None:
        self._repo = SQLiteProcessRepository(db_path=db_path)
        self._approvals = approval_service
        self._policy = PolicyEngine()

    # ── create ────────────────────────────────────────────────────────────────

    def create(self, doc: ProcessDocument) -> ProcessDocument:
        if not doc.id:
            doc.id = f"proc_{uuid.uuid4().hex[:12]}"
        doc.completeness_score = _completeness_score(doc)
        return self._repo.create(doc)

    # ── read ──────────────────────────────────────────────────────────────────

    def get(self, process_id: str) -> ProcessDocument | None:
        return self._repo.get_latest(process_id)

    def get_version(self, process_id: str, version: str) -> ProcessDocument | None:
        return self._repo.get_version(process_id, version)

    def list(self, org_id: str = "org-1") -> list[ProcessDocument]:
        return self._repo.list_by_org(org_id)

    def history(self, process_id: str) -> list[dict[str, Any]]:
        return self._repo.list_versions(process_id)

    # ── update ────────────────────────────────────────────────────────────────

    def update(
        self,
        process_id: str,
        changes: dict[str, Any],
        bump: str = "patch",
        author: str = "user",
        changelog_entry: str = "",
    ) -> ProcessDocument | dict[str, Any]:
        """Apply changes dict to the latest version, create a new version row.

        If bump == "major" and an ApprovalService is configured, the update is
        held pending approval. Returns a dict with status="pending_approval" in
        that case; otherwise returns the updated ProcessDocument.
        """
        doc = self._repo.get_latest(process_id)
        if doc is None:
            raise KeyError(f"Process {process_id!r} not found")

        # Check policy for this bump type
        decision = self._policy.evaluate_process_version_bump(bump=bump)
        if decision.requires_approval and self._approvals is not None:
            old_version = doc.version
            new_version = _bump_version(old_version, bump)
            approval = ApprovalRequest(
                approval_id=f"appr_{uuid.uuid4().hex[:12]}",
                run_id=process_id,
                reason=f"Major version bump: {doc.process_name} {old_version} → {new_version}",
                action_summary=(
                    f"Process '{doc.process_name}' major version bump {old_version} → {new_version}. "
                    f"Author: {author}. Changes: {changelog_entry or 'see payload'}"
                ),
                requested_scopes=["process.write"],
            )
            self._approvals.create(approval)
            return {
                "status": "pending_approval",
                "approval_id": approval.approval_id,
                "process_id": process_id,
                "old_version": old_version,
                "new_version": new_version,
                "message": "Major version bump requires approval. Approve via the Approvals panel.",
            }

        # Apply scalar fields
        for key in ("process_name", "trigger", "status", "mermaid_flowchart", "mermaid_swimlane"):
            if key in changes:
                setattr(doc, key, changes[key])

        # Apply list fields
        for key in ("roles", "tools", "kpis", "exceptions", "decision_points"):
            if key in changes:
                setattr(doc, key, changes[key])

        # Apply steps (accepts list of dicts or ProcessStep objects)
        if "steps" in changes:
            doc.steps = [
                ProcessStep(**s) if isinstance(s, dict) else s
                for s in changes["steps"]
            ]

        doc.version = _bump_version(doc.version, bump)
        doc.completeness_score = _completeness_score(doc)

        entry = changelog_entry or f"Updated via API (bump={bump})"
        return self._repo.save_version(doc, entry, author)

    # ── delete ────────────────────────────────────────────────────────────────

    def delete(self, process_id: str) -> None:
        self._repo.soft_delete(process_id)

    # ── diagram generation ────────────────────────────────────────────────────

    def generate_mermaid(self, process_id: str) -> dict[str, str]:
        """Return {"mermaid": "...", "source": "stored"|"generated"}.

        Uses the stored mermaid_flowchart if present; otherwise auto-generates
        one from the structured steps and decision_points.
        """
        doc = self._repo.get_latest(process_id)
        if doc is None:
            raise KeyError(f"Process {process_id!r} not found")
        if doc.mermaid_flowchart:
            return {"mermaid": doc.mermaid_flowchart, "source": "stored"}
        if not doc.steps:
            return {"mermaid": "", "source": "none"}
        return {"mermaid": _build_mermaid(doc), "source": "generated"}

    # ── execution tracking ────────────────────────────────────────────────────

    def start_execution(self, process_id: str, actor: str = "user") -> dict[str, Any]:
        """Create a new in-progress execution run for a process."""
        doc = self._repo.get_latest(process_id)
        if doc is None:
            raise KeyError(f"Process {process_id!r} not found")
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        run = self._repo.create_execution_run(run_id, process_id, actor)
        run["total_steps"] = len(doc.steps)
        if doc.steps:
            run["current_step_name"] = doc.steps[0].name
        return run

    def advance_step(self, run_id: str) -> dict[str, Any]:
        """Advance the execution run to the next step."""
        run = self._repo.get_execution_run(run_id)
        if run is None:
            raise KeyError(f"Execution run {run_id!r} not found")
        if run["status"] != "in_progress":
            raise ValueError(f"Run {run_id!r} is not in_progress (status={run['status']})")
        doc = self._repo.get_latest(run["process_id"])
        next_idx = run["current_step_index"] + 1
        if doc and next_idx >= len(doc.steps):
            # Auto-complete when advancing past last step
            return self.complete_execution(run_id)
        updated = self._repo.update_execution_run(run_id, current_step_index=next_idx) or {}
        if doc and next_idx < len(doc.steps):
            updated["current_step_name"] = doc.steps[next_idx].name
        updated["total_steps"] = len(doc.steps) if doc else 0
        return updated

    def complete_execution(self, run_id: str) -> dict[str, Any]:
        """Mark an execution run as completed."""
        run = self._repo.get_execution_run(run_id)
        if run is None:
            raise KeyError(f"Execution run {run_id!r} not found")
        updated = self._repo.update_execution_run(
            run_id, status="completed", completed_at=utc_now_iso()
        ) or {}
        return updated

    def list_executions(self, process_id: str) -> list[dict[str, Any]]:
        """List all execution runs for a process, newest first."""
        doc = self._repo.get_latest(process_id)
        total = len(doc.steps) if doc else 0
        runs = self._repo.list_execution_runs(process_id)
        for r in runs:
            r["total_steps"] = total
        return runs

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def completeness_breakdown(doc: ProcessDocument) -> dict[str, Any]:
        """Return per-field completeness with gap recommendations."""
        fields = {
            "trigger":          (bool(doc.trigger), "Add a trigger — what event starts this process?"),
            "steps (≥3)":       (len(doc.steps) >= 3, f"Add more steps — currently {len(doc.steps)}, need at least 3"),
            "decision_points":  (len(doc.decision_points) >= 1, "Add at least one decision point / branching condition"),
            "roles":            (len(doc.roles) >= 1, "Identify at least one role or team owner"),
            "kpis":             (len(doc.kpis) >= 1, "Add success metrics or SLA targets"),
            "exceptions":       (len(doc.exceptions) >= 1, "Document what happens when something goes wrong"),
        }
        populated = sum(1 for ok, _ in fields.values() if ok)
        return {
            "score": round(populated / len(fields), 2),
            "fields": {
                name: {"ok": ok, "recommendation": rec if not ok else None}
                for name, (ok, rec) in fields.items()
            },
        }

    @staticmethod
    def to_dict(doc: ProcessDocument) -> dict[str, Any]:
        return doc.to_dict()

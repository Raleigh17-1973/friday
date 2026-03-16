from __future__ import annotations

import os
from functools import cached_property
from pathlib import Path

from packages.agents.registry import AgentRegistry
from packages.governance.approvals import ApprovalService
from packages.governance.audit import AuditLog
from packages.governance.policy import PolicyEngine
from packages.governance.run_store import PostgresRunStore, SQLiteRunStore
from packages.memory.service import LayeredMemoryService
from packages.process.service import ProcessService
from packages.process.repository import SQLiteProcessRepository
from packages.storage import FileStorageService
from packages.credentials import CredentialService
from packages.templates import TemplateService
from packages.analytics import KPIService
from packages.okrs import OKRService
from packages.workspaces import WorkspaceService
from packages.projects.service import ProjectService
from packages.brand import BrandAssetService
from packages.conversations.service import ConversationService
from packages.tasks import TaskService
from packages.notifications import NotificationService
from packages.activity import ActivityService
from packages.tools.mcp import MCPRegistry
from packages.tools.policy_wrapped_tools import ToolExecutor
from packages.tools.registry import ToolRegistry
from packages.llm.factory import create_llm_provider
from workers.orchestrator.runtime import FridayManager
from workers.orchestrator.workflows import InProcessWorkflowEngine, TemporalWorkflowEngine


class FridayService:
    def __init__(self) -> None:
        self.root = Path(__file__).resolve().parents[2]
        manifests_dir = self.root / "packages" / "agents" / "manifests"
        self._memory_db = self.root / "data" / "friday_memory.sqlite3"
        self._workflow_db = self.root / "data" / "friday_workflows.sqlite3"
        self._audit_db = self.root / "data" / "friday_audit.sqlite3"
        self._mcp_registry_file = self.root / "data" / "mcp_servers.json"

        # ------------------------------------------------------------------ #
        # CORE services — always eagerly initialised; used on every request   #
        # ------------------------------------------------------------------ #
        self.registry = AgentRegistry(manifests_dir=manifests_dir)

        memory_dsn = os.getenv("FRIDAY_MEMORY_DATABASE_URL", "").strip()
        self.memory = (
            LayeredMemoryService.with_postgres(memory_dsn)
            if memory_dsn
            else LayeredMemoryService.with_sqlite(self._memory_db)
        )

        self.policy = PolicyEngine()
        self.mcp = MCPRegistry(self._mcp_registry_file)
        self.tools = ToolRegistry(self.mcp)

        approvals_db = self.root / "data" / "friday_approvals.sqlite3"
        self.approvals = ApprovalService(db_path=approvals_db)

        process_db = self.root / "data" / "friday_processes.sqlite3"
        self.processes = ProcessService(db_path=process_db, approval_service=self.approvals)

        audit_dsn = os.getenv("FRIDAY_AUDIT_DATABASE_URL", "").strip()
        _run_store = PostgresRunStore(audit_dsn) if audit_dsn else SQLiteRunStore(self._audit_db)
        self.audit = AuditLog(run_store=_run_store)

        self.llm = create_llm_provider()
        self.manager = FridayManager(
            registry=self.registry,
            memory=self.memory,
            policy=self.policy,
            approvals=self.approvals,
            audit=self.audit,
            tool_executor=ToolExecutor(self.root),
            llm=self.llm,
        )

        workflow_engine = os.getenv("FRIDAY_WORKFLOW_ENGINE", "inprocess").strip().lower()
        if workflow_engine == "temporal":
            self.workflow = TemporalWorkflowEngine(
                address=os.getenv("TEMPORAL_ADDRESS", "localhost:7233"),
                namespace=os.getenv("TEMPORAL_NAMESPACE", "default"),
                task_queue=os.getenv("TEMPORAL_TASK_QUEUE", "friday-runs"),
            )
        else:
            self.workflow = InProcessWorkflowEngine(self._workflow_db)

        # File storage
        storage_dir = self.root / "data" / "files"
        storage_db = self.root / "data" / "friday_files.sqlite3"
        self.storage = FileStorageService(storage_dir=storage_dir, db_path=storage_db)

        credentials_db = self.root / "data" / "friday_credentials.sqlite3"
        self.credentials = CredentialService(db_path=credentials_db)

        templates_db = self.root / "data" / "friday_templates.sqlite3"
        seed_dir = self.root / "data" / "templates"
        self.templates = TemplateService(db_path=templates_db, seed_dir=seed_dir)

        analytics_db = self.root / "data" / "friday_analytics.sqlite3"
        self.kpis = KPIService(db_path=analytics_db)

        okr_db = self.root / "data" / "friday_okrs.sqlite3"
        self.okrs = OKRService(db_path=okr_db)

        workspace_db = self.root / "data" / "workspaces.db"
        self.workspaces = WorkspaceService(db_path=workspace_db)

        projects_db = self.root / "data" / "friday_projects.sqlite3"
        self.projects = ProjectService(db_path=projects_db)

        brand_db = self.root / "data" / "friday_brand.sqlite3"
        self.brand = BrandAssetService(db_path=brand_db)

        conv_db = self.root / "data" / "friday_conversations.sqlite3"
        self.conversations = ConversationService(db_path=conv_db)

        tasks_db = self.root / "data" / "friday_tasks.sqlite3"
        self.tasks = TaskService(db_path=tasks_db)

        notifications_db = self.root / "data" / "friday_notifications.sqlite3"
        self.notifications = NotificationService(db_path=notifications_db)

        activity_db = self.root / "data" / "friday_activity.sqlite3"
        self.activity = ActivityService(db_path=activity_db)

        # Start the scheduler eagerly (it self-stubs when APScheduler is absent)
        from packages.scheduler.service import SchedulerService, register_default_jobs
        self.scheduler = SchedulerService()
        try:
            register_default_jobs(self.scheduler, self)
            self.scheduler.start()
        except Exception:
            pass  # Never block startup if scheduler setup fails

        # ------------------------------------------------------------------ #
        # LAZY services — @cached_property, initialised only on first access  #
        # ------------------------------------------------------------------ #
        # (defined below as @cached_property methods)

    # ---------------------------------------------------------------------- #
    # Lazy-loaded domain services                                              #
    # ---------------------------------------------------------------------- #

    @cached_property
    def process_analytics(self):
        from packages.process.analytics import ProcessAnalytics
        _repo = SQLiteProcessRepository(
            db_path=self.root / "data" / "friday_processes.sqlite3"
        )
        return ProcessAnalytics(repo=_repo)

    @cached_property
    def eval_harness(self):
        from workers.evals.harness import EvalHarness
        return EvalHarness(self.root)

    @cached_property
    def reflection(self):
        from workers.reflection.worker import ReflectionWorker
        return ReflectionWorker()

    @cached_property
    def docgen(self):
        """Returns a DocGenService instance, or None if the package is not installed."""
        try:
            from packages.docgen import DocGenService
            return DocGenService(storage=self.storage)
        except Exception:
            return None

    @cached_property
    def charts(self):
        from packages.analytics import ChartService
        return ChartService()

    @cached_property
    def qa(self):
        from packages.qa import QAService
        qa_db = self.root / "data" / "friday_qa.sqlite3"
        return QAService(db_path=qa_db)

    @cached_property
    def invoices(self):
        from packages.finance import InvoiceService
        finance_db = self.root / "data" / "friday_finance.sqlite3"
        return InvoiceService(db_path=finance_db)

    @cached_property
    def budgets(self):
        from packages.finance import BudgetService
        finance_db = self.root / "data" / "friday_finance.sqlite3"
        return BudgetService(db_path=finance_db)

    @cached_property
    def modeling(self):
        from packages.finance import FinancialModelingService
        return FinancialModelingService()

    @cached_property
    def events(self):
        from packages.events import EventBus
        return EventBus()

    @cached_property
    def interpreter(self):
        from packages.interpreter import CodeInterpreterService
        return CodeInterpreterService(storage=self.storage)

    @cached_property
    def scanner(self):
        from packages.proactive import ProactiveScanner
        proactive_db = self.root / "data" / "friday_proactive.sqlite3"
        return ProactiveScanner(db_path=proactive_db)

    @cached_property
    def briefs(self):
        from packages.proactive import MeetingBriefService
        return MeetingBriefService()

    @cached_property
    def digest(self):
        from packages.proactive import DigestService
        return DigestService()

    @cached_property
    def org_context(self):
        from packages.org_context import OrgContextService
        org_context_db = self.root / "data" / "friday_org_context.sqlite3"
        return OrgContextService(db_path=org_context_db)

    @cached_property
    def meetings(self):
        from packages.meetings import MeetingService
        meetings_db = self.root / "data" / "friday_meetings.sqlite3"
        return MeetingService(db_path=meetings_db)

    @cached_property
    def decisions(self):
        from packages.decisions import DecisionLogService
        decisions_db = self.root / "data" / "friday_decisions.sqlite3"
        return DecisionLogService(db_path=decisions_db)

    @cached_property
    def voice(self):
        from packages.voice import VoiceTranscriptionService
        return VoiceTranscriptionService()

    # ---------------------------------------------------------------------- #
    # Business logic helpers                                                   #
    # ---------------------------------------------------------------------- #

    def execute_chat_payload(self, payload: dict, upload_store: dict | None = None) -> dict:
        from packages.common.models import ChatRequest

        message = str(payload.get("message") or "").strip()
        if not message:
            raise ValueError("message is required")

        # Inject uploaded file context blocks if context_ids were supplied
        context_ids: list[str] = payload.get("context_ids") or []
        if context_ids and upload_store:
            context_blocks: list[str] = []
            for cid in context_ids:
                entry = upload_store.get(cid)
                if entry:
                    context_blocks.append(
                        f"[Attached file: {entry['filename']} ({entry['type']})]\n{entry['text'][:8000]}"
                    )
            if context_blocks:
                message = "\n\n---\n".join(context_blocks) + "\n\n---\nUser request: " + message

        request = ChatRequest(
            user_id=str(payload.get("user_id") or "user-1"),
            org_id=str(payload.get("org_id") or "org-1"),
            conversation_id=str(payload.get("conversation_id") or "conv-1"),
            message=message,
            context_packet=payload.get("context_packet") or {},
            workspace_id=payload.get("workspace_id") or None,
        )
        response = self.manager.run(request)
        trace = self.audit.get_run(response["run_id"])
        if trace is not None:
            response["reflection"] = self.reflection.reflect(trace, self.memory).to_dict()

        # Doc generation hook
        self._maybe_generate_document(request.message, request.org_id, response)

        # Ensure top-level "response" key for backward compatibility with static UI
        if "response" not in response:
            response["response"] = (response.get("final_answer") or {}).get("direct_answer", "")
        return response

    # ---------------------------------------------------------------------- #
    # Document generation helpers                                              #
    # ---------------------------------------------------------------------- #

    _FORMAT_KEYWORDS: dict[str, list[str]] = {
        "docx": ["word doc", "word document", ".docx", "microsoft word", "word file"],
        "pptx": ["powerpoint", "pptx", "slide deck", "slides", "presentation", "deck"],
        "xlsx": ["excel", "spreadsheet", "xlsx", ".xls", "worksheet"],
        "pdf":  ["pdf", "portable document"],
    }

    def _detect_format(self, message: str) -> str | None:
        lower = message.lower()
        for fmt, keywords in self._FORMAT_KEYWORDS.items():
            if any(kw in lower for kw in keywords):
                return fmt
        return None

    def _maybe_generate_document(self, message: str, org_id: str, response: dict) -> None:
        if self.docgen is None:
            return
        planner = response.get("planner") or {}
        if planner.get("output_format") != "full_deliverable":
            return
        fmt = self._detect_format(message)
        if not fmt:
            return

        final_answer = response.get("final_answer") or {}
        content_text = final_answer.get("direct_answer", "")
        if not content_text:
            return

        if final_answer.get("artifacts", {}).get("document"):
            return

        try:
            from packages.docgen.generators.base import DocumentContent, DocumentSection
            import re as _re

            raw_sections = _re.split(r"^## ", content_text, flags=_re.MULTILINE)
            sections: list[DocumentSection] = []
            title = (planner.get("problem_statement") or "Document")[:80]

            for chunk in raw_sections:
                if not chunk.strip():
                    continue
                lines = chunk.split("\n", 1)
                heading = lines[0].strip()
                body = lines[1].strip() if len(lines) > 1 else ""

                table: list[list[str]] | None = None
                table_lines = [l for l in body.splitlines() if l.strip().startswith("|")]
                if table_lines:
                    rows = []
                    for tl in table_lines:
                        if _re.match(r"^\|[-|\s]+\|$", tl.strip()):
                            continue
                        cells = [c.strip() for c in tl.strip().strip("|").split("|")]
                        rows.append(cells)
                    if rows:
                        table = rows

                notes = ""
                notes_match = _re.search(r"---\s*NOTES:\s*(.+)", body, _re.IGNORECASE | _re.DOTALL)
                if notes_match:
                    notes = notes_match.group(1).strip()
                    body = body[: notes_match.start()].strip()

                if not sections:
                    title = heading

                sections.append(DocumentSection(
                    heading=heading,
                    body=body,
                    level=1,
                    table=table,
                    slide_notes=notes,
                ))

            if not sections:
                sections = [DocumentSection(heading="Document", body=content_text, level=1)]

            doc_type = {
                "docx": "report",
                "pptx": "deck",
                "xlsx": "spreadsheet",
                "pdf": "report",
            }.get(fmt, "report")

            content = DocumentContent(
                title=title,
                document_type=doc_type,
                sections=sections,
                metadata={"org_id": org_id, "generated_by": "friday"},
            )
            stored = self.docgen.generate(content, format=fmt, org_id=org_id)

            final_answer.setdefault("artifacts", {})["document"] = stored.file_id
            response["generated_document"] = {
                "file_id": stored.file_id,
                "filename": stored.filename,
                "mime_type": stored.mime_type,
                "size_bytes": stored.size_bytes,
                "format": fmt,
                "download_url": f"/files/{stored.file_id}",
            }
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("Doc generation failed: %s", exc)

    def get_dashboard_metrics(self) -> dict:
        agents = self.registry.list_active()
        mcp_servers = self.mcp.list_servers()
        workflows = {"engine": self.workflow.__class__.__name__}
        return {
            "active_agents": len(agents),
            "mcp_servers_total": len(mcp_servers),
            "mcp_servers_enabled": len([s for s in mcp_servers if s.enabled]),
            "tool_count": len(self.tools.list_tools()),
            "workflow": workflows,
        }

from __future__ import annotations

import os
from pathlib import Path

from packages.agents.registry import AgentRegistry
from packages.governance.approvals import ApprovalService
from packages.governance.audit import AuditLog
from packages.governance.policy import PolicyEngine
from packages.governance.run_store import PostgresRunStore, SQLiteRunStore
from packages.memory.service import LayeredMemoryService
from packages.process.service import ProcessService
from packages.process.analytics import ProcessAnalytics
from packages.process.repository import SQLiteProcessRepository
from packages.storage import FileStorageService
from packages.credentials import CredentialService
from packages.templates import TemplateService
from packages.analytics import KPIService, ChartService
from packages.okrs import OKRService
from packages.finance import InvoiceService, BudgetService
from packages.brand import BrandAssetService
from packages.events import EventBus
from packages.tools.mcp import MCPRegistry
from packages.tools.policy_wrapped_tools import ToolExecutor
from packages.tools.registry import ToolRegistry
from packages.llm.factory import create_llm_provider
from workers.evals.harness import EvalHarness
from workers.orchestrator.runtime import FridayManager
from workers.orchestrator.workflows import InProcessWorkflowEngine, TemporalWorkflowEngine
from workers.reflection.worker import ReflectionWorker


class FridayService:
    def __init__(self) -> None:
        self.root = Path(__file__).resolve().parents[2]
        manifests_dir = self.root / "packages" / "agents" / "manifests"
        memory_db = self.root / "data" / "friday_memory.sqlite3"
        workflow_db = self.root / "data" / "friday_workflows.sqlite3"
        audit_db = self.root / "data" / "friday_audit.sqlite3"
        mcp_registry_file = self.root / "data" / "mcp_servers.json"
        audit_dsn = os.getenv("FRIDAY_AUDIT_DATABASE_URL", "").strip()
        workflow_engine = os.getenv("FRIDAY_WORKFLOW_ENGINE", "inprocess").strip().lower()
        self.registry = AgentRegistry(manifests_dir=manifests_dir)
        memory_dsn = os.getenv("FRIDAY_MEMORY_DATABASE_URL", "").strip()
        self.memory = (
            LayeredMemoryService.with_postgres(memory_dsn)
            if memory_dsn
            else LayeredMemoryService.with_sqlite(memory_db)
        )
        self.policy = PolicyEngine()
        self.mcp = MCPRegistry(mcp_registry_file)
        self.tools = ToolRegistry(self.mcp)
        approvals_db = self.root / "data" / "friday_approvals.sqlite3"
        self.approvals = ApprovalService(db_path=approvals_db)
        process_db = self.root / "data" / "friday_processes.sqlite3"
        _process_repo = SQLiteProcessRepository(db_path=process_db)
        self.processes = ProcessService(db_path=process_db, approval_service=self.approvals)
        self.process_analytics = ProcessAnalytics(repo=_process_repo)
        run_store = PostgresRunStore(audit_dsn) if audit_dsn else SQLiteRunStore(audit_db)
        self.audit = AuditLog(run_store=run_store)
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
        if workflow_engine == "temporal":
            self.workflow = TemporalWorkflowEngine(
                address=os.getenv("TEMPORAL_ADDRESS", "localhost:7233"),
                namespace=os.getenv("TEMPORAL_NAMESPACE", "default"),
                task_queue=os.getenv("TEMPORAL_TASK_QUEUE", "friday-runs"),
            )
        else:
            self.workflow = InProcessWorkflowEngine(workflow_db)
        self.eval_harness = EvalHarness(self.root)
        self.reflection = ReflectionWorker()

        # Phase 0 infrastructure
        storage_dir = self.root / "data" / "files"
        storage_db = self.root / "data" / "friday_files.sqlite3"
        self.storage = FileStorageService(storage_dir=storage_dir, db_path=storage_db)

        credentials_db = self.root / "data" / "friday_credentials.sqlite3"
        self.credentials = CredentialService(db_path=credentials_db)

        templates_db = self.root / "data" / "friday_templates.sqlite3"
        seed_dir = self.root / "data" / "templates"
        self.templates = TemplateService(db_path=templates_db, seed_dir=seed_dir)

        # DocGenService wired after background agents create it
        self.docgen = None
        try:
            from packages.docgen import DocGenService
            self.docgen = DocGenService(storage=self.storage)
        except Exception:
            pass

        # Phase 4: Analytics
        analytics_db = self.root / "data" / "friday_analytics.sqlite3"
        self.kpis = KPIService(db_path=analytics_db)
        self.charts = ChartService()

        # Phase 5: OKRs
        okr_db = self.root / "data" / "friday_okrs.sqlite3"
        self.okrs = OKRService(db_path=okr_db)

        # Phase 6: Brand
        brand_db = self.root / "data" / "friday_brand.sqlite3"
        self.brand = BrandAssetService(db_path=brand_db)

        # Phase 7: Finance
        finance_db = self.root / "data" / "friday_finance.sqlite3"
        self.invoices = InvoiceService(db_path=finance_db)
        self.budgets = BudgetService(db_path=finance_db)

        # Phase 8: Events
        self.events = EventBus()

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
        )
        response = self.manager.run(request)
        trace = self.audit.get_run(response["run_id"])
        if trace is not None:
            response["reflection"] = self.reflection.reflect(trace, self.memory).to_dict()
        # Ensure top-level "response" key for backward compatibility with static UI
        if "response" not in response:
            response["response"] = (response.get("final_answer") or {}).get("direct_answer", "")
        return response

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

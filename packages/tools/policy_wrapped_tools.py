from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen


@dataclass
class ToolCall:
    tool_name: str
    mode: str
    idempotency_key: str | None
    args: dict[str, Any]


@dataclass
class ToolResult:
    tool_name: str
    ok: bool
    output: dict[str, Any]
    error: str | None = None


class ToolExecutor:
    def __init__(self, repo_root: Path) -> None:
        self._repo_root = repo_root
        self._resource_catalog_path = self._repo_root / "data" / "resource_catalog.json"
        self._text_cache: dict[str, tuple[int, str]] = {}
        self._pdf_cache: dict[str, tuple[int, list[str]]] = {}

    def run(self, tool_name: str, args: dict[str, Any]) -> ToolResult:
        if tool_name == "web.research":
            return self._web_research(args)
        if tool_name == "docs.retrieve":
            return self._docs_retrieve(args)

        # Phase 1: Document generation
        if tool_name == "docs.generate":
            return self._docs_generate(args)
        if tool_name in ("templates.list", "templates.read"):
            return self._templates_tool(tool_name, args)

        # Phase 2: Google Workspace (stubs)
        if tool_name.startswith("google."):
            return self._google_stub(tool_name, args)

        # Phase 3: Email, Calendar, Slack (stubs)
        if tool_name.startswith("email."):
            return self._email_stub(tool_name, args)
        if tool_name.startswith("calendar."):
            return self._calendar_stub(tool_name, args)
        if tool_name.startswith("slack."):
            return self._slack_stub(tool_name, args)

        # Phase 4: Analytics
        if tool_name.startswith("analytics."):
            return self._analytics_tool(tool_name, args)

        # Phase 5: Jira, Linear, OKRs (stubs)
        if tool_name.startswith("jira."):
            return self._integration_stub(tool_name, args, "Jira")
        if tool_name.startswith("linear."):
            return self._integration_stub(tool_name, args, "Linear")
        if tool_name.startswith("okrs."):
            return self._okrs_tool(tool_name, args)

        # Phase 6: Knowledge & Brand (stubs)
        if tool_name.startswith("confluence."):
            return self._integration_stub(tool_name, args, "Confluence")
        if tool_name.startswith("notion."):
            return self._integration_stub(tool_name, args, "Notion")
        if tool_name in ("brand_assets.read", "styleguide.read"):
            return self._brand_tool(tool_name, args)

        # Phase 7: Finance & CRM
        if tool_name.startswith("finance."):
            return self._finance_tool(tool_name, args)
        if tool_name.startswith("salesforce."):
            return self._integration_stub(tool_name, args, "Salesforce")
        if tool_name.startswith("hubspot."):
            return self._integration_stub(tool_name, args, "HubSpot")

        return ToolResult(tool_name=tool_name, ok=False, output={}, error="unknown tool")

    def _web_research(self, args: dict[str, Any]) -> ToolResult:
        query = str(args.get("query") or "").strip()
        if not query:
            return ToolResult(tool_name="web.research", ok=False, output={}, error="query is required")

        params = urlencode({"q": query, "format": "json", "no_redirect": "1", "no_html": "1"})
        url = f"https://api.duckduckgo.com/?{params}"

        try:
            with urlopen(url, timeout=5) as resp:  # nosec B310
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # pragma: no cover
            return ToolResult(
                tool_name="web.research",
                ok=False,
                output={"query": query, "results": []},
                error=f"web lookup failed: {exc}",
            )

        related = data.get("RelatedTopics") or []
        results: list[dict[str, Any]] = []
        for item in related:
            if isinstance(item, dict) and item.get("Text") and item.get("FirstURL"):
                results.append({"title": item["Text"], "url": item["FirstURL"]})
            elif isinstance(item, dict) and isinstance(item.get("Topics"), list):
                for topic in item["Topics"]:
                    if topic.get("Text") and topic.get("FirstURL"):
                        results.append({"title": topic["Text"], "url": topic["FirstURL"]})
            if len(results) >= 5:
                break

        return ToolResult(
            tool_name="web.research",
            ok=True,
            output={"query": query, "results": results[:5], "source": "duckduckgo_instant_answer"},
        )

    def _docs_retrieve(self, args: dict[str, Any]) -> ToolResult:
        query = str(args.get("query") or "").strip().lower()
        if not query:
            return ToolResult(tool_name="docs.retrieve", ok=False, output={}, error="query is required")

        include_ext = {".md", ".txt", ".rst", ".pdf"}
        matches: list[dict[str, Any]] = []
        warnings: list[str] = []

        for path in self._iter_docs(include_ext, query):
            if len(matches) >= 10:
                break
            if not path.is_file() or path.suffix.lower() not in include_ext:
                continue
            if ".git" in path.parts:
                continue
            if path.suffix.lower() == ".pdf":
                try:
                    pdf_hits = self._search_pdf(path, query, 10 - len(matches))
                    matches.extend(pdf_hits)
                except Exception as exc:  # pragma: no cover
                    warnings.append(f"failed to parse PDF {path}: {exc}")
                continue

            text = self._read_text_doc(path)
            if text is None:
                continue
            lowered = text.lower()
            index = lowered.find(query)
            if index == -1:
                continue
            start = max(0, index - 120)
            end = min(len(text), index + 180)
            snippet = text[start:end].replace("\n", " ").strip()
            matches.append({"path": str(path), "snippet": snippet})

        return ToolResult(
            tool_name="docs.retrieve",
            ok=True,
            output={"query": query, "matches": matches, "warnings": warnings},
        )

    def _iter_docs(self, include_ext: set[str], query: str) -> list[Path]:
        docs: list[Path] = []
        for path in self._repo_root.rglob("*"):
            if path.is_file() and path.suffix.lower() in include_ext:
                docs.append(path)

        for path, domain in self._load_external_resources():
            if not self._is_relevant_query_for_domain(query, domain):
                continue
            if path.is_file() and path.suffix.lower() in include_ext:
                docs.append(path)
        return docs

    def _load_external_resources(self) -> list[tuple[Path, str]]:
        if not self._resource_catalog_path.exists():
            return []

        try:
            payload = json.loads(self._resource_catalog_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

        raw_resources: list[Any]
        if isinstance(payload, dict):
            raw_resources = list(payload.get("resources") or [])
        elif isinstance(payload, list):
            raw_resources = payload
        else:
            raw_resources = []

        resources: list[tuple[Path, str]] = []
        for item in raw_resources:
            if isinstance(item, str):
                resources.append((Path(item).expanduser(), "general"))
                continue
            if isinstance(item, dict) and item.get("path"):
                resources.append(
                    (
                        Path(str(item["path"])).expanduser(),
                        str(item.get("domain") or "general"),
                    )
                )
        return resources

    def _is_relevant_query_for_domain(self, query: str, domain: str) -> bool:
        if domain != "project_management":
            return True
        pm_tokens = {
            "project",
            "charter",
            "scope",
            "schedule",
            "wbs",
            "milestone",
            "stakeholder",
            "risk",
            "issue",
            "pmo",
            "governance",
            "baseline",
            "deliverable",
        }
        return any(token in query for token in pm_tokens)

    def _read_text_doc(self, path: Path) -> str | None:
        key = str(path.resolve())
        try:
            mtime = path.stat().st_mtime_ns
        except OSError:
            return None

        cached = self._text_cache.get(key)
        if cached and cached[0] == mtime:
            return cached[1]

        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return None
        self._text_cache[key] = (mtime, text)
        return text

    def _search_pdf(self, path: Path, query: str, max_hits: int) -> list[dict[str, Any]]:
        if max_hits <= 0:
            return []

        key = str(path.resolve())
        try:
            mtime = path.stat().st_mtime_ns
        except OSError:
            return []

        pages: list[str]
        cached = self._pdf_cache.get(key)
        if cached and cached[0] == mtime:
            pages = cached[1]
        else:
            try:
                from pypdf import PdfReader
            except ModuleNotFoundError as exc:  # pragma: no cover
                raise RuntimeError("pypdf is required for PDF resource retrieval") from exc

            reader = PdfReader(str(path))
            pages = [(page.extract_text() or "") for page in reader.pages]
            self._pdf_cache[key] = (mtime, pages)

        hits: list[dict[str, Any]] = []
        for page_idx, text in enumerate(pages, start=1):
            lowered = text.lower()
            index = lowered.find(query)
            if index == -1:
                continue
            start = max(0, index - 120)
            end = min(len(text), index + 220)
            snippet = " ".join(text[start:end].split())
            hits.append({"path": str(path), "page": page_idx, "snippet": snippet})
            if len(hits) >= max_hits:
                break
        return hits

    # ---- Phase 1: Document generation ----

    def _docs_generate(self, args: dict[str, Any]) -> ToolResult:
        """Generate a document file (docx, pptx, xlsx, pdf)."""
        try:
            from packages.docgen import DocGenService
            from packages.docgen.generators.base import DocumentContent, DocumentSection
            from packages.storage import FileStorageService
        except ImportError as exc:
            return ToolResult(tool_name="docs.generate", ok=False, output={}, error=f"docgen not available: {exc}")

        fmt = str(args.get("format", "docx")).lower()
        title = str(args.get("title", "Untitled"))
        sections_raw = args.get("sections") or []
        sections = []
        for s in sections_raw:
            sections.append(DocumentSection(
                heading=str(s.get("heading", "")),
                body=str(s.get("body", "")),
                level=int(s.get("level", 1)),
                table=s.get("table"),
                chart_spec=s.get("chart_spec"),
                slide_notes=str(s.get("slide_notes", "")),
            ))
        if not sections:
            sections = [DocumentSection(heading="Content", body=str(args.get("content", "")), level=1)]

        content = DocumentContent(
            title=title,
            document_type=str(args.get("document_type", "report")),
            sections=sections,
            metadata=args.get("metadata") or {"author": "Friday"},
        )

        storage_dir = self._repo_root / "data" / "files"
        storage_db = self._repo_root / "data" / "friday_files.sqlite3"
        storage = FileStorageService(storage_dir=storage_dir, db_path=storage_db)
        docgen = DocGenService(storage=storage)
        try:
            stored = docgen.generate(content, fmt)
            return ToolResult(
                tool_name="docs.generate", ok=True,
                output={"file_id": stored.file_id, "filename": stored.filename, "format": fmt},
            )
        except Exception as exc:
            return ToolResult(tool_name="docs.generate", ok=False, output={}, error=str(exc))

    def _templates_tool(self, tool_name: str, args: dict[str, Any]) -> ToolResult:
        """List or read document templates."""
        try:
            from packages.templates import TemplateService
        except ImportError as exc:
            return ToolResult(tool_name=tool_name, ok=False, output={}, error=str(exc))

        db_path = self._repo_root / "data" / "friday_templates.sqlite3"
        seed_dir = self._repo_root / "data" / "templates"
        svc = TemplateService(db_path=db_path, seed_dir=seed_dir)
        if tool_name == "templates.list":
            doc_type = args.get("document_type")
            templates = svc.list_by_type(doc_type) if doc_type else svc.list_templates()
            return ToolResult(tool_name=tool_name, ok=True, output={
                "templates": [{"id": t.template_id, "name": t.name, "type": t.document_type} for t in templates]
            })
        elif tool_name == "templates.read":
            template_id = str(args.get("template_id", ""))
            t = svc.get(template_id)
            if t is None:
                return ToolResult(tool_name=tool_name, ok=False, output={}, error=f"Template {template_id!r} not found")
            return ToolResult(tool_name=tool_name, ok=True, output={
                "template": {"id": t.template_id, "name": t.name, "type": t.document_type,
                             "description": t.description, "variables": t.variables}
            })
        return ToolResult(tool_name=tool_name, ok=False, output={}, error="unknown templates sub-tool")

    # ---- Phase 2-3, 5-7: Integration stubs ----

    def _google_stub(self, tool_name: str, args: dict[str, Any]) -> ToolResult:
        return ToolResult(tool_name=tool_name, ok=True, output={
            "stub": True, "message": "Google Workspace integration not yet connected. Configure OAuth in Settings.",
            "args_received": args,
        })

    def _email_stub(self, tool_name: str, args: dict[str, Any]) -> ToolResult:
        return ToolResult(tool_name=tool_name, ok=True, output={
            "stub": True, "message": "Email integration not yet connected. Configure Gmail/Outlook in Settings.",
            "args_received": args,
        })

    def _calendar_stub(self, tool_name: str, args: dict[str, Any]) -> ToolResult:
        return ToolResult(tool_name=tool_name, ok=True, output={
            "stub": True, "message": "Calendar integration not yet connected. Configure Google Calendar/Outlook in Settings.",
            "args_received": args,
        })

    def _slack_stub(self, tool_name: str, args: dict[str, Any]) -> ToolResult:
        return ToolResult(tool_name=tool_name, ok=True, output={
            "stub": True, "message": "Slack integration not yet connected. Configure Slack in Settings.",
            "args_received": args,
        })

    def _integration_stub(self, tool_name: str, args: dict[str, Any], service: str) -> ToolResult:
        return ToolResult(tool_name=tool_name, ok=True, output={
            "stub": True, "message": f"{service} integration not yet connected. Configure in Settings.",
            "args_received": args,
        })

    # ---- Phase 4: Analytics ----

    def _analytics_tool(self, tool_name: str, args: dict[str, Any]) -> ToolResult:
        try:
            from packages.analytics import KPIService
        except ImportError as exc:
            return ToolResult(tool_name=tool_name, ok=False, output={}, error=str(exc))

        db_path = self._repo_root / "data" / "friday_analytics.sqlite3"
        svc = KPIService(db_path=db_path)
        if tool_name == "analytics.kpi_status":
            kpis = svc.list_kpis()
            statuses = []
            for k in kpis:
                status = svc.kpi_status(k.kpi_id)
                statuses.append(status)
            return ToolResult(tool_name=tool_name, ok=True, output={"kpis": statuses})
        elif tool_name == "analytics.chart":
            kpi_id = str(args.get("kpi_id", ""))
            try:
                from packages.analytics import ChartService
                chart_svc = ChartService()
                trend = svc.get_trend(kpi_id)
                result = chart_svc.render_sparkline(kpi_id, trend)
                return ToolResult(tool_name=tool_name, ok=True, output=result)
            except Exception as exc:
                return ToolResult(tool_name=tool_name, ok=False, output={}, error=str(exc))
        return ToolResult(tool_name=tool_name, ok=False, output={}, error="unknown analytics sub-tool")

    # ---- Phase 5: OKRs ----

    def _okrs_tool(self, tool_name: str, args: dict[str, Any]) -> ToolResult:
        try:
            from packages.okrs import OKRService
        except ImportError as exc:
            return ToolResult(tool_name=tool_name, ok=False, output={}, error=str(exc))

        db_path = self._repo_root / "data" / "friday_okrs.sqlite3"
        svc = OKRService(db_path=db_path)
        if tool_name == "okrs.status":
            objectives = svc.list_objectives()
            return ToolResult(tool_name=tool_name, ok=True, output={
                "objectives": [{"id": o.objective_id, "title": o.title, "progress": o.progress} for o in objectives]
            })
        return ToolResult(tool_name=tool_name, ok=False, output={}, error="unknown okrs sub-tool")

    # ---- Phase 6: Brand ----

    def _brand_tool(self, tool_name: str, args: dict[str, Any]) -> ToolResult:
        try:
            from packages.brand import BrandAssetService
        except ImportError as exc:
            return ToolResult(tool_name=tool_name, ok=False, output={}, error=str(exc))

        db_path = self._repo_root / "data" / "friday_brand.sqlite3"
        svc = BrandAssetService(db_path=db_path)
        assets = svc.get_assets()
        return ToolResult(tool_name=tool_name, ok=True, output={"brand": assets})

    # ---- Phase 7: Finance ----

    def _finance_tool(self, tool_name: str, args: dict[str, Any]) -> ToolResult:
        try:
            from packages.finance import InvoiceService, BudgetService
        except ImportError as exc:
            return ToolResult(tool_name=tool_name, ok=False, output={}, error=str(exc))

        db_path = self._repo_root / "data" / "friday_finance.sqlite3"
        if tool_name == "finance.create_invoice":
            svc = InvoiceService(db_path=db_path)
            try:
                from packages.finance.invoice_service import InvoiceItem
                items = [InvoiceItem(
                    description=str(i.get("description", "")),
                    quantity=float(i.get("quantity", 1)),
                    unit_price=float(i.get("unit_price", 0)),
                ) for i in (args.get("items") or [])]
                invoice = svc.create_invoice(
                    client_name=str(args.get("client_name", "")),
                    items=items,
                    org_id=str(args.get("org_id", "org-1")),
                )
                return ToolResult(tool_name=tool_name, ok=True, output={
                    "invoice_id": invoice.invoice_id, "total": invoice.total, "status": invoice.status
                })
            except Exception as exc:
                return ToolResult(tool_name=tool_name, ok=False, output={}, error=str(exc))
        elif tool_name == "finance.budget_status":
            svc = BudgetService(db_path=db_path)
            categories = svc.list_categories()
            return ToolResult(tool_name=tool_name, ok=True, output={
                "categories": [{"name": c.name, "budget": c.budget_amount, "spent": c.spent} for c in categories]
            })
        return ToolResult(tool_name=tool_name, ok=False, output={}, error="unknown finance sub-tool")

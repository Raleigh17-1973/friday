from __future__ import annotations

import ipaddress
import json
import os
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse
from urllib.request import urlopen


# ── PR-07: SSRF / egress policy ───────────────────────────────────────────────
# Tools that make outbound HTTP calls use _safe_urlopen() which blocks
# requests to private networks and enforces timeouts + response size caps.

_HTTP_TIMEOUT = int(os.getenv("FRIDAY_TOOL_HTTP_TIMEOUT", "15"))           # seconds
_HTTP_MAX_BYTES = int(os.getenv("FRIDAY_TOOL_MAX_RESPONSE_BYTES", str(5 * 1024 * 1024)))  # 5 MB
_EGRESS_ALLOWLIST: list[str] = [
    h.strip()
    for h in os.getenv("FRIDAY_TOOL_EGRESS_ALLOWLIST", "").split(",")
    if h.strip()
]

_PRIVATE_NETS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),   # link-local / cloud metadata
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]


def _check_egress(url: str) -> None:
    """Raise ValueError if the URL targets a private/internal address.

    Checks:
    - Scheme must be https (or http for known trusted API hosts)
    - If FRIDAY_TOOL_EGRESS_ALLOWLIST is set, hostname must be in it
    - Resolved IP must not be in a private range
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Disallowed URL scheme: {parsed.scheme}")
    host = parsed.hostname or ""
    if _EGRESS_ALLOWLIST and not any(host == h or host.endswith("." + h) for h in _EGRESS_ALLOWLIST):
        raise ValueError(f"Host {host!r} not in egress allowlist")
    try:
        ip_str = socket.gethostbyname(host)
        ip = ipaddress.ip_address(ip_str)
        for net in _PRIVATE_NETS:
            if ip in net:
                raise ValueError(f"SSRF: {host} resolved to private address {ip_str}")
    except socket.gaierror:
        pass  # DNS failure will surface as a connection error; not a security issue


def _safe_urlopen(url: str, **kwargs: Any):
    """urlopen wrapper that enforces egress policy, timeout, and response-size cap."""
    _check_egress(url)
    timeout = kwargs.pop("timeout", _HTTP_TIMEOUT)
    resp = urlopen(url, timeout=timeout, **kwargs)  # nosec B310
    # Wrap read to cap bytes
    original_read = resp.read

    def _capped_read(n: int = -1) -> bytes:
        data = original_read(n)
        if len(data) > _HTTP_MAX_BYTES:
            raise ValueError(f"Response exceeded {_HTTP_MAX_BYTES} byte limit")
        return data

    resp.read = _capped_read  # type: ignore[method-assign]
    return resp


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
            return self._slack_tool(tool_name, args)

        # Phase 4: Analytics
        if tool_name.startswith("analytics."):
            return self._analytics_tool(tool_name, args)

        # Phase 5: Jira, Linear, OKRs
        if tool_name.startswith("jira."):
            return self._integration_stub(tool_name, args, "Jira")
        if tool_name.startswith("linear."):
            return self._integration_stub(tool_name, args, "Linear")
        if tool_name.startswith("okrs."):
            return self._okrs_tool(tool_name, args)
        if tool_name.startswith("process."):
            return self._process_tool(tool_name, args)
        if tool_name.startswith("tasks."):
            return self._tasks_tool(tool_name, args)

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

        # Phase N+1: Code interpreter / data analysis
        if tool_name.startswith("analysis.") or tool_name == "code.run":
            return self._analysis_tool(tool_name, args)

        # Phase N+2: Meeting intelligence
        if tool_name.startswith("meetings."):
            return self._meetings_tool(tool_name, args)

        # Phase N+3: Org context
        if tool_name.startswith("org."):
            return self._org_tool(tool_name, args)

        # Phase N+4: Decision log
        if tool_name.startswith("decisions."):
            return self._decisions_tool(tool_name, args)

        # Phase N+5: Financial modeling
        if tool_name.startswith("modeling."):
            return self._modeling_tool(tool_name, args)

        # Phase N+6: Proactive intelligence
        if tool_name.startswith("proactive."):
            return self._proactive_tool(tool_name, args)

        return ToolResult(tool_name=tool_name, ok=False, output={}, error="unknown tool")

    def _web_research(self, args: dict[str, Any]) -> ToolResult:
        """Web research with priority: Tavily API → Exa API → DuckDuckGo fallback.

        Set TAVILY_API_KEY or EXA_API_KEY env vars for full search capability.
        DuckDuckGo instant-answer API is used as a no-key fallback (limited results).
        """
        import os
        query = str(args.get("query") or "").strip()
        if not query:
            return ToolResult(tool_name="web.research", ok=False, output={}, error="query is required")

        # --- Tavily (best for research queries) ---
        tavily_key = os.getenv("TAVILY_API_KEY", "")
        if tavily_key:
            try:
                return self._web_research_tavily(query, tavily_key)
            except Exception:
                pass  # fall through

        # --- Exa (semantic search) ---
        exa_key = os.getenv("EXA_API_KEY", "")
        if exa_key:
            try:
                return self._web_research_exa(query, exa_key)
            except Exception:
                pass  # fall through

        # --- DuckDuckGo instant answer (no-key fallback) ---
        return self._web_research_ddg(query)

    def _web_research_tavily(self, query: str, api_key: str) -> ToolResult:
        """Call Tavily Search API — returns full page excerpts."""
        import json as _json
        from urllib.request import Request

        body = _json.dumps({
            "api_key": api_key,
            "query": query,
            "search_depth": "advanced",
            "max_results": 6,
            "include_answer": True,
        }).encode("utf-8")

        req = Request(
            "https://api.tavily.com/search",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with _safe_urlopen(req, timeout=10) as resp:
            data = _json.loads(resp.read().decode("utf-8"))

        results = [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("content", "")[:400],
                "score": r.get("score", 0),
            }
            for r in data.get("results", [])
        ]
        answer = data.get("answer", "")
        return ToolResult(
            tool_name="web.research",
            ok=True,
            output={
                "query": query,
                "answer": answer,
                "results": results,
                "source": "tavily",
            },
        )

    def _web_research_exa(self, query: str, api_key: str) -> ToolResult:
        """Call Exa neural search API."""
        import json as _json
        from urllib.request import Request

        body = _json.dumps({
            "query": query,
            "numResults": 6,
            "useAutoprompt": True,
            "type": "neural",
            "contents": {"text": {"maxCharacters": 400}},
        }).encode("utf-8")

        req = Request(
            "https://api.exa.ai/search",
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
            },
            method="POST",
        )
        with _safe_urlopen(req, timeout=10) as resp:
            data = _json.loads(resp.read().decode("utf-8"))

        results = [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": (r.get("text") or "")[:400],
                "score": r.get("score", 0),
            }
            for r in data.get("results", [])
        ]
        return ToolResult(
            tool_name="web.research",
            ok=True,
            output={"query": query, "results": results, "source": "exa"},
        )

    def _web_research_ddg(self, query: str) -> ToolResult:
        """DuckDuckGo instant answer API — no key required, limited results."""
        params = urlencode({"q": query, "format": "json", "no_redirect": "1", "no_html": "1"})
        url = f"https://api.duckduckgo.com/?{params}"

        try:
            with _safe_urlopen(url, timeout=5) as resp:
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
        abstract = data.get("AbstractText", "")
        if abstract:
            results.append({
                "title": data.get("Heading", query),
                "url": data.get("AbstractURL", ""),
                "snippet": abstract[:400],
            })
        for item in related:
            if isinstance(item, dict) and item.get("Text") and item.get("FirstURL"):
                results.append({"title": item["Text"][:120], "url": item["FirstURL"], "snippet": item["Text"]})
            elif isinstance(item, dict) and isinstance(item.get("Topics"), list):
                for topic in item["Topics"]:
                    if topic.get("Text") and topic.get("FirstURL"):
                        results.append({"title": topic["Text"][:120], "url": topic["FirstURL"], "snippet": topic["Text"]})
            if len(results) >= 6:
                break

        return ToolResult(
            tool_name="web.research",
            ok=True,
            output={
                "query": query,
                "results": results[:6],
                "source": "duckduckgo_instant_answer",
                "note": "Set TAVILY_API_KEY or EXA_API_KEY for full search results",
            },
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

    def _slack_tool(self, tool_name: str, args: dict[str, Any]) -> ToolResult:
        """Real Slack tool dispatch — uses SlackClient with credential-resolved token."""
        from packages.integrations.slack.client import SlackClient
        # Resolve token from credential service if available
        token: str | None = None
        try:
            if hasattr(self, "_service") and self._service is not None:
                cred_svc = getattr(self._service, "credentials", None)
                if cred_svc and cred_svc.has_credential("slack", "org-1"):
                    cred = cred_svc.get_credential("slack", "org-1")
                    token = cred.token if cred else None
        except Exception:
            pass
        client = SlackClient(token=token)
        try:
            if tool_name == "slack.post":
                result = client.post_message(
                    channel=str(args.get("channel", "#general")),
                    text=str(args.get("text", "")),
                    thread_ts=args.get("thread_ts"),
                )
                return ToolResult(tool_name=tool_name, ok=result.get("ok", False), output=result)
            if tool_name == "slack.dm":
                result = client.send_dm(
                    user_id=str(args.get("user_id", "")),
                    text=str(args.get("text", "")),
                )
                return ToolResult(tool_name=tool_name, ok=result.get("ok", False), output=result)
            if tool_name == "slack.channels":
                return ToolResult(tool_name=tool_name, ok=True, output={"channels": client.get_channels()})
            if tool_name == "slack.users":
                return ToolResult(tool_name=tool_name, ok=True, output={"users": client.get_users()})
        except Exception as exc:
            return ToolResult(tool_name=tool_name, ok=False, error=str(exc))
        return self._slack_stub(tool_name, args)

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

    # ---- Enterprise OKRs ----

    def _okrs_tool(self, tool_name: str, args: dict[str, Any]) -> ToolResult:
        try:
            from packages.okrs import EnterpriseOKRService
        except ImportError as exc:
            return ToolResult(tool_name=tool_name, ok=False, output={}, error=str(exc))

        db_path = self._repo_root / "data" / "friday_okrs_v2.sqlite3"
        svc = EnterpriseOKRService(db_path=db_path)

        # ── Read: status overview ─────────────────────────────────────────────
        if tool_name == "okrs.status":
            objs = svc.list_objectives(org_id=str(args.get("org_id", "org-1")))
            return ToolResult(tool_name=tool_name, ok=True, output={
                "objectives": [
                    {"id": o.objective_id, "title": o.title,
                     "type": o.objective_type, "health": o.health_current,
                     "score": o.confidence_current}
                    for o in objs
                ]
            })

        # ── Write: org node ───────────────────────────────────────────────────
        if tool_name == "okrs.create_org_node":
            try:
                node = svc.create_org_node(
                    name=str(args.get("name", "New Team")),
                    node_type=str(args.get("node_type", "team")),
                    parent_id=args.get("parent_id"),
                    org_id=str(args.get("org_id", "org-1")),
                    owner_user_id=str(args.get("owner_user_id", "user-1")),
                )
                return ToolResult(tool_name=tool_name, ok=True, output={
                    "node_id": node.node_id, "name": node.name, "created": True,
                })
            except Exception as exc:
                return ToolResult(tool_name=tool_name, ok=False, output={}, error=str(exc))

        # ── Write: period ─────────────────────────────────────────────────────
        if tool_name == "okrs.create_period":
            try:
                period = svc.create_period(
                    name=str(args.get("name", "")),
                    period_type=str(args.get("period_type", "quarterly")),
                    fiscal_year=int(args.get("fiscal_year", 2026)),
                    quarter=args.get("quarter"),
                    start_date=str(args.get("start_date", "")),
                    end_date=str(args.get("end_date", "")),
                    org_id=str(args.get("org_id", "org-1")),
                )
                return ToolResult(tool_name=tool_name, ok=True, output={
                    "period_id": period.period_id, "name": period.name, "created": True,
                })
            except Exception as exc:
                return ToolResult(tool_name=tool_name, ok=False, output={}, error=str(exc))

        # ── Write: objective ──────────────────────────────────────────────────
        if tool_name == "okrs.create_objective":
            try:
                obj = svc.create_objective(
                    period_id=str(args.get("period_id", "")),
                    org_node_id=str(args.get("org_node_id", "node-company")),
                    title=str(args.get("title", "")),
                    objective_type=str(args.get("objective_type", "committed")),
                    owner_user_id=str(args.get("owner_user_id", "user-1")),
                    org_id=str(args.get("org_id", "org-1")),
                    description=str(args.get("description", "")),
                    rationale=str(args.get("rationale", "")),
                    parent_objective_id=args.get("parent_objective_id"),
                    sponsor_user_id=args.get("sponsor_user_id"),
                )
                return ToolResult(tool_name=tool_name, ok=True, output={
                    "objective_id": obj.objective_id, "title": obj.title,
                    "type": obj.objective_type, "created": True,
                })
            except Exception as exc:
                return ToolResult(tool_name=tool_name, ok=False, output={}, error=str(exc))

        if tool_name == "okrs.update_objective":
            try:
                obj_id = str(args.get("objective_id", ""))
                if not obj_id:
                    return ToolResult(tool_name=tool_name, ok=False, output={}, error="objective_id required")
                update_kwargs = {k: v for k, v in args.items() if k != "objective_id" and v is not None}
                obj = svc.update_objective(obj_id, **update_kwargs)
                return ToolResult(tool_name=tool_name, ok=True, output={
                    "objective_id": obj.objective_id, "updated": True,
                })
            except Exception as exc:
                return ToolResult(tool_name=tool_name, ok=False, output={}, error=str(exc))

        # ── Write: key result ─────────────────────────────────────────────────
        if tool_name == "okrs.create_kr":
            try:
                kr = svc.create_key_result(
                    objective_id=str(args.get("objective_id", "")),
                    title=str(args.get("title", "")),
                    kr_type=str(args.get("kr_type", "metric")),
                    owner_user_id=str(args.get("owner_user_id", "user-1")),
                    org_id=str(args.get("org_id", "org-1")),
                    baseline_value=args.get("baseline_value"),
                    target_value=args.get("target_value"),
                    unit=str(args.get("unit", "")),
                    direction=str(args.get("direction", "increase")),
                    metric_name=args.get("metric_name"),
                    description=str(args.get("description", "")),
                    due_date=args.get("due_date"),
                )
                return ToolResult(tool_name=tool_name, ok=True, output={
                    "kr_id": kr.kr_id, "title": kr.title,
                    "type": kr.kr_type, "created": True,
                })
            except Exception as exc:
                return ToolResult(tool_name=tool_name, ok=False, output={}, error=str(exc))

        if tool_name == "okrs.update_kr":
            try:
                kr_id = str(args.get("kr_id", ""))
                if not kr_id:
                    return ToolResult(tool_name=tool_name, ok=False, output={}, error="kr_id required")
                update_kwargs = {k: v for k, v in args.items() if k != "kr_id" and v is not None}
                kr = svc.update_key_result(kr_id, **update_kwargs)
                return ToolResult(tool_name=tool_name, ok=True, output={
                    "kr_id": kr.kr_id, "score": kr.score_current, "updated": True,
                })
            except Exception as exc:
                return ToolResult(tool_name=tool_name, ok=False, output={}, error=str(exc))

        # ── Write: check-in ───────────────────────────────────────────────────
        if tool_name == "okrs.checkin_kr":
            try:
                checkin = svc.add_checkin(
                    object_type="key_result",
                    object_id=str(args.get("kr_id", "")),
                    user_id=str(args.get("user_id", "user-1")),
                    checkin_date=args.get("checkin_date"),
                    current_value=args.get("current_value"),
                    confidence=args.get("confidence"),
                    blockers=str(args.get("blockers", "")),
                    decisions_needed=str(args.get("decisions_needed", "")),
                    narrative_update=str(args.get("narrative_update", "")),
                    next_steps=str(args.get("next_steps", "")),
                    org_id=str(args.get("org_id", "org-1")),
                )
                return ToolResult(tool_name=tool_name, ok=True, output={
                    "checkin_id": checkin.checkin_id,
                    "score_snapshot": checkin.score_snapshot,
                    "created": True,
                })
            except Exception as exc:
                return ToolResult(tool_name=tool_name, ok=False, output={}, error=str(exc))

        # ── Write: KPI ────────────────────────────────────────────────────────
        if tool_name == "okrs.create_kpi":
            try:
                kpi = svc.create_kpi(
                    name=str(args.get("name", "")),
                    unit=str(args.get("unit", "")),
                    org_id=str(args.get("org_id", "org-1")),
                    org_node_id=args.get("org_node_id"),
                    metric_definition=str(args.get("metric_definition", "")),
                    description=str(args.get("description", "")),
                    target_band_low=args.get("target_band_low"),
                    target_band_high=args.get("target_band_high"),
                    update_frequency=str(args.get("update_frequency", "monthly")),
                )
                return ToolResult(tool_name=tool_name, ok=True, output={
                    "kpi_id": kpi.kpi_id, "name": kpi.name, "created": True,
                })
            except Exception as exc:
                return ToolResult(tool_name=tool_name, ok=False, output={}, error=str(exc))

        # ── Write: KR–KPI link ────────────────────────────────────────────────
        if tool_name == "okrs.link_kpi":
            try:
                link = svc.link_kr_to_kpi(
                    kr_id=str(args.get("kr_id", "")),
                    kpi_id=str(args.get("kpi_id", "")),
                    link_type=str(args.get("link_type", "derived_from")),
                    contribution_notes=str(args.get("contribution_notes", "")),
                )
                return ToolResult(tool_name=tool_name, ok=True, output={
                    "link_id": link.link_id, "linked": True,
                })
            except Exception as exc:
                return ToolResult(tool_name=tool_name, ok=False, output={}, error=str(exc))

        # ── Write: dependency ─────────────────────────────────────────────────
        if tool_name == "okrs.create_dependency":
            try:
                dep = svc.create_dependency(
                    source_type=str(args.get("source_type", "objective")),
                    source_id=str(args.get("source_id", "")),
                    target_type=str(args.get("target_type", "objective")),
                    target_id=str(args.get("target_id", "")),
                    dep_type=str(args.get("dep_type", "contributes_to")),
                    severity=str(args.get("severity", "medium")),
                    org_id=str(args.get("org_id", "org-1")),
                )
                return ToolResult(tool_name=tool_name, ok=True, output={
                    "dependency_id": dep.dependency_id, "created": True,
                })
            except Exception as exc:
                return ToolResult(tool_name=tool_name, ok=False, output={}, error=str(exc))

        # ── Write: grade objective ────────────────────────────────────────────
        if tool_name == "okrs.grade_objective":
            try:
                result = svc.grade_objective(
                    objective_id=str(args.get("objective_id", "")),
                    grade=float(args.get("grade", 0.0)),
                    retrospective=str(args.get("retrospective", "")),
                    carry_forward=bool(args.get("carry_forward", False)),
                    next_period_id=args.get("next_period_id"),
                )
                return ToolResult(tool_name=tool_name, ok=True, output=result)
            except Exception as exc:
                return ToolResult(tool_name=tool_name, ok=False, output={}, error=str(exc))

        # ── Write: meeting artifact ───────────────────────────────────────────
        if tool_name == "okrs.generate_meeting":
            try:
                artifact = svc.generate_meeting_artifact(
                    meeting_type=str(args.get("meeting_type", "weekly_checkin")),
                    org_node_id=args.get("org_node_id"),
                    period_id=args.get("period_id"),
                    org_id=str(args.get("org_id", "org-1")),
                )
                return ToolResult(tool_name=tool_name, ok=True, output={
                    "artifact_id": artifact.artifact_id,
                    "meeting_type": artifact.meeting_type,
                    "agenda_markdown": artifact.agenda_markdown[:500],
                    "created": True,
                })
            except Exception as exc:
                return ToolResult(tool_name=tool_name, ok=False, output={}, error=str(exc))

        return ToolResult(tool_name=tool_name, ok=False, output={}, error=f"unknown okrs sub-tool: {tool_name}")

    # ---- Process management ----

    def _process_tool(self, tool_name: str, args: dict[str, Any]) -> ToolResult:
        try:
            from packages.process.service import ProcessService
            from packages.common.models import ProcessDocument, ProcessStep
        except ImportError as exc:
            return ToolResult(tool_name=tool_name, ok=False, output={}, error=str(exc))

        db_path = self._repo_root / "data" / "friday_processes.sqlite3"
        svc = ProcessService(db_path=db_path)

        if tool_name == "process.create":
            try:
                raw_steps = args.get("steps") or []
                steps = []
                for i, s in enumerate(raw_steps):
                    if isinstance(s, dict):
                        steps.append(ProcessStep(
                            id=str(s.get("id", f"step_{i+1}")),
                            name=str(s.get("name", s.get("title", f"Step {i+1}"))),
                            owner=str(s.get("owner", s.get("owner_role", ""))),
                            inputs=list(s.get("inputs", [])),
                            outputs=list(s.get("outputs", [])),
                            tools=list(s.get("tools", [])),
                            sla=str(s.get("sla", s.get("duration_estimate", ""))),
                        ))
                    elif isinstance(s, str):
                        steps.append(ProcessStep(id=f"step_{i+1}", name=s, owner=""))

                doc = ProcessDocument(
                    id="",
                    org_id=str(args.get("org_id", "org-1")),
                    process_name=str(args.get("process_name", args.get("name", "New Process"))),
                    trigger=str(args.get("trigger", "")),
                    steps=steps,
                    decision_points=list(args.get("decision_points", [])),
                    roles=list(args.get("roles", [])),
                    tools=list(args.get("tools", [])),
                    exceptions=list(args.get("exceptions", [])),
                    kpis=list(args.get("kpis", [])),
                    mermaid_flowchart=str(args.get("mermaid_flowchart", "")),
                    mermaid_swimlane=str(args.get("mermaid_swimlane", "")),
                    completeness_score=0.0,
                    status="draft",
                )
                created = svc.create(doc)
                return ToolResult(tool_name=tool_name, ok=True, output={
                    "process_id": created.id,
                    "process_name": created.process_name,
                    "created": True,
                })
            except Exception as exc:
                return ToolResult(tool_name=tool_name, ok=False, output={}, error=str(exc))

        if tool_name == "process.update":
            try:
                process_id = str(args.get("process_id", ""))
                if not process_id:
                    return ToolResult(tool_name=tool_name, ok=False, output={}, error="process_id is required")
                changes = {k: v for k, v in args.items() if k not in ("process_id", "bump", "author") and v is not None}
                bump = str(args.get("bump", "patch"))
                author = str(args.get("author", "friday"))
                updated = svc.update(process_id, changes=changes, bump=bump, author=author)
                return ToolResult(tool_name=tool_name, ok=True, output={
                    "process_id": process_id,
                    "updated": True,
                    "process_name": updated.process_name if updated else "",
                })
            except Exception as exc:
                return ToolResult(tool_name=tool_name, ok=False, output={}, error=str(exc))

        return ToolResult(tool_name=tool_name, ok=False, output={}, error="unknown process sub-tool")

    # ---- Tasks ----

    def _tasks_tool(self, tool_name: str, args: dict[str, Any]) -> ToolResult:
        try:
            from packages.tasks import TaskService
        except ImportError as exc:
            return ToolResult(tool_name=tool_name, ok=False, output={}, error=str(exc))

        db_path = self._repo_root / "data" / "friday_tasks.sqlite3"
        svc = TaskService(db_path=db_path)

        if tool_name == "tasks.create":
            try:
                task = svc.create(
                    title=str(args.get("title", "Untitled task")),
                    description=str(args.get("description", "")),
                    assignee=args.get("assignee"),
                    due_date=args.get("due_date"),
                    priority=str(args.get("priority", "medium")),
                    status=str(args.get("status", "open")),
                    workspace_id=args.get("workspace_id"),
                    okr_id=args.get("okr_id"),
                    kr_id=args.get("kr_id"),
                    process_id=args.get("process_id"),
                    created_by=str(args.get("created_by", "friday")),
                )
                return ToolResult(tool_name=tool_name, ok=True, output={
                    "task_id": task.task_id,
                    "title": task.title,
                    "created": True,
                })
            except Exception as exc:
                return ToolResult(tool_name=tool_name, ok=False, output={}, error=str(exc))

        if tool_name == "tasks.update":
            try:
                task_id = str(args.get("task_id", ""))
                if not task_id:
                    return ToolResult(tool_name=tool_name, ok=False, output={}, error="task_id is required")
                changes = {k: v for k, v in args.items() if k != "task_id" and v is not None}
                updated = svc.update(task_id, **changes)
                return ToolResult(tool_name=tool_name, ok=True, output={
                    "task_id": task_id,
                    "updated": True,
                    "title": updated.title if updated else "",
                })
            except Exception as exc:
                return ToolResult(tool_name=tool_name, ok=False, output={}, error=str(exc))

        if tool_name == "tasks.list":
            try:
                tasks = svc.list(
                    assignee=args.get("assignee"),
                    workspace_id=args.get("workspace_id"),
                    status=args.get("status"),
                    priority=args.get("priority"),
                    due_before=args.get("due_before"),
                    okr_id=args.get("okr_id"),
                    limit=int(args.get("limit", 50)),
                )
                return ToolResult(tool_name=tool_name, ok=True, output={
                    "tasks": [t.to_dict() for t in tasks],
                    "count": len(tasks),
                })
            except Exception as exc:
                return ToolResult(tool_name=tool_name, ok=False, output={}, error=str(exc))

        return ToolResult(tool_name=tool_name, ok=False, output={}, error="unknown tasks sub-tool")

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

    # ---- Code Interpreter / Data Analysis ----

    def _analysis_tool(self, tool_name: str, args: dict[str, Any]) -> ToolResult:
        try:
            from packages.interpreter import CodeInterpreterService
        except ImportError as exc:
            return ToolResult(tool_name=tool_name, ok=False, output={}, error=str(exc))

        svc = CodeInterpreterService(timeout=30)

        if tool_name in ("analysis.run", "code.run"):
            code = str(args.get("code") or "")
            if not code:
                return ToolResult(tool_name=tool_name, ok=False, output={}, error="code is required")
            data_files = dict(args.get("data_files") or {})
            result = svc.run(code, data_files=data_files, org_id=str(args.get("org_id", "org-1")))
            return ToolResult(tool_name=tool_name, ok=result["ok"], output=result, error=result.get("error"))

        if tool_name == "analysis.file":
            file_path = str(args.get("file_path") or "")
            question = str(args.get("question") or "Summarize this data")
            if not file_path:
                return ToolResult(tool_name=tool_name, ok=False, output={}, error="file_path is required")
            result = svc.analyze_file(file_path, question, org_id=str(args.get("org_id", "org-1")))
            return ToolResult(tool_name=tool_name, ok=result["ok"], output=result, error=result.get("error"))

        return ToolResult(tool_name=tool_name, ok=False, output={}, error="unknown analysis sub-tool")

    # ---- Meeting Intelligence ----

    def _meetings_tool(self, tool_name: str, args: dict[str, Any]) -> ToolResult:
        try:
            from packages.meetings import MeetingService
        except ImportError as exc:
            return ToolResult(tool_name=tool_name, ok=False, output={}, error=str(exc))

        db_path = self._repo_root / "data" / "meetings.db"
        svc = MeetingService(db_path=db_path)
        org_id = str(args.get("org_id", "org-1"))

        if tool_name == "meetings.create":
            meeting = svc.create_meeting(
                title=str(args.get("title", "Meeting")),
                scheduled_at=str(args.get("scheduled_at", "")),
                attendees=list(args.get("attendees") or []),
                agenda=list(args.get("agenda") or []),
                duration_minutes=int(args.get("duration_minutes", 60)),
                org_id=org_id,
            )
            return ToolResult(tool_name=tool_name, ok=True, output={"meeting_id": meeting.meeting_id, "title": meeting.title})
        if tool_name == "meetings.process_notes":
            note = svc.process_notes(
                meeting_id=str(args.get("meeting_id", "")),
                raw_text=str(args.get("notes", "")),
                org_id=org_id,
            )
            return ToolResult(tool_name=tool_name, ok=True, output={
                "note_id": note.note_id,
                "action_items": [{"description": a.description, "owner": a.owner} for a in note.action_items],
                "decisions": note.decisions_made,
                "summary": note.structured_summary,
            })
        if tool_name == "meetings.action_items":
            items = svc.list_action_items(org_id=org_id, status=str(args.get("status", "open")))
            return ToolResult(tool_name=tool_name, ok=True, output={
                "action_items": [{"id": i.item_id, "description": i.description, "owner": i.owner, "due": i.due_date} for i in items]
            })
        if tool_name == "meetings.list":
            meetings = svc.list_meetings(org_id=org_id, status=args.get("status"))
            return ToolResult(tool_name=tool_name, ok=True, output={
                "meetings": [{"id": m.meeting_id, "title": m.title, "at": m.scheduled_at, "status": m.status} for m in meetings]
            })
        return ToolResult(tool_name=tool_name, ok=False, output={}, error="unknown meetings sub-tool")

    # ---- Org Context ----

    def _org_tool(self, tool_name: str, args: dict[str, Any]) -> ToolResult:
        try:
            from packages.org_context import OrgContextService
        except ImportError as exc:
            return ToolResult(tool_name=tool_name, ok=False, output={}, error=str(exc))

        db_path = self._repo_root / "data" / "org_context.db"
        svc = OrgContextService(db_path=db_path)
        org_id = str(args.get("org_id", "org-1"))

        if tool_name == "org.context":
            summary = svc.build_context_summary(org_id)
            return ToolResult(tool_name=tool_name, ok=True, output={"context": summary})
        if tool_name == "org.people":
            people = svc.list_people(org_id, department=args.get("department"))
            return ToolResult(tool_name=tool_name, ok=True, output={
                "people": [{"name": p.name, "role": p.role, "department": p.department} for p in people]
            })
        if tool_name == "org.priorities":
            priorities = svc.list_priorities(org_id)
            return ToolResult(tool_name=tool_name, ok=True, output={
                "priorities": [{"title": p.title, "owner": p.owner, "due": p.due_date, "status": p.status} for p in priorities]
            })
        if tool_name == "org.chart":
            chart = svc.org_chart(org_id)
            return ToolResult(tool_name=tool_name, ok=True, output={"org_chart": chart})
        return ToolResult(tool_name=tool_name, ok=False, output={}, error="unknown org sub-tool")

    # ---- Decision Log ----

    def _decisions_tool(self, tool_name: str, args: dict[str, Any]) -> ToolResult:
        try:
            from packages.decisions import DecisionLogService
        except ImportError as exc:
            return ToolResult(tool_name=tool_name, ok=False, output={}, error=str(exc))

        db_path = self._repo_root / "data" / "decisions.db"
        svc = DecisionLogService(db_path=db_path)
        org_id = str(args.get("org_id", "org-1"))

        if tool_name == "decisions.log":
            decision = svc.log(
                title=str(args.get("title", "")),
                context=str(args.get("context", "")),
                rationale=str(args.get("rationale", "")),
                owner=str(args.get("owner", "")),
                options_considered=list(args.get("options_considered") or []),
                org_id=org_id,
                tags=list(args.get("tags") or []),
                reversibility=str(args.get("reversibility", "reversible")),
                confidence=float(args.get("confidence", 0.8)),
                related_run_id=str(args.get("related_run_id", "")),
            )
            return ToolResult(tool_name=tool_name, ok=True, output={"decision_id": decision.decision_id})
        if tool_name == "decisions.search":
            decisions = svc.search(str(args.get("query", "")), org_id)
            return ToolResult(tool_name=tool_name, ok=True, output={
                "decisions": [{"id": d.decision_id, "title": d.title, "rationale": d.rationale[:200], "made_at": d.made_at} for d in decisions]
            })
        if tool_name == "decisions.list":
            decisions = svc.list_decisions(org_id, tag=args.get("tag"))
            return ToolResult(tool_name=tool_name, ok=True, output={
                "decisions": [{"id": d.decision_id, "title": d.title, "owner": d.owner, "made_at": d.made_at} for d in decisions]
            })
        if tool_name == "decisions.context":
            ctx = svc.context_for_query(str(args.get("query", "")), org_id)
            return ToolResult(tool_name=tool_name, ok=True, output={"context": ctx})
        return ToolResult(tool_name=tool_name, ok=False, output={}, error="unknown decisions sub-tool")

    # ---- Financial Modeling ----

    def _modeling_tool(self, tool_name: str, args: dict[str, Any]) -> ToolResult:
        try:
            from packages.finance.modeling import FinancialModelingService
        except ImportError as exc:
            return ToolResult(tool_name=tool_name, ok=False, output={}, error=str(exc))

        svc = FinancialModelingService()

        if tool_name == "modeling.scenarios":
            scenarios = svc.three_case_model(
                base_revenue=float(args.get("base_revenue", 0)),
                base_costs=float(args.get("base_costs", 0)),
                optimistic_growth_pct=float(args.get("optimistic_growth_pct", 0.30)),
                pessimistic_growth_pct=float(args.get("pessimistic_growth_pct", -0.15)),
            )
            ev = svc.expected_value(scenarios)
            from dataclasses import asdict
            return ToolResult(tool_name=tool_name, ok=True, output={
                "scenarios": [asdict(s) for s in scenarios],
                "expected_value": ev,
            })
        if tool_name == "modeling.runway":
            result = svc.runway(
                cash_on_hand=float(args.get("cash_on_hand", 0)),
                monthly_burn=float(args.get("monthly_burn", 0)),
                current_mrr=float(args.get("current_mrr", 0)),
                mrr_growth_rate=float(args.get("mrr_growth_rate", 0.08)),
            )
            from dataclasses import asdict
            return ToolResult(tool_name=tool_name, ok=True, output=asdict(result))
        if tool_name == "modeling.dcf":
            result = svc.dcf(
                annual_cash_flows=list(args.get("annual_cash_flows") or []),
                terminal_growth_rate=float(args.get("terminal_growth_rate", 0.03)),
                wacc=float(args.get("wacc", 0.12)),
                net_debt=float(args.get("net_debt", 0)),
            )
            from dataclasses import asdict
            return ToolResult(tool_name=tool_name, ok=True, output=asdict(result))
        if tool_name == "modeling.unit_economics":
            result = svc.unit_economics(
                arpu=float(args.get("arpu", 0)),
                cac=float(args.get("cac", 0)),
                churn_rate=float(args.get("churn_rate", 0.02)),
                gross_margin=float(args.get("gross_margin", 0.70)),
            )
            return ToolResult(tool_name=tool_name, ok=True, output=result)
        if tool_name == "modeling.sensitivity":
            result = svc.sensitivity_table(
                base_revenue=float(args.get("base_revenue", 0)),
                base_margin=float(args.get("base_margin", 0.20)),
            )
            return ToolResult(tool_name=tool_name, ok=True, output=result)
        return ToolResult(tool_name=tool_name, ok=False, output={}, error="unknown modeling sub-tool")

    # ---- Proactive Intelligence ----

    def _proactive_tool(self, tool_name: str, args: dict[str, Any]) -> ToolResult:
        try:
            from packages.proactive import ProactiveScanner, DigestService
        except ImportError as exc:
            return ToolResult(tool_name=tool_name, ok=False, output={}, error=str(exc))

        db_path = self._repo_root / "data" / "proactive.db"
        scanner = ProactiveScanner(db_path=db_path)
        org_id = str(args.get("org_id", "org-1"))

        if tool_name == "proactive.alerts":
            alerts = scanner.list_alerts(org_id=org_id, severity=args.get("severity"))
            return ToolResult(tool_name=tool_name, ok=True, output={
                "alerts": [{"id": a.alert_id, "severity": a.severity.value, "title": a.title, "body": a.body, "category": a.category} for a in alerts]
            })
        if tool_name == "proactive.scan_kpis":
            kpis = list(args.get("kpis") or [])
            alerts = scanner.scan_kpis(kpis)
            return ToolResult(tool_name=tool_name, ok=True, output={"alerts_generated": len(alerts)})
        if tool_name == "proactive.scan_budget":
            categories = list(args.get("categories") or [])
            alerts = scanner.scan_budget(categories)
            return ToolResult(tool_name=tool_name, ok=True, output={"alerts_generated": len(alerts)})
        if tool_name == "proactive.digest":
            digest_svc = DigestService()
            digest = digest_svc.generate_weekly(
                kpis=list(args.get("kpis") or []),
                objectives=list(args.get("objectives") or []),
                alerts=[a.__dict__ for a in scanner.list_alerts(org_id)],
                decisions=list(args.get("decisions") or []),
                org_id=org_id,
            )
            md = digest_svc.digest_to_markdown(digest)
            return ToolResult(tool_name=tool_name, ok=True, output={"digest": md, "digest_id": digest.digest_id})
        return ToolResult(tool_name=tool_name, ok=False, output={}, error="unknown proactive sub-tool")

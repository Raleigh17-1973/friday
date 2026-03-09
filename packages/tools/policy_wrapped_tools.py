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

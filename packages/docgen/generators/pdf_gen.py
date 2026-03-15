"""PDF generator with weasyprint fallback."""
from __future__ import annotations

import io
import logging
from html import escape

from packages.docgen.generators.base import DocumentContent, DocumentGenerator, DocumentSection

_log = logging.getLogger(__name__)

_CSS = """\
body {
    font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
    margin: 40px 60px;
    color: #222;
    line-height: 1.6;
}
h1 { font-size: 28px; border-bottom: 2px solid #333; padding-bottom: 8px; }
h2 { font-size: 22px; margin-top: 24px; }
h3 { font-size: 18px; margin-top: 20px; }
table {
    border-collapse: collapse;
    width: 100%;
    margin: 16px 0;
}
th, td {
    border: 1px solid #bbb;
    padding: 8px 12px;
    text-align: left;
}
th {
    background-color: #4472C4;
    color: #fff;
    font-weight: bold;
}
tr:nth-child(even) { background-color: #f2f2f2; }
.metadata { color: #666; font-size: 14px; margin-bottom: 24px; }
ul { margin: 8px 0; padding-left: 24px; }
"""


class PdfGenerator(DocumentGenerator):
    """Generate PDF files, with weasyprint when available."""

    @property
    def mime_type(self) -> str:
        return "application/pdf"

    @property
    def file_extension(self) -> str:
        return "pdf"

    def generate(
        self,
        content: DocumentContent,
        template_path: str | None = None,
        brand: dict | None = None,
    ) -> bytes:
        html = self._build_html(content, brand=brand or {})

        try:
            from weasyprint import HTML  # type: ignore[import-untyped]

            pdf_bytes = HTML(string=html).write_pdf()
            return pdf_bytes
        except ImportError:
            _log.warning(
                "weasyprint not installed — falling back to raw HTML with .pdf extension. "
                "Install weasyprint for proper PDF generation."
            )
            return html.encode("utf-8")

    # ------------------------------------------------------------------
    def _build_html(self, content: DocumentContent, brand: dict | None = None) -> str:
        brand = brand or {}
        primary_color = brand.get("primary_color", "#4472C4")
        company_name = brand.get("company_name", "")
        # Inject brand color into CSS (replace default header bg color)
        css = _CSS.replace("background-color: #4472C4;", f"background-color: {primary_color};")
        css = css.replace("border-bottom: 2px solid #333;", f"border-bottom: 2px solid {primary_color};")

        parts: list[str] = [
            "<!DOCTYPE html>",
            "<html><head>",
            "<meta charset='utf-8'>",
            f"<title>{escape(content.title)}</title>",
            f"<style>{css}</style>",
            "</head><body>",
            f"<h1>{escape(content.title)}</h1>",
        ]

        # Metadata
        author = content.metadata.get("author", company_name)
        date = content.metadata.get("date", "")
        if author or date:
            meta_parts = []
            if author:
                meta_parts.append(f"Author: {escape(author)}")
            if date:
                meta_parts.append(f"Date: {escape(date)}")
            parts.append(f'<p class="metadata">{" | ".join(meta_parts)}</p>')

        for section in content.sections:
            parts.append(self._section_html(section))

        parts.append("</body></html>")
        return "\n".join(parts)

    def _section_html(self, section: DocumentSection) -> str:
        level = min(max(section.level + 1, 2), 6)  # h2..h6
        parts: list[str] = [f"<h{level}>{escape(section.heading)}</h{level}>"]

        if section.body:
            parts.append(self._body_html(section.body))

        if section.table:
            parts.append(self._table_html(section.table))

        return "\n".join(parts)

    def _body_html(self, body: str) -> str:
        lines = body.split("\n")
        html_parts: list[str] = []
        in_list = False

        for line in lines:
            stripped = line.strip()
            if not stripped:
                if in_list:
                    html_parts.append("</ul>")
                    in_list = False
                continue

            if stripped.startswith("- "):
                if not in_list:
                    html_parts.append("<ul>")
                    in_list = True
                item = self._inline_format(stripped[2:])
                html_parts.append(f"<li>{item}</li>")
            else:
                if in_list:
                    html_parts.append("</ul>")
                    in_list = False
                html_parts.append(f"<p>{self._inline_format(stripped)}</p>")

        if in_list:
            html_parts.append("</ul>")

        return "\n".join(html_parts)

    @staticmethod
    def _inline_format(text: str) -> str:
        """Handle **bold** and *italic* in HTML."""
        import re

        text = escape(text)
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
        return text

    @staticmethod
    def _table_html(table_data: list[list[str]]) -> str:
        if not table_data:
            return ""

        parts = ["<table>"]
        for r_idx, row in enumerate(table_data):
            parts.append("<tr>")
            tag = "th" if r_idx == 0 else "td"
            for cell in row:
                parts.append(f"<{tag}>{escape(cell)}</{tag}>")
            parts.append("</tr>")
        parts.append("</table>")
        return "\n".join(parts)

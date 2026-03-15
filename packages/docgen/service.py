"""DocGenService facade — generate documents and store them."""
from __future__ import annotations

import re

from packages.docgen.generators.base import DocumentContent, DocumentSection
from packages.docgen.generators.docx_gen import DocxGenerator
from packages.docgen.generators.pdf_gen import PdfGenerator
from packages.docgen.generators.pptx_gen import PptxGenerator
from packages.docgen.generators.xlsx_gen import XlsxGenerator
from packages.storage.service import FileStorageService, StoredFile


class DocGenService:
    """Unified document generation service."""

    def __init__(self, storage: FileStorageService) -> None:
        self._storage = storage
        self._generators = {
            "docx": DocxGenerator(),
            "pptx": PptxGenerator(),
            "xlsx": XlsxGenerator(),
            "pdf": PdfGenerator(),
        }

    def generate(
        self,
        content: DocumentContent,
        format: str = "docx",
        template_path: str | None = None,
        brand: dict | None = None,
        org_id: str = "org-1",
        created_by: str = "friday",
        workspace_id: str | None = None,
    ) -> StoredFile:
        """Generate a document and store it.

        Args:
            content: Structured document content.
            format: Output format — docx | pptx | xlsx | pdf.
            template_path: Optional binary template file path.
            brand: Optional brand dict (primary_color, company_name, …).
            org_id: Org scope for storage.
            created_by: Creator identifier.
            workspace_id: Optional workspace to tag the document with.
        """
        generator = self._generators.get(format)
        if not generator:
            raise ValueError(f"Unsupported format: {format}")

        file_bytes = generator.generate(content, template_path, brand=brand)
        safe_title = re.sub(r"[^\w\s-]", "", content.title).strip().replace(" ", "_")
        filename = f"{safe_title or 'document'}.{generator.file_extension}"

        metadata: dict = {"document_type": content.document_type, "format": format}
        if workspace_id:
            metadata["workspace_id"] = workspace_id

        return self._storage.store(
            content=file_bytes,
            filename=filename,
            mime_type=generator.mime_type,
            org_id=org_id,
            created_by=created_by,
            metadata=metadata,
        )

    def generate_from_template(
        self,
        template_id: str,
        data: dict,
        org_id: str = "org-1",
        brand: dict | None = None,
        workspace_id: str | None = None,
    ) -> StoredFile:
        """Generate a document using a template with variable substitution.

        Replaces ``{{variable_name}}`` placeholders in section bodies with
        values from *data*. The template's document_type determines the output
        format.  Falls back gracefully when the template file doesn't exist on
        disk — the template_path is only used when the file is present.
        """
        from packages.templates.service import TemplateService
        # TemplateService is already wired in FridayService; import lazily here
        # to avoid circular dependency at module load time.
        raise NotImplementedError(
            "generate_from_template() must be called via FridayService which passes "
            "the template object; use DocGenService._generate_from_template_obj() instead."
        )

    def _generate_from_template_obj(
        self,
        template,  # DocumentTemplate dataclass
        data: dict,
        org_id: str = "org-1",
        brand: dict | None = None,
        workspace_id: str | None = None,
    ) -> StoredFile:
        """Internal: generate from a pre-fetched DocumentTemplate + data dict."""
        import os

        fmt = template.document_type  # "docx", "pptx", "xlsx", "pdf"
        title = _substitute(data.get("title", template.name), data)

        # Build a simple document if no sections are provided in data
        sections_data: list[dict] = data.get("sections", [])
        sections: list[DocumentSection] = []
        for sd in sections_data:
            body = _substitute(sd.get("body", ""), data)
            sections.append(DocumentSection(
                heading=_substitute(sd.get("heading", ""), data),
                body=body,
                level=int(sd.get("level", 1)),
                table=sd.get("table"),
                slide_notes=sd.get("slide_notes", ""),
            ))

        if not sections:
            # Fallback: single section with all data as bullet list
            body_lines = [f"- **{k}:** {v}" for k, v in data.items() if k not in ("title", "sections")]
            sections = [DocumentSection(heading="Details", body="\n".join(body_lines), level=1)]

        content = DocumentContent(
            title=title,
            document_type=fmt,
            sections=sections,
            metadata={k: str(v) for k, v in data.items() if k in ("author", "date", "company_name")},
        )

        # Only use template_path if the file actually exists on disk
        tpl_path: str | None = template.template_path if os.path.isfile(template.template_path) else None

        return self.generate(
            content,
            format=fmt,
            template_path=tpl_path,
            brand=brand,
            org_id=org_id,
            workspace_id=workspace_id,
        )

    def supported_formats(self) -> list[str]:
        return list(self._generators.keys())


def _substitute(text: str, data: dict) -> str:
    """Replace {{key}} placeholders in *text* with values from *data*."""
    def replacer(m: re.Match) -> str:  # type: ignore[type-arg]
        key = m.group(1).strip()
        return str(data.get(key, m.group(0)))  # leave unreplaced if key missing

    return re.sub(r"\{\{(\w+)\}\}", replacer, text)

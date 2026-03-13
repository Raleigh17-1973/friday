"""DocGenService facade — generate documents and store them."""
from __future__ import annotations

from packages.docgen.generators.base import DocumentContent
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
        org_id: str = "org-1",
        created_by: str = "friday",
    ) -> StoredFile:
        generator = self._generators.get(format)
        if not generator:
            raise ValueError(f"Unsupported format: {format}")

        file_bytes = generator.generate(content, template_path)
        filename = f"{content.title.replace(' ', '_')}.{generator.file_extension}"

        return self._storage.store(
            content=file_bytes,
            filename=filename,
            mime_type=generator.mime_type,
            org_id=org_id,
            created_by=created_by,
            metadata={"document_type": content.document_type, "format": format},
        )

    def supported_formats(self) -> list[str]:
        return list(self._generators.keys())

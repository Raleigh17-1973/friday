"""Base document generator ABC and data contracts."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DocumentSection:
    heading: str
    body: str  # markdown formatted
    level: int = 1
    table: list[list[str]] | None = None
    chart_spec: dict | None = None
    slide_notes: str = ""


@dataclass
class DocumentContent:
    title: str
    document_type: str  # "memo", "report", "deck", "spreadsheet", "sop", "invoice"
    sections: list[DocumentSection]
    metadata: dict[str, Any] = field(default_factory=dict)  # author, date, confidentiality


class DocumentGenerator(ABC):
    """Abstract base class for all document generators."""

    @abstractmethod
    def generate(
        self, content: DocumentContent, template_path: str | None = None
    ) -> bytes:
        """Generate document bytes from structured content."""
        ...

    @property
    @abstractmethod
    def mime_type(self) -> str: ...

    @property
    @abstractmethod
    def file_extension(self) -> str: ...

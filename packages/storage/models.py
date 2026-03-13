"""Data models for file storage."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from packages.common.models import utc_now_iso


@dataclass
class StoredFile:
    file_id: str
    filename: str
    mime_type: str
    size_bytes: int
    storage_path: str
    created_by: str
    org_id: str
    created_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

"""Persistent file storage service with pluggable backends."""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from packages.storage.models import StoredFile
from packages.storage.repository import FileMetadataRepository


class FileStorageService:
    """Store, retrieve, list, and delete files with metadata persistence."""

    def __init__(self, storage_dir: Path, db_path: Path | None = None) -> None:
        self._storage_dir = storage_dir
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._repo = FileMetadataRepository(db_path=db_path)

    def store(
        self,
        content: bytes,
        filename: str,
        mime_type: str,
        org_id: str = "org-1",
        created_by: str = "friday",
        metadata: dict[str, Any] | None = None,
    ) -> StoredFile:
        file_id = f"file_{uuid.uuid4().hex[:12]}"
        # Preserve extension from filename
        ext = Path(filename).suffix or ""
        storage_name = f"{file_id}{ext}"
        storage_path = self._storage_dir / storage_name
        storage_path.write_bytes(content)

        stored = StoredFile(
            file_id=file_id,
            filename=filename,
            mime_type=mime_type,
            size_bytes=len(content),
            storage_path=str(storage_path),
            created_by=created_by,
            org_id=org_id,
            metadata=metadata or {},
        )
        self._repo.save(stored)
        return stored

    def retrieve(self, file_id: str) -> tuple[StoredFile, bytes]:
        meta = self._repo.get(file_id)
        if meta is None:
            raise KeyError(f"File {file_id!r} not found")
        path = Path(meta.storage_path)
        if not path.exists():
            raise FileNotFoundError(f"File data missing at {path}")
        return meta, path.read_bytes()

    def get_metadata(self, file_id: str) -> StoredFile | None:
        return self._repo.get(file_id)

    def list_files(self, org_id: str = "org-1", limit: int = 50) -> list[StoredFile]:
        return self._repo.list_by_org(org_id, limit=limit)

    def delete(self, file_id: str) -> None:
        meta = self._repo.get(file_id)
        if meta is not None:
            path = Path(meta.storage_path)
            if path.exists():
                path.unlink()
            self._repo.delete(file_id)

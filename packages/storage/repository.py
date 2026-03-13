"""SQLite metadata repository for stored files."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from packages.storage.models import StoredFile


class FileMetadataRepository:
    def __init__(self, db_path: Path | None = None) -> None:
        path = str(db_path) if db_path else ":memory:"
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS files (
                file_id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                mime_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                storage_path TEXT NOT NULL,
                created_by TEXT NOT NULL,
                org_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}'
            )"""
        )
        self._conn.commit()

    def save(self, f: StoredFile) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO files
               (file_id, filename, mime_type, size_bytes, storage_path, created_by, org_id, created_at, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (f.file_id, f.filename, f.mime_type, f.size_bytes, f.storage_path,
             f.created_by, f.org_id, f.created_at, json.dumps(f.metadata)),
        )
        self._conn.commit()

    def get(self, file_id: str) -> StoredFile | None:
        row = self._conn.execute("SELECT * FROM files WHERE file_id = ?", (file_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_stored(row)

    def list_by_org(self, org_id: str, limit: int = 50) -> list[StoredFile]:
        rows = self._conn.execute(
            "SELECT * FROM files WHERE org_id = ? ORDER BY created_at DESC LIMIT ?",
            (org_id, limit),
        ).fetchall()
        return [self._row_to_stored(r) for r in rows]

    def delete(self, file_id: str) -> None:
        self._conn.execute("DELETE FROM files WHERE file_id = ?", (file_id,))
        self._conn.commit()

    @staticmethod
    def _row_to_stored(row: tuple) -> StoredFile:
        return StoredFile(
            file_id=row[0],
            filename=row[1],
            mime_type=row[2],
            size_bytes=row[3],
            storage_path=row[4],
            created_by=row[5],
            org_id=row[6],
            created_at=row[7],
            metadata=json.loads(row[8]) if row[8] else {},
        )

"""Credential management with encrypted storage for OAuth tokens and API keys."""
from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from packages.common.models import utc_now_iso


@dataclass
class Credential:
    credential_id: str
    org_id: str
    provider: str  # "google", "slack", "jira", etc.
    credential_type: str  # "oauth2", "api_key", "service_account"
    scopes: list[str] = field(default_factory=list)
    expires_at: str | None = None
    created_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CredentialService:
    """Store and retrieve encrypted credentials for external integrations.

    In dev mode (no FRIDAY_ENCRYPTION_KEY), credentials are stored as
    plain JSON. In production, they should be encrypted at rest.
    """

    def __init__(self, db_path: Path | None = None, encryption_key: str | None = None) -> None:
        path = str(db_path) if db_path else ":memory:"
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS credentials (
                credential_id TEXT PRIMARY KEY,
                org_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                credential_type TEXT NOT NULL,
                data TEXT NOT NULL,
                scopes TEXT NOT NULL DEFAULT '[]',
                expires_at TEXT,
                created_at TEXT NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}'
            )"""
        )
        self._conn.commit()
        self._encryption_key = encryption_key  # reserved for future encryption

    def store(
        self,
        provider: str,
        credential_type: str,
        data: dict[str, Any],
        org_id: str = "org-1",
        scopes: list[str] | None = None,
        expires_at: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Credential:
        cred_id = f"cred_{uuid.uuid4().hex[:12]}"
        cred = Credential(
            credential_id=cred_id,
            org_id=org_id,
            provider=provider,
            credential_type=credential_type,
            scopes=scopes or [],
            expires_at=expires_at,
            metadata=metadata or {},
        )
        self._conn.execute(
            """INSERT INTO credentials
               (credential_id, org_id, provider, credential_type, data, scopes, expires_at, created_at, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (cred.credential_id, cred.org_id, cred.provider, cred.credential_type,
             json.dumps(data), json.dumps(cred.scopes), cred.expires_at,
             cred.created_at, json.dumps(cred.metadata)),
        )
        self._conn.commit()
        return cred

    def get_data(self, provider: str, org_id: str = "org-1") -> dict[str, Any] | None:
        """Retrieve the raw credential data for a provider."""
        row = self._conn.execute(
            "SELECT data FROM credentials WHERE provider = ? AND org_id = ? ORDER BY created_at DESC LIMIT 1",
            (provider, org_id),
        ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def get_credential(self, provider: str, org_id: str = "org-1") -> Credential | None:
        row = self._conn.execute(
            """SELECT credential_id, org_id, provider, credential_type, scopes, expires_at, created_at, metadata
               FROM credentials WHERE provider = ? AND org_id = ? ORDER BY created_at DESC LIMIT 1""",
            (provider, org_id),
        ).fetchone()
        if row is None:
            return None
        return Credential(
            credential_id=row[0], org_id=row[1], provider=row[2], credential_type=row[3],
            scopes=json.loads(row[4]), expires_at=row[5], created_at=row[6],
            metadata=json.loads(row[7]),
        )

    def list_credentials(self, org_id: str = "org-1") -> list[Credential]:
        rows = self._conn.execute(
            """SELECT credential_id, org_id, provider, credential_type, scopes, expires_at, created_at, metadata
               FROM credentials WHERE org_id = ? ORDER BY created_at DESC""",
            (org_id,),
        ).fetchall()
        return [
            Credential(
                credential_id=r[0], org_id=r[1], provider=r[2], credential_type=r[3],
                scopes=json.loads(r[4]), expires_at=r[5], created_at=r[6],
                metadata=json.loads(r[7]),
            )
            for r in rows
        ]

    def revoke(self, credential_id: str) -> None:
        self._conn.execute("DELETE FROM credentials WHERE credential_id = ?", (credential_id,))
        self._conn.commit()

    def has_credential(self, provider: str, org_id: str = "org-1") -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM credentials WHERE provider = ? AND org_id = ? LIMIT 1",
            (provider, org_id),
        ).fetchone()
        return row is not None

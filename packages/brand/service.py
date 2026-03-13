from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from packages.common.models import utc_now_iso

_DEFAULT_BRAND = {
    "primary_color": "#0f5cc0",
    "secondary_color": "#1a1a2e",
    "accent_color": "#e94560",
    "font_family": "Inter, system-ui, sans-serif",
    "logo_file_id": None,
    "company_name": "Friday",
    "tagline": "Your AI Business Operations Platform",
    "voice_tone": "professional, clear, and helpful",
}


@dataclass
class BrandGuidelines:
    org_id: str
    primary_color: str = _DEFAULT_BRAND["primary_color"]
    secondary_color: str = _DEFAULT_BRAND["secondary_color"]
    accent_color: str = _DEFAULT_BRAND["accent_color"]
    font_family: str = _DEFAULT_BRAND["font_family"]
    logo_file_id: str | None = None
    company_name: str = _DEFAULT_BRAND["company_name"]
    tagline: str = _DEFAULT_BRAND["tagline"]
    voice_tone: str = _DEFAULT_BRAND["voice_tone"]
    updated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self):
        return asdict(self)


class BrandAssetService:
    def __init__(self, db_path: Path | None = None):
        path = str(db_path) if db_path else ":memory:"
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS brand_guidelines (
            org_id TEXT PRIMARY KEY, primary_color TEXT NOT NULL,
            secondary_color TEXT NOT NULL, accent_color TEXT NOT NULL,
            font_family TEXT NOT NULL, logo_file_id TEXT,
            company_name TEXT NOT NULL, tagline TEXT NOT NULL DEFAULT '',
            voice_tone TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL)"""
        )
        self._conn.commit()

    def get_brand(self, org_id: str) -> BrandGuidelines | None:
        r = self._conn.execute(
            "SELECT org_id, primary_color, secondary_color, accent_color, font_family, logo_file_id, company_name, tagline, voice_tone, updated_at FROM brand_guidelines WHERE org_id = ?",
            (org_id,),
        ).fetchone()
        if r is None:
            return None
        return BrandGuidelines(
            org_id=r[0], primary_color=r[1], secondary_color=r[2],
            accent_color=r[3], font_family=r[4], logo_file_id=r[5],
            company_name=r[6], tagline=r[7], voice_tone=r[8], updated_at=r[9],
        )

    def update_brand(self, org_id: str, changes: dict[str, Any]) -> BrandGuidelines:
        existing = self.get_brand(org_id)
        if existing is None:
            brand = BrandGuidelines(org_id=org_id, **{k: v for k, v in changes.items() if k != "org_id"})
            self._conn.execute(
                "INSERT INTO brand_guidelines (org_id, primary_color, secondary_color, accent_color, font_family, logo_file_id, company_name, tagline, voice_tone, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (brand.org_id, brand.primary_color, brand.secondary_color, brand.accent_color,
                 brand.font_family, brand.logo_file_id, brand.company_name, brand.tagline,
                 brand.voice_tone, brand.updated_at),
            )
        else:
            d = existing.to_dict()
            d.update(changes)
            d["updated_at"] = utc_now_iso()
            brand = BrandGuidelines(**{k: v for k, v in d.items()})
            self._conn.execute(
                "UPDATE brand_guidelines SET primary_color=?, secondary_color=?, accent_color=?, font_family=?, logo_file_id=?, company_name=?, tagline=?, voice_tone=?, updated_at=? WHERE org_id=?",
                (brand.primary_color, brand.secondary_color, brand.accent_color,
                 brand.font_family, brand.logo_file_id, brand.company_name, brand.tagline,
                 brand.voice_tone, brand.updated_at, brand.org_id),
            )
        self._conn.commit()
        return brand

    def get_brand_or_default(self, org_id: str) -> BrandGuidelines:
        brand = self.get_brand(org_id)
        if brand is not None:
            return brand
        return BrandGuidelines(org_id=org_id)

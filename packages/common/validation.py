from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any


def validate_required_fields(payload: Any, schema: dict[str, Any], schema_name: str) -> None:
    if is_dataclass(payload):
        data = asdict(payload)
    elif isinstance(payload, dict):
        data = payload
    else:
        raise TypeError(f"{schema_name} payload must be a dataclass or dict")

    required = schema.get("required", [])
    missing = [field for field in required if field not in data]
    if missing:
        raise ValueError(f"{schema_name} missing required fields: {', '.join(missing)}")

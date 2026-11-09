"""Błędy domenowe. Każda ścieżka (REST/UI/MCP) decyduje, ile z tej informacji pokazać."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any


@dataclass
class DomainError(Exception):
    code: str
    message: str
    http_status: int = 400
    field: str | None = None
    expected: str | None = None
    example: str | None = None
    details: dict[str, Any] = dataclasses.field(default_factory=dict)

    def __str__(self) -> str:  # pragma: no cover - debug
        return f"{self.code}: {self.message}"

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"code": self.code, "message": self.message}
        for key in ("field", "expected", "example"):
            value = getattr(self, key)
            if value is not None:
                out[key] = value
        out.update(self.details)
        return out

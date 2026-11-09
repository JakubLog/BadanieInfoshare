"""Wspólny interfejs środowisk (UI / REST / MCP) dla pętli agenta."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ToolResult:
    text: str
    is_error: bool = False
    meta: dict[str, Any] = field(default_factory=dict)


class Env(Protocol):
    path: str
    tools: list[dict]

    async def start(self) -> None: ...

    def system_prompt(self) -> str: ...

    async def call(self, name: str, args: dict) -> ToolResult: ...

    async def close(self) -> None: ...

    def tool_key(self, name: str, args: dict) -> str:
        """Klucz „tego samego narzędzia” dla metryki samonaprawy (REST: metoda + szablon ścieżki)."""
        ...

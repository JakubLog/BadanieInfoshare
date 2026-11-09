"""Ścieżka MCP: osobny proces serwera stdio na przebieg, klient z oficjalnego SDK `mcp`."""

from __future__ import annotations

import json
import os
import sys
from contextlib import AsyncExitStack
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from harness.envs.base import ToolResult
from klubfit.db import ROOT
from klubfit.flags import McpFlags, flags_dict


class McpEnv:
    path = "mcp"

    def __init__(self, db_path: str | Path, flags: McpFlags):
        self.db_path = str(db_path)
        self.flags = flags
        self.tools: list[dict] = []
        self._stack = AsyncExitStack()
        self.client: Client | None = None

    async def start(self) -> None:
        env = {**os.environ, "KLUBFIT_DB": self.db_path, "KLUBFIT_MCP_FLAGS": json.dumps(flags_dict(self.flags)),
               "PYTHONPATH": str(ROOT)}
        env.pop("ANTHROPIC_API_KEY", None)  # serwer MCP nie potrzebuje klucza
        params = StdioServerParameters(command=sys.executable, args=["-m", "klubfit.mcp.server"], env=env, cwd=str(ROOT))
        self.client = await self._stack.enter_async_context(Client(params, read_timeout_seconds=30))
        listed = await self.client.list_tools()
        self.tools = [{"name": t.name, "description": t.description or "", "input_schema": t.input_schema}
                      for t in listed.tools]

    def system_prompt(self) -> str:
        return "Masz dostęp do systemu klubu przez narzędzia serwera MCP."

    def tool_key(self, name: str, args: dict) -> str:
        return name

    async def call(self, name: str, args: dict) -> ToolResult:
        assert self.client is not None
        res = await self.client.call_tool(name, args)
        text = "\n".join(getattr(c, "text", "") for c in res.content)
        return ToolResult(text, is_error=bool(res.is_error))

    async def close(self) -> None:
        await self._stack.aclose()

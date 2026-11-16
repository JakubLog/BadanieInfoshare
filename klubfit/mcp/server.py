"""Serwer MCP (stdio). Konfiguracja z env: KLUBFIT_DB (ścieżka bazy), KLUBFIT_MCP_FLAGS (JSON z flagami).

Uruchomienie: python -m klubfit.mcp.server
"""

from __future__ import annotations

import json
import os

import anyio
from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from klubfit.db import connect
from klubfit.flags import make_flags
from klubfit.mcp.tools import McpState, build_toolset, describe, run_tool


def build_server(db_path: str, flags_json: str) -> Server:
    flags = make_flags("mcp", json.loads(flags_json or "{}"))
    state = McpState(connect(db_path), flags)
    specs = build_toolset(flags)
    by_name = {t.name: t for t in specs}

    async def on_list_tools(ctx, params) -> types.ListToolsResult:
        return types.ListToolsResult(tools=[
            types.Tool(name=t.name, description=describe(t, flags), input_schema=t.schema) for t in specs])

    async def on_call_tool(ctx, params: types.CallToolRequestParams) -> types.CallToolResult:
        text, is_error = run_tool(state, by_name, params.name, params.arguments or {})
        return types.CallToolResult(content=[types.TextContent(type="text", text=text)], is_error=is_error)

    return Server("klubfit", version="1.0", on_list_tools=on_list_tools, on_call_tool=on_call_tool)


async def _main() -> None:
    server = build_server(os.environ["KLUBFIT_DB"], os.environ.get("KLUBFIT_MCP_FLAGS", "{}"))
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    anyio.run(_main)

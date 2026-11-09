"""Ścieżka REST: agent ma jedno narzędzie http_request i skróconą dokumentację API w prompcie."""

from __future__ import annotations

import json
import re
from pathlib import Path

import httpx

from harness.envs.base import ToolResult
from klubfit.api.reference import build_reference
from klubfit.api.rest import create_rest_app
from klubfit.flags import RestFlags

TOOLS = [{
    "name": "http_request",
    "description": "Wysyła żądanie HTTP do REST API Klubu Fit i zwraca kod statusu oraz treść odpowiedzi.",
    "input_schema": {"type": "object", "properties": {
        "method": {"type": "string", "enum": ["GET", "POST", "DELETE"]},
        "path": {"type": "string", "description": "Ścieżka, np. /clients"},
        "query": {"type": "object", "description": "Parametry zapytania (opcjonalnie)."},
        "body": {"type": "object", "description": "Treść JSON dla POST (opcjonalnie)."}},
        "required": ["method", "path"]},
}]
SEGMENTS = {"clients", "classes", "bookings", "memberships"}


class RestEnv:
    path = "rest"
    tools = TOOLS

    def __init__(self, db_path: str | Path, flags: RestFlags):
        self.flags = flags
        self.app = create_rest_app(db_path, flags)
        self.client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://klubfit.local",
                                        timeout=30)

    def system_prompt(self) -> str:
        return "Masz dostęp do systemu klubu przez REST API.\n\n" + build_reference(self.flags)

    def tool_key(self, name: str, args: dict) -> str:
        """Metoda + szablon ścieżki, np. 'GET /clients/{id}/bookings'."""
        path = str(args.get("path", "")).split("?")[0].strip("/")
        parts = path.split("/") if path else []
        tmpl = [p if p in SEGMENTS else "{id}" for p in parts]
        return f"{str(args.get('method', 'GET')).upper()} /" + "/".join(tmpl)

    async def call(self, name: str, args: dict) -> ToolResult:
        assert self.client is not None
        if name != "http_request":
            return ToolResult(f"Nieznane narzędzie: {name}", is_error=True)
        method = str(args.get("method", "GET")).upper()
        path = str(args.get("path", "/"))
        if path.startswith("http"):
            path = re.sub(r"^https?://[^/]+", "", path)
        query = args.get("query") or None
        if isinstance(query, dict):
            query = {k: (json.dumps(v) if isinstance(v, (dict, list)) else str(v)) for k, v in query.items()}
        body = args.get("body")
        resp = await self.client.request(method, path if path.startswith("/") else "/" + path, params=query,
                                         json=body if method == "POST" else None)
        return ToolResult(f"HTTP {resp.status_code}\n{resp.text}", is_error=resp.status_code >= 400,
                          meta={"status": resp.status_code})

    async def close(self) -> None:
        if self.client is not None:
            await self.client.aclose()
        self.app.state.api.conn.close()

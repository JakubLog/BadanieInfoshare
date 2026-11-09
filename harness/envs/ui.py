"""Ścieżka UI: panel HTML serwowany przez uvicorn, agent steruje Chromium przez Playwright.

Agent nie dostaje zrzutów ekranu: tylko drzewo dostępności (ARIA snapshot) i cztery narzędzia.
"""

from __future__ import annotations

import asyncio
import threading

import uvicorn
from playwright.async_api import Browser, Error as PlaywrightError, TimeoutError as PlaywrightTimeout

from harness.envs.base import ToolResult
from klubfit.flags import UiFlags
from klubfit.ui.app import create_ui_app

TOOLS = [
    {"name": "snapshot", "description": "Zwraca adres URL i drzewo dostępności (ARIA snapshot) bieżącej strony.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "click",
     "description": ("Klika element o podanej roli ARIA (np. button, link, checkbox) i nazwie dostępnej "
                     "(dopasowanie fragmentu, bez rozróżniania wielkości liter). Rola 'text' klika element "
                     "po widocznym tekście. Gdy pasuje kilka elementów, podaj index (liczony od 0)."),
     "input_schema": {"type": "object", "properties": {
         "role": {"type": "string"}, "name": {"type": "string"},
         "index": {"type": "integer", "minimum": 0}}, "required": ["role", "name"]}},
    {"name": "fill",
     "description": ("Wpisuje wartość w pole formularza wskazane etykietą (albo nazwą dostępną lub "
                     "placeholderem pola). Dla list rozwijanych wybiera opcję o podanym tekście."),
     "input_schema": {"type": "object", "properties": {
         "label": {"type": "string"}, "value": {"type": "string"}}, "required": ["label", "value"]}},
    {"name": "goto", "description": "Otwiera podany adres URL (bezwzględny lub względny względem panelu).",
     "input_schema": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}},
]
FIELD_ROLES = ("textbox", "searchbox", "combobox", "spinbutton")


class _Server:
    def __init__(self, app):
        self.server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error",
                                                    lifespan="off", access_log=False))
        self.server.install_signal_handlers = lambda: None  # type: ignore[method-assign]
        self.thread = threading.Thread(target=self.server.run, daemon=True)

    async def start(self) -> int:
        self.thread.start()
        for _ in range(200):
            if self.server.started:
                return self.server.servers[0].sockets[0].getsockname()[1]
            await asyncio.sleep(0.025)
        raise RuntimeError("Serwer UI nie wystartował")

    async def stop(self) -> None:
        self.server.should_exit = True
        await asyncio.to_thread(self.thread.join, 5)


class UiEnv:
    path = "ui"
    tools = TOOLS

    def __init__(self, db_path, flags: UiFlags, browser: Browser):
        self.flags = flags
        self.browser = browser
        self._server = _Server(create_ui_app(db_path, flags))
        self.base = ""
        self.context = None
        self.page = None

    async def start(self) -> None:
        port = await self._server.start()
        self.base = f"http://127.0.0.1:{port}"
        self.context = await self.browser.new_context(viewport={"width": 1280, "height": 900}, locale="pl-PL")
        self.page = await self.context.new_page()
        self.page.set_default_timeout(5000)
        await self.page.goto(self.base + "/")

    def system_prompt(self) -> str:
        return (f"Pracujesz w panelu recepcji Klubu Fit otwartym w przeglądarce pod adresem {self.base}/ . "
                "Nie widzisz ekranu. Stan strony poznajesz narzędziem snapshot(), a działasz narzędziami "
                "click(), fill() i goto().")

    def tool_key(self, name: str, args: dict) -> str:
        return name

    async def _settle(self) -> None:
        await self.page.wait_for_timeout(250)
        try:
            await self.page.wait_for_load_state("load", timeout=5000)
        except PlaywrightTimeout:
            pass

    async def call(self, name: str, args: dict) -> ToolResult:
        page = self.page
        try:
            if name == "snapshot":
                tree = await page.locator("body").aria_snapshot()
                return ToolResult(f"URL: {page.url}\n{tree}")
            if name == "goto":
                url = str(args.get("url", ""))
                if not url.startswith("http"):
                    url = self.base + "/" + url.lstrip("/")
                resp = await page.goto(url)
                status = resp.status if resp else 0
                return ToolResult(f"Otwarto {page.url} (HTTP {status}).", is_error=status >= 400)
            if name == "click":
                role, label = str(args.get("role", "")), str(args.get("name", ""))
                loc = page.get_by_text(label) if role == "text" else page.get_by_role(role, name=label)
                n = await loc.count()
                if n == 0:
                    return ToolResult(f"Nie znaleziono elementu: role={role!r}, name={label!r}.", is_error=True)
                idx = args.get("index")
                if n > 1 and idx is None:
                    return ToolResult(f"Pasuje {n} elementów (role={role!r}, name={label!r}). Podaj index 0..{n - 1}.",
                                      is_error=True)
                idx = int(idx or 0)
                if idx >= n:
                    return ToolResult(f"index {idx} poza zakresem 0..{n - 1}.", is_error=True)
                await loc.nth(idx).click()
                await self._settle()
                return ToolResult(f"Kliknięto. URL: {page.url}")
            if name == "fill":
                label, value = str(args.get("label", "")), str(args.get("value", ""))
                loc = page.get_by_label(label)
                if await loc.count() == 0:
                    candidates = [page.get_by_role(role, name=label) for role in FIELD_ROLES]
                    candidates.append(page.get_by_placeholder(label))
                    for cand in candidates:
                        if await cand.count():
                            loc = cand
                            break
                n = await loc.count()
                if n == 0:
                    return ToolResult(f"Nie znaleziono pola: {label!r}.", is_error=True)
                if n > 1:
                    return ToolResult(f"Pasuje {n} pól o etykiecie {label!r}. Doprecyzuj etykietę.", is_error=True)
                el = loc.first
                tag = await el.evaluate("e => e.tagName.toLowerCase()")
                if tag == "select":
                    await el.select_option(label=value)
                else:
                    await el.fill(value)
                return ToolResult(f"Wpisano wartość w pole {label!r}.")
            return ToolResult(f"Nieznane narzędzie: {name}", is_error=True)
        except PlaywrightTimeout as e:
            return ToolResult(f"Przekroczono czas oczekiwania: {str(e).splitlines()[0]}", is_error=True)
        except PlaywrightError as e:
            return ToolResult(f"Błąd przeglądarki: {str(e).splitlines()[0]}", is_error=True)

    async def close(self) -> None:
        try:
            if self.context is not None:
                await self.context.close()
        finally:
            await self._server.stop()

"""Definicje narzędzi MCP i ich obsługa. Wszystkie operacje idą przez `klubfit.domain.services`.

Warianty:
- ziarnistość: 5 narzędzi 1:1 z endpointami (granular) albo jedno zadaniowe `book_class` (task),
- opisy: jedno zdanie (short) albo pełny opis (full),
- liczba narzędzi: 5 / 20 / 60 / 60 z przestrzeniami nazw (narzędzia dodatkowe w extra_tools.py),
- nieodwracalne akcje: `create_booking` (direct) albo `prepare_booking` + `confirm_booking` (confirm).
"""

from __future__ import annotations

import json
import secrets
import sqlite3
from dataclasses import dataclass, field
from datetime import time
from typing import Any, Callable

from klubfit.clock import TODAY, utc_iso_to_local
from klubfit.domain import services as svc
from klubfit.domain.errors import DomainError
from klubfit.flags import McpFlags


@dataclass
class ToolSpec:
    name: str
    short: str
    full: str
    schema: dict
    handler: Callable[["McpState", dict], Any]
    namespace: str = "zajecia"
    group: str = "base"  # base | task | confirm | extra


@dataclass
class McpState:
    conn: sqlite3.Connection
    flags: McpFlags
    tokens: dict[str, dict] = field(default_factory=dict)
    writes: int = 0


def _obj(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required}


def _s(desc: str) -> dict:
    return {"type": "string", "description": desc}


def _local_iso(starts_at: str) -> str:
    return utc_iso_to_local(starts_at).isoformat()


def _membership(m: dict | None) -> dict | None:
    if not m:
        return None
    return {"plan": m["plan"], "status": m["status"], "valid_from": m["valid_from"], "valid_to": m["valid_to"]}


def _client_card(c: dict) -> dict:
    return {"client_id": c["id"], "name": f"{c['first_name']} {c['last_name']}", "email": c["email"],
            "phone": c["phone"], "notes": c["notes"] or None}


def _class_card(k: dict) -> dict:
    return {"class_id": k["id"], "name": k["name"], "type": k["type"], "starts_at": _local_iso(k["starts_at"]),
            "duration_min": k["duration_min"], "room": k["room"], "trainer": k["trainer"]}


def _id(args: dict, key: str) -> str:
    return svc.ensure_uuid(svc.require(args.get(key), key, "UUID", svc.EXAMPLE_UUID), key)


def _maybe_fault(state: McpState) -> None:
    """Warunek środowiska w eksperymencie idempotencji: pierwszy zapis się wykonuje, ale odpowiedź ginie."""
    state.writes += 1
    if state.flags.fault == "timeout_first_write" and state.writes == 1:
        raise DomainError("UPSTREAM_TIMEOUT", "Przekroczono czas odpowiedzi systemu rezerwacji (30 s). "
                          "Stan operacji jest nieznany.", 504)


# --- narzędzia bazowe (1:1 z endpointami REST) ---------------------------------------------
def h_search_clients(state: McpState, args: dict) -> dict:
    q = svc.require(args.get("query"), "query", "fragment imienia, nazwiska lub e-maila", "Anna Kowalska")
    rows = svc.search_clients(state.conn, q=str(q))
    return {"total": len(rows), "results": [_client_card(c) for c in rows[:20]]}


def h_get_client(state: McpState, args: dict) -> dict:
    cid = _id(args, "client_id")
    c = svc.get_client(state.conn, cid)
    m = svc.current_membership(state.conn, cid, TODAY) or svc.latest_membership(state.conn, cid)
    bookings = []
    for b in svc.client_bookings(state.conn, cid):
        k = svc.get_class(state.conn, b["class_id"])
        bookings.append({"booking_id": b["id"], "class_id": k["id"], "class": svc.class_label(k)})
    return {**_client_card(c), "membership": _membership(m), "upcoming_bookings": bookings}


def h_list_classes(state: McpState, args: dict) -> dict:
    d = svc.parse_date(args.get("date"), "date")
    rows = svc.list_classes(state.conn, on=d, class_type=args.get("type") or None)
    return {"date": d.isoformat(), "timezone": "Europe/Warsaw", "classes": [_class_card(k) for k in rows]}


def h_get_class_availability(state: McpState, args: dict) -> dict:
    k = svc.get_class(state.conn, _id(args, "class_id"))
    booked = svc.booked_count(state.conn, k["id"])
    return {"class_id": k["id"], "class": svc.class_label(k), "capacity": k["capacity"], "booked": booked,
            "spots_left": k["capacity"] - booked}


def _booking_out(state: McpState, b: dict) -> dict:
    k = svc.get_class(state.conn, b["class_id"])
    c = svc.get_client(state.conn, b["client_id"])
    return {"booking_id": b["id"], "status": b["status"], "client": f"{c['first_name']} {c['last_name']}",
            "class": svc.class_label(k)}


def h_create_booking(state: McpState, args: dict) -> dict:
    b = svc.create_booking(state.conn, _id(args, "client_id"), _id(args, "class_id"), source="mcp", created_by="mcp")
    _maybe_fault(state)
    return _booking_out(state, b)


# [variant:idempotency=confirm]
def h_prepare_booking(state: McpState, args: dict) -> dict:
    client, cls = svc.check_booking(state.conn, _id(args, "client_id"), _id(args, "class_id"))
    token = "cf_" + secrets.token_hex(8)
    state.tokens[token] = {"client_id": client["id"], "class_id": cls["id"], "booking": None}
    return {"confirmation_token": token,
            "summary": f"{client['first_name']} {client['last_name']} → {svc.class_label(cls)}",
            "note": "Rezerwacja NIE została jeszcze utworzona. Wywołaj confirm_booking z tym tokenem. "
                    "Ponowne wywołanie confirm_booking z tym samym tokenem jest bezpieczne i nie utworzy "
                    "drugiej rezerwacji."}


def h_confirm_booking(state: McpState, args: dict) -> dict:
    token = str(svc.require(args.get("confirmation_token"), "confirmation_token", "token z prepare_booking", "cf_1a2b3c4d5e6f7a8b"))
    entry = state.tokens.get(token)
    if entry is None:
        raise DomainError("INVALID_TOKEN", "Nieznany token potwierdzenia. Wywołaj najpierw prepare_booking.", 404,
                          field="confirmation_token")
    if entry["booking"] is not None:
        return {**_booking_out(state, svc.get_booking(state.conn, entry["booking"])), "already_confirmed": True}
    b = svc.create_booking(state.conn, entry["client_id"], entry["class_id"], source="mcp", created_by="mcp")
    entry["booking"] = b["id"]
    _maybe_fault(state)
    return {**_booking_out(state, b), "already_confirmed": False}
# [/variant]


# [variant:granularity=task]
def h_book_class(state: McpState, args: dict) -> dict:
    conn = state.conn
    who = str(svc.require(args.get("client"), "client", "imię i nazwisko albo e-mail", "Anna Kowalska"))
    name = str(svc.require(args.get("class_name"), "class_name", "nazwa zajęć", "Joga"))
    d = svc.parse_date(args.get("date"), "date")
    hhmm = str(svc.require(args.get("time"), "time", "HH:MM (czas lokalny)", "18:00")).strip()
    try:
        h, m = map(int, hhmm.split(":"))
        wanted = time(h, m)
    except ValueError:
        raise DomainError("INVALID_TIME_FORMAT", "Pole 'time' musi mieć format HH:MM (czas lokalny).", 422,
                          field="time", expected="HH:MM", example="18:00") from None
    clients = svc.search_clients(conn, email=who) if "@" in who else svc.search_clients(conn, q=who)
    if "@" not in who:
        exact = [c for c in clients if f"{c['first_name']} {c['last_name']}".lower() == who.lower()]
        clients = exact or clients
    if not clients:
        raise DomainError("CLIENT_NOT_FOUND", f"Nie znaleziono klienta '{who}'.", 404, field="client")
    if len(clients) > 1:
        raise DomainError("AMBIGUOUS_CLIENT", f"Pasuje {len(clients)} klientów. Podaj e-mail w polu 'client'.", 409,
                          field="client", details={"candidates": [
                              {"name": f"{c['first_name']} {c['last_name']}", "email": c["email"]} for c in clients[:10]]})
    day = svc.list_classes(conn, on=d)
    matches = [k for k in day if k["name"].lower() == name.strip().lower() and utc_iso_to_local(k["starts_at"]).time() == wanted]
    if not matches:
        raise DomainError("CLASS_NOT_FOUND", f"Brak zajęć '{name}' o {hhmm} w dniu {d.isoformat()}.", 404,
                          field="class_name", details={"classes_that_day": [svc.class_label(k) for k in day]})
    try:
        b = svc.create_booking(conn, clients[0]["id"], matches[0]["id"], source="mcp", created_by="mcp")
    except DomainError as e:
        alts = e.details.get("next_available")
        if alts:
            e.details["next_available"] = [
                {"class": a["label"], "date": utc_iso_to_local(a["starts_at"]).date().isoformat(),
                 "time": f"{utc_iso_to_local(a['starts_at']):%H:%M}"} for a in alts]
        raise
    out = _booking_out(state, b)
    out["spots_left"] = svc.spots_left(conn, matches[0])
    return out
# [/variant]


CLIENT_ID = _s("Identyfikator klienta (UUID) z wyniku search_clients.")
CLASS_ID = _s("Identyfikator zajęć (UUID) z wyniku list_classes.")

BASE_TOOLS = [
    ToolSpec(
        "search_clients", "Wyszukuje klientów.",
        # [variant:descriptions=full]
        "Wyszukuje klientów klubu po fragmencie imienia, nazwiska lub adresu e-mail (bez rozróżniania wielkości "
        "liter i polskich znaków). Używaj, aby ustalić client_id przed innymi operacjami. Nie używaj do "
        "sprawdzania karnetu ani rezerwacji (służy do tego get_client). Wyszukiwanie dopasowuje fragmenty, więc "
        "'Anna Kowalska' zwróci też np. 'Hanna Kowalska'; przy kilku wynikach rozróżniaj klientów po e-mailu. "
        "Zwraca maks. 20 wyników oraz pole total z łączną liczbą dopasowań.",
        # [/variant]
        _obj({"query": _s("Fragment imienia, nazwiska lub e-maila.")}, ["query"]), h_search_clients),
    ToolSpec(
        "get_client", "Zwraca dane klienta.",
        # [variant:descriptions=full]
        "Zwraca dane klienta: kontakt, aktualny karnet (plan, status, daty ważności), notatki recepcji oraz "
        "listę nadchodzących aktywnych rezerwacji z booking_id. Używaj, aby sprawdzić karnet przed zapisem "
        "albo zweryfikować, czy rezerwacja faktycznie powstała. Wymaga client_id (UUID) z search_clients; "
        "nie przyjmuje imienia ani e-maila.",
        # [/variant]
        _obj({"client_id": CLIENT_ID}, ["client_id"]), h_get_client),
    ToolSpec(
        "list_classes", "Zwraca grafik zajęć na dany dzień.",
        # [variant:descriptions=full]
        "Zwraca wszystkie zajęcia w danym dniu (czas lokalny Europe/Warsaw) z class_id, nazwą, godziną "
        "rozpoczęcia, salą i trenerem. Parametr date w formacie YYYY-MM-DD (np. 2026-11-12); opcjonalny type "
        "(joga, pilates, crossfit, spinning, zumba) zawęża wynik. Tego samego dnia mogą być zajęcia o tej "
        "samej godzinie w różnych salach, więc sprawdzaj nazwę i godzinę. Nie zwraca liczby wolnych miejsc "
        "(służy do tego get_class_availability).",
        # [/variant]
        _obj({"date": _s("Data zajęć."), "type": _s("Typ zajęć (opcjonalnie).")}, ["date"]), h_list_classes),
    ToolSpec(
        "get_class_availability", "Zwraca liczbę wolnych miejsc na zajęciach.",
        # [variant:descriptions=full]
        "Zwraca limit miejsc, liczbę aktywnych zapisów i liczbę wolnych miejsc (spots_left) dla zajęć o "
        "podanym class_id. Używaj przed zapisem, gdy zajęcia mogą być pełne. Gdy spots_left = 0, zapis się nie "
        "uda: wybierz inne zajęcia z list_classes (np. kolejny termin tego samego typu).",
        # [/variant]
        _obj({"class_id": CLASS_ID}, ["class_id"]), h_get_class_availability),
    ToolSpec(
        "create_booking", "Zapisuje klienta na zajęcia.",
        # [variant:descriptions=full]
        "Tworzy rezerwację klienta na zajęcia (operacja zapisująca, nieodwracalna bez cancel). Wymaga "
        "client_id i class_id (UUID). System sprawdza ważność karnetu na dzień zajęć, limit miejsc i kolizje z "
        "innymi rezerwacjami klienta; błąd zwraca kod (np. CLASS_FULL, MEMBERSHIP_INVALID, SCHEDULE_CONFLICT). "
        "Uwaga: system NIE blokuje ponownego zapisu tej samej osoby na te same zajęcia, więc nie powtarzaj "
        "wywołania po niejasnym błędzie, tylko sprawdź get_client. Zwraca booking_id.",
        # [/variant]
        _obj({"client_id": CLIENT_ID, "class_id": CLASS_ID}, ["client_id", "class_id"]), h_create_booking),
]

CONFIRM_TOOLS = [
    ToolSpec(
        "prepare_booking", "Przygotowuje rezerwację do potwierdzenia.",
        # [variant:descriptions=full]
        "Sprawdza, czy klienta można zapisać na zajęcia (karnet, limit miejsc, kolizje), i zwraca "
        "confirmation_token oraz podsumowanie. NIE tworzy rezerwacji. Aby ją utworzyć, wywołaj confirm_booking "
        "z otrzymanym tokenem.",
        # [/variant]
        _obj({"client_id": CLIENT_ID, "class_id": CLASS_ID}, ["client_id", "class_id"]), h_prepare_booking,
        group="confirm"),
    ToolSpec(
        "confirm_booking", "Potwierdza przygotowaną rezerwację.",
        # [variant:descriptions=full]
        "Tworzy rezerwację przygotowaną przez prepare_booking. Token działa jak klucz idempotencji: ponowne "
        "wywołanie z tym samym tokenem zwraca tę samą rezerwację (already_confirmed = true) i nie tworzy "
        "duplikatu, więc po błędzie lub przekroczeniu czasu można bezpiecznie ponowić wywołanie.",
        # [/variant]
        _obj({"confirmation_token": _s("Token z prepare_booking.")}, ["confirmation_token"]), h_confirm_booking,
        group="confirm"),
]

TASK_TOOL = ToolSpec(
    "book_class", "Zapisuje klienta na zajęcia podane nazwą, datą i godziną.",
    # [variant:descriptions=full]
    "Zapisuje klienta na zajęcia w jednym kroku: odnajduje klienta (imię i nazwisko albo e-mail), zajęcia "
    "(nazwa, data YYYY-MM-DD, godzina HH:MM czasu lokalnego), sprawdza karnet, limit miejsc i kolizje, po "
    "czym tworzy rezerwację. Gdy klient jest niejednoznaczny, zwraca AMBIGUOUS_CLIENT z kandydatami (podaj "
    "wtedy e-mail). Gdy zajęcia są pełne, zwraca CLASS_FULL z listą najbliższych wolnych terminów.",
    # [/variant]
    _obj({"client": _s("Imię i nazwisko albo e-mail klienta."), "class_name": _s("Nazwa zajęć, np. Joga."),
          "date": _s("Data zajęć."), "time": _s("Godzina rozpoczęcia.")}, ["client", "class_name", "date", "time"]),
    h_book_class, group="task")


def build_toolset(flags: McpFlags) -> list[ToolSpec]:
    from klubfit.mcp.extra_tools import EXTRA_TOOLS

    if flags.granularity == "task":
        tools = [TASK_TOOL]
    else:
        tools = list(BASE_TOOLS)
        if flags.idempotency == "confirm":
            tools = [t for t in tools if t.name != "create_booking"] + CONFIRM_TOOLS
    n_extra = {"5": 0, "20": 15, "60": 55, "60ns": 55}[flags.toolcount]
    tools = tools + EXTRA_TOOLS[:n_extra]
    if flags.toolcount == "60ns":
        tools = [ToolSpec(f"{t.namespace}_{t.name}", t.short, t.full, t.schema, t.handler, t.namespace, t.group)
                 for t in tools]
    return tools


def describe(tool: ToolSpec, flags: McpFlags) -> str:
    return tool.full if flags.descriptions == "full" and tool.group != "extra" else tool.short


def run_tool(state: McpState, tools: dict[str, ToolSpec], name: str, args: dict) -> tuple[str, bool]:
    tool = tools.get(name)
    if tool is None:
        return json.dumps({"error": {"code": "UNKNOWN_TOOL", "message": f"Nieznane narzędzie: {name}"}},
                          ensure_ascii=False), True
    try:
        return json.dumps(tool.handler(state, args or {}), ensure_ascii=False), False
    except DomainError as e:
        return json.dumps({"error": e.as_dict()}, ensure_ascii=False), True

"""Logika domenowa Klubu Fit. Wszystkie ścieżki (REST, UI, MCP) wołają wyłącznie te funkcje.

Znana cecha systemu (celowo, jak w wielu systemach legacy): kontrola kolizji obejmuje tylko
INNE zajęcia nachodzące czasowo. Ponowny zapis tej samej osoby na te same zajęcia nie jest
blokowany (historycznie: „rezerwacja z osobą towarzyszącą”), więc ponowienie żądania
tworzy duplikat. To właśnie mierzy eksperyment z idempotencją.
"""

from __future__ import annotations

import re
import sqlite3
import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from klubfit.clock import NOW_LOCAL, TZ, now_utc_iso, utc_iso_to_local
from klubfit.domain.errors import DomainError
from klubfit.seed import strip_accents

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
EXAMPLE_DATE = "2026-11-12"
EXAMPLE_UUID = "3f2b8c1e-5d4a-4e6f-9a7b-1c2d3e4f5a6b"


# --- walidacja wejścia -------------------------------------------------------------------
def parse_date(value: str | None, field: str = "date") -> date:
    if value is None or not DATE_RE.match(str(value).strip()):
        raise DomainError("INVALID_DATE_FORMAT", f"Pole '{field}' musi być datą w formacie YYYY-MM-DD.",
                          422, field=field, expected="YYYY-MM-DD", example=EXAMPLE_DATE)
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        raise DomainError("INVALID_DATE_FORMAT", f"Pole '{field}' zawiera nieistniejącą datę.",
                          422, field=field, expected="YYYY-MM-DD", example=EXAMPLE_DATE) from None


def ensure_uuid(value: str | None, field: str) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise DomainError("INVALID_ID", f"Pole '{field}' musi być identyfikatorem UUID.", 422,
                          field=field, expected="UUID", example=EXAMPLE_UUID) from None


def require(value, field: str, expected: str, example: str):
    if value in (None, ""):
        raise DomainError("MISSING_FIELD", f"Brak wymaganego pola '{field}'.", 422,
                          field=field, expected=expected, example=example)
    return value


def _norm(text: str) -> str:
    return strip_accents(text or "").lower()


def _dicts(rows) -> list[dict]:
    return [dict(r) for r in rows]


# --- klienci -----------------------------------------------------------------------------
def search_clients(conn: sqlite3.Connection, q: str | None = None, email: str | None = None) -> list[dict]:
    rows = _dicts(conn.execute("SELECT * FROM clients WHERE deleted_at = '' ORDER BY last_name, first_name, email"))
    if email:
        rows = [r for r in rows if r["email"].lower() == email.strip().lower()]
    if q:
        tokens = _norm(q).split()
        rows = [r for r in rows
                if all(t in _norm(f"{r['first_name']} {r['last_name']} {r['email']}") for t in tokens)]
    return rows


def get_client(conn: sqlite3.Connection, client_id: str) -> dict:
    row = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    if row is None:
        raise DomainError("CLIENT_NOT_FOUND", f"Nie znaleziono klienta o id '{client_id}'.", 404, field="client_id")
    return dict(row)


def client_memberships(conn: sqlite3.Connection, client_id: str) -> list[dict]:
    get_client(conn, client_id)
    return _dicts(conn.execute("SELECT * FROM memberships WHERE client_id = ? ORDER BY valid_to DESC", (client_id,)))


def current_membership(conn: sqlite3.Connection, client_id: str, on: date) -> dict | None:
    for m in client_memberships(conn, client_id):
        if m["status"] == "active" and m["valid_from"] <= on.isoformat() <= m["valid_to"]:
            return m
    return None


def latest_membership(conn: sqlite3.Connection, client_id: str) -> dict | None:
    ms = client_memberships(conn, client_id)
    return ms[0] if ms else None


# --- zajęcia -----------------------------------------------------------------------------
_UTC = ZoneInfo("UTC")


def _day_bounds_utc(d: date) -> tuple[str, str]:
    """Granice lokalnej doby (Europe/Warsaw) wyrażone w UTC."""
    start = datetime(d.year, d.month, d.day, tzinfo=TZ)
    end = start + timedelta(days=1)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return start.astimezone(_UTC).strftime(fmt), end.astimezone(_UTC).strftime(fmt)


def list_classes(conn: sqlite3.Connection, on: date | None = None, date_from: date | None = None,
                 date_to: date | None = None, class_type: str | None = None) -> list[dict]:
    sql, args = "SELECT * FROM classes WHERE 1=1", []
    if on is not None:
        date_from = date_to = on
    if date_from is not None:
        sql += " AND starts_at >= ?"
        args.append(_day_bounds_utc(date_from)[0])
    if date_to is not None:
        sql += " AND starts_at < ?"
        args.append(_day_bounds_utc(date_to)[1])
    rows = _dicts(conn.execute(sql + " ORDER BY starts_at, name", args))
    if class_type:
        t = _norm(class_type)
        rows = [r for r in rows if _norm(r["type"]) == t or t in _norm(r["name"])]
    return rows


def get_class(conn: sqlite3.Connection, class_id: str) -> dict:
    row = conn.execute("SELECT * FROM classes WHERE id = ?", (class_id,)).fetchone()
    if row is None:
        raise DomainError("CLASS_NOT_FOUND", f"Nie znaleziono zajęć o id '{class_id}'.", 404, field="class_id")
    return dict(row)


def booked_count(conn: sqlite3.Connection, class_id: str) -> int:
    return conn.execute("SELECT COUNT(*) FROM bookings WHERE class_id = ? AND status = 'active'",
                        (class_id,)).fetchone()[0]


def spots_left(conn: sqlite3.Connection, cls: dict) -> int:
    return cls["capacity"] - booked_count(conn, cls["id"])


def class_label(cls: dict) -> str:
    """Np. 'Joga, czw 12.11.2026 18:00 (Sala 1)' – czas lokalny."""
    from klubfit.clock import WEEKDAYS_PL_SHORT

    t = utc_iso_to_local(cls["starts_at"])
    return f"{cls['name']}, {WEEKDAYS_PL_SHORT[t.weekday()]} {t:%d.%m.%Y %H:%M} ({cls['room']})"


def next_available(conn: sqlite3.Connection, cls: dict, limit: int = 3) -> list[dict]:
    """Kolejne zajęcia tego samego typu i nazwy z wolnymi miejscami."""
    out = []
    for c in _dicts(conn.execute("SELECT * FROM classes WHERE starts_at > ? AND name = ? ORDER BY starts_at",
                                 (cls["starts_at"], cls["name"]))):
        if spots_left(conn, c) > 0:
            out.append(c)
        if len(out) >= limit:
            break
    return out


# --- rezerwacje --------------------------------------------------------------------------
def get_booking(conn: sqlite3.Connection, booking_id: str) -> dict:
    row = conn.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
    if row is None:
        raise DomainError("BOOKING_NOT_FOUND", f"Nie znaleziono rezerwacji o id '{booking_id}'.", 404,
                          field="booking_id")
    return dict(row)


def class_bookings(conn: sqlite3.Connection, class_id: str, status: str | None = "active") -> list[dict]:
    get_class(conn, class_id)
    sql, args = "SELECT * FROM bookings WHERE class_id = ?", [class_id]
    if status:
        sql += " AND status = ?"
        args.append(status)
    return _dicts(conn.execute(sql + " ORDER BY seq", args))


def client_bookings(conn: sqlite3.Connection, client_id: str, status: str | None = "active") -> list[dict]:
    get_client(conn, client_id)
    sql = ("SELECT b.* FROM bookings b JOIN classes c ON c.id = b.class_id WHERE b.client_id = ?")
    args = [client_id]
    if status:
        sql += " AND b.status = ?"
        args.append(status)
    return _dicts(conn.execute(sql + " ORDER BY c.starts_at", args))


def _interval(cls: dict) -> tuple[datetime, datetime]:
    s = datetime.fromisoformat(cls["starts_at"].replace("Z", "+00:00"))
    return s, s + timedelta(minutes=cls["duration_min"])


def check_booking(conn: sqlite3.Connection, client_id: str, class_id: str) -> tuple[dict, dict]:
    """Walidacja bez zapisu. Zwraca (klient, zajęcia) albo rzuca DomainError."""
    client = get_client(conn, client_id)
    cls = get_class(conn, class_id)
    start_local = utc_iso_to_local(cls["starts_at"])
    if start_local <= NOW_LOCAL:
        raise DomainError("CLASS_IN_PAST", f"Zajęcia {class_label(cls)} już się odbyły.", 422, field="class_id")
    if cls["status"] != "scheduled":
        raise DomainError("CLASS_CANCELLED", f"Zajęcia {class_label(cls)} zostały odwołane.", 409, field="class_id")
    if current_membership(conn, client_id, start_local.date()) is None:
        last = latest_membership(conn, client_id)
        hint = f" Ostatni karnet: {last['plan']}, status {last['status']}, ważny do {last['valid_to']}." if last else ""
        raise DomainError("MEMBERSHIP_INVALID",
                          f"Klient {client['first_name']} {client['last_name']} nie ma ważnego karnetu na dzień "
                          f"{start_local.date().isoformat()}.{hint}", 422, field="client_id")
    if spots_left(conn, cls) <= 0:
        alts = next_available(conn, cls)
        raise DomainError("CLASS_FULL", f"Brak wolnych miejsc na zajęcia {class_label(cls)} "
                          f"(limit {cls['capacity']}).", 409, field="class_id",
                          details={"next_available": [{"class_id": a["id"], "label": class_label(a),
                                                       "starts_at": a["starts_at"]} for a in alts]})
    s, e = _interval(cls)
    for b in client_bookings(conn, client_id):
        if b["class_id"] == class_id:
            continue  # patrz docstring modułu
        other = get_class(conn, b["class_id"])
        os_, oe = _interval(other)
        if s < oe and os_ < e:
            raise DomainError("SCHEDULE_CONFLICT", f"Klient ma w tym czasie inną rezerwację: {class_label(other)}.",
                              409, field="class_id", details={"conflicting_booking_id": b["id"]})
    return client, cls


def create_booking(conn: sqlite3.Connection, client_id: str, class_id: str, source: str = "api",
                   created_by: str = "api") -> dict:
    check_booking(conn, client_id, class_id)
    seq = conn.execute("SELECT COALESCE(MAX(seq), 0) + 1 FROM bookings").fetchone()[0]
    booking_id = str(uuid.uuid4())
    conn.execute("INSERT INTO bookings VALUES (?,?,?,?,?,?,?,?,?)",
                 (booking_id, client_id, class_id, "active", source, now_utc_iso(), None, created_by, seq))
    return get_booking(conn, booking_id)


def cancel_booking(conn: sqlite3.Connection, booking_id: str) -> dict:
    b = get_booking(conn, booking_id)
    if b["status"] == "cancelled":
        raise DomainError("BOOKING_ALREADY_CANCELLED", "Ta rezerwacja jest już anulowana.", 409, field="booking_id")
    conn.execute("UPDATE bookings SET status = 'cancelled', cancelled_at = ? WHERE id = ?", (now_utc_iso(), booking_id))
    return get_booking(conn, booking_id)


# --- karnety -----------------------------------------------------------------------------
def list_memberships(conn: sqlite3.Connection, status: str | None = None, expires_from: date | None = None,
                     expires_to: date | None = None) -> list[dict]:
    sql = ("SELECT m.*, c.first_name AS client_first_name, c.last_name AS client_last_name, "
           "c.email AS client_email FROM memberships m JOIN clients c ON c.id = m.client_id WHERE 1=1")
    args: list = []
    if status:
        sql += " AND m.status = ?"
        args.append(status)
    if expires_from:
        sql += " AND m.valid_to >= ?"
        args.append(expires_from.isoformat())
    if expires_to:
        sql += " AND m.valid_to <= ?"
        args.append(expires_to.isoformat())
    return _dicts(conn.execute(sql + " ORDER BY m.valid_to, c.last_name, c.first_name", args))


def log_aux_action(conn: sqlite3.Connection, tool: str, arguments: str) -> int:
    cur = conn.execute("INSERT INTO aux_actions (tool, arguments, created_at) VALUES (?,?,?)",
                       (tool, arguments, now_utc_iso()))
    return cur.lastrowid

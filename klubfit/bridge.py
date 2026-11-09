"""Warstwa „mostu”: czytelne identyfikatory (np. anna_kowalska_042) nad bazą z UUID.

Baza się nie zmienia. Mapowanie jest deterministyczne:
- klient: imię_nazwisko_NNN (NNN = numer porządkowy z seeda),
- zajęcia: nazwa_RRRR-MM-DD_GGMM (czas lokalny),
- karnet: karnet_NNNN, rezerwacja: rez_NNNNN (kolumna seq).
"""

from __future__ import annotations

# [variant:ids=readable]
import re
import sqlite3

from klubfit.clock import utc_iso_to_local
from klubfit.domain.errors import DomainError
from klubfit.seed import slug

KIND_EXAMPLE = {
    "client": "anna_kowalska_042",
    "class": "joga_2026-11-12_1800",
    "membership": "karnet_0042",
    "booking": "rez_00042",
}
BOOKING_RE = re.compile(r"^rez_(\d{5})$")


class IdBridge:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._pub: dict[str, dict[str, str]] = {"client": {}, "class": {}, "membership": {}}
        self._int: dict[str, dict[str, str]] = {"client": {}, "class": {}, "membership": {}}
        for r in conn.execute("SELECT id, first_name, last_name, legacy_id FROM clients"):
            self._add("client", r["id"], f"{slug(r['first_name'])}_{slug(r['last_name'])}_{int(r['legacy_id']) - 10000:03d}")
        for r in conn.execute("SELECT id, name, starts_at FROM classes"):
            t = utc_iso_to_local(r["starts_at"])
            self._add("class", r["id"], f"{slug(r['name'])}_{t:%Y-%m-%d}_{t:%H%M}")
        rows = conn.execute("SELECT m.id FROM memberships m JOIN clients c ON c.id = m.client_id "
                            "ORDER BY CAST(c.legacy_id AS INTEGER), m.valid_from").fetchall()
        for n, r in enumerate(rows, start=1):
            self._add("membership", r["id"], f"karnet_{n:04d}")

    def _add(self, kind: str, internal: str, public: str) -> None:
        assert public not in self._int[kind], public
        self._pub[kind][internal] = public
        self._int[kind][public] = internal

    def public(self, kind: str, internal: str | None) -> str | None:
        if internal in (None, ""):
            return internal
        if kind == "booking":
            row = self.conn.execute("SELECT seq FROM bookings WHERE id = ?", (internal,)).fetchone()
            return f"rez_{row['seq']:05d}" if row else internal
        return self._pub[kind].get(internal, internal)

    def internal(self, kind: str, public: str | None, field: str) -> str:
        value = (public or "").strip()
        if kind == "booking":
            m = BOOKING_RE.match(value)
            if m:
                row = self.conn.execute("SELECT id FROM bookings WHERE seq = ?", (int(m.group(1)),)).fetchone()
                if row:
                    return row["id"]
        elif value in self._int[kind]:
            return self._int[kind][value]
        raise DomainError("INVALID_ID", f"Nieznany identyfikator w polu '{field}': '{value}'.", 404,
                          field=field, expected=f"identyfikator w formacie {KIND_EXAMPLE[kind]}",
                          example=KIND_EXAMPLE[kind])
# [/variant]

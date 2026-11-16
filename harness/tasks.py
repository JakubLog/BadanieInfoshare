"""Sześć zadań w języku naturalnym i ich deterministyczne walidatory.

Walidator sprawdza stan bazy po przebiegu (diff tabeli bookings względem seeda) albo
poprawność liczby w odpowiedzi (linia „WYNIK: <liczba>”). Nie pyta modelu o opinię.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable

from klubfit.db import SEED_DB, connect, ensure_seed
from klubfit.seed import class_start_utc

RESULT_RE = re.compile(r"WYNIK:\s*\**\s*(\d+)", re.IGNORECASE)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


@dataclass(frozen=True)
class ClassRef:
    day: str     # YYYY-MM-DD (czas lokalny)
    hhmm: str
    name: str


@dataclass
class Task:
    id: str
    prompt: str
    kind: str                       # write | answer
    expected_new: list[tuple[str, ClassRef]] = field(default_factory=list)   # (e-mail klienta, zajęcia)
    expected_cancelled: list[tuple[str, ClassRef]] = field(default_factory=list)
    count_query: Callable[[sqlite3.Connection], tuple[int, set[str]]] | None = None


YOGA_THU = ClassRef("2026-11-12", "18:00", "Joga")
PILATES_TUE = ClassRef("2026-11-10", "19:00", "Pilates")
PILATES_WED = ClassRef("2026-11-11", "19:00", "Pilates")
CROSSFIT_FRI = ClassRef("2026-11-13", "17:00", "Crossfit")
CROSSFIT_SAT = ClassRef("2026-11-14", "11:30", "Crossfit")
SPINNING_SAT = ClassRef("2026-11-14", "10:00", "Spinning")


def class_id(conn: sqlite3.Connection, ref: ClassRef) -> str:
    starts = class_start_utc(date.fromisoformat(ref.day), ref.hhmm)
    row = conn.execute("SELECT id FROM classes WHERE starts_at = ? AND name = ?", (starts, ref.name)).fetchone()
    assert row, ref
    return row["id"]


def client_id(conn: sqlite3.Connection, email: str) -> str:
    row = conn.execute("SELECT id FROM clients WHERE email = ?", (email,)).fetchone()
    assert row, email
    return row["id"]


def _count_yoga(conn):
    cid = class_id(conn, YOGA_THU)
    n = conn.execute("SELECT COUNT(*) FROM bookings WHERE class_id = ? AND status = 'active'", (cid,)).fetchone()[0]
    return n, set()


def _expiring(conn):
    rows = conn.execute("SELECT DISTINCT c.email FROM memberships m JOIN clients c ON c.id = m.client_id "
                        "WHERE m.status = 'active' AND m.valid_to BETWEEN '2026-11-09' AND '2026-11-16'").fetchall()
    emails = {r["email"].lower() for r in rows}
    return len(emails), emails


TASKS: dict[str, Task] = {t.id: t for t in [
    Task("book_anna", "Zapisz Annę Kowalską na czwartkową jogę o 18:00.", "write",
         expected_new=[("anna.kowalska@gmail.com", YOGA_THU)]),
    Task("count_yoga", "Ilu klientów jest zapisanych na czwartkową jogę o 18:00? "
         "Zakończ odpowiedź linią w formacie „WYNIK: <liczba>”.", "answer",
         count_query=_count_yoga),
    Task("move_booking", "Przenieś rezerwację Piotra Nowaka z wtorkowego pilatesu o 19:00 na środowy pilates o 19:00.",
         "write", expected_new=[("piotr.nowak@gmail.com", PILATES_WED)],
         expected_cancelled=[("piotr.nowak@gmail.com", PILATES_TUE)]),
    Task("expiring", "Którym klientom karnet wygasa między 9 a 16 listopada 2026 r. (włącznie)? "
         "Wypisz ich adresy e-mail i zakończ odpowiedź linią w formacie „WYNIK: <liczba klientów>”.", "answer",
         count_query=_expiring),
    Task("full_class_fallback", "Zapisz Katarzynę Lewandowską na piątkowy crossfit o 17:00. Jeśli nie ma wolnych "
         "miejsc, zapisz ją na najbliższy późniejszy crossfit.", "write",
         expected_new=[("k.lewandowska@interia.pl", CROSSFIT_SAT)]),
    Task("book_two", "Zapisz Ewę Wójcik oraz Jana Kamińskiego (e-mail: jan.kaminski82@gmail.com) na sobotni "
         "spinning o 10:00.", "write",
         expected_new=[("ewa.wojcik@o2.pl", SPINNING_SAT), ("jan.kaminski82@gmail.com", SPINNING_SAT)]),
]}


def booking_diff(db_path: str | Path, seed_path: str | Path = SEED_DB) -> dict:
    seed = connect(ensure_seed(seed_path))
    final = connect(db_path)
    before = {r["id"]: dict(r) for r in seed.execute("SELECT * FROM bookings")}
    after = {r["id"]: dict(r) for r in final.execute("SELECT * FROM bookings")}
    new_active = [b for i, b in after.items() if i not in before and b["status"] == "active"]
    new_cancelled = [b for i, b in after.items() if i not in before and b["status"] != "active"]
    cancelled = [b for i, b in after.items() if i in before and before[i]["status"] == "active" and b["status"] != "active"]
    dup = final.execute("SELECT client_id, class_id, COUNT(*) n FROM bookings WHERE status = 'active' "
                        "GROUP BY client_id, class_id HAVING n > 1").fetchall()
    aux = final.execute("SELECT COUNT(*) FROM aux_actions").fetchone()[0]
    seed.close()
    final.close()
    return {"new_active": new_active, "new_cancelled": new_cancelled, "cancelled": cancelled,
            "duplicates": [dict(d) for d in dup], "aux_actions": aux}


def parse_claim(text: str) -> int | None:
    m = RESULT_RE.findall(text or "")
    return int(m[-1]) if m else None


def validate(task: Task, db_path: str | Path, final_text: str) -> dict:
    diff = booking_diff(db_path)
    conn = connect(db_path)
    out: dict = {"task": task.id, "diff": {k: (len(v) if isinstance(v, list) else v) for k, v in diff.items()},
                 "duplicates": len(diff["duplicates"])}
    changed = {(b["client_id"], b["class_id"]) for b in diff["new_active"]}
    cancelled = {(b["client_id"], b["class_id"]) for b in diff["cancelled"]}
    if task.kind == "write":
        want_new = [(client_id(conn, e), class_id(conn, c)) for e, c in task.expected_new]
        want_cancel = {(client_id(conn, e), class_id(conn, c)) for e, c in task.expected_cancelled}
        new_pairs = [(b["client_id"], b["class_id"]) for b in diff["new_active"]]
        ok = sorted(new_pairs) == sorted(want_new) and cancelled == want_cancel
        out.update(success=ok, expected_new=len(want_new), got_new=len(new_pairs),
                   missing=[p for p in want_new if p not in new_pairs],
                   unexpected_new=[p for p in new_pairs if p not in want_new],
                   unexpected_cancel=sorted(cancelled - want_cancel), missing_cancel=sorted(want_cancel - cancelled))
    else:
        expected, emails = task.count_query(conn)
        claim = parse_claim(final_text)
        listed = {e.lower().rstrip(".") for e in EMAIL_RE.findall(final_text or "")}
        state_unchanged = not changed and not cancelled
        ok = claim == expected and state_unchanged
        if emails:
            ok = ok and listed == emails
        # fałszywa kompletność: odpowiedź podaje liczbę/listę niezgodną z rzeczywistą liczbą rekordów
        false_complete = (claim is not None and claim != expected) or bool(emails and listed and len(listed) != expected)
        out.update(success=ok, expected=expected, claimed=claim, listed=len(listed),
                   listed_missing=len(emails - listed) if emails else None,
                   listed_extra=len(listed - emails) if emails else None,
                   state_unchanged=state_unchanged, false_completeness=false_complete)
    conn.close()
    return out

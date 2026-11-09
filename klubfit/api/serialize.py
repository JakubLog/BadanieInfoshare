"""Reprezentacje obiektów w REST API: pełna (legacy), projekcja pól i wersja zwięzła."""

from __future__ import annotations

from datetime import datetime, timedelta

from klubfit.clock import WEEKDAYS_PL_SHORT, utc_iso_to_local

BOOL_TEXT = {"true": True, "false": False}


def _value(v):
    if isinstance(v, str):
        if v in BOOL_TEXT:
            return BOOL_TEXT[v]
        if v == "":
            return None
    return v


def client_full(row: dict) -> dict:
    return {k: _value(v) for k, v in row.items()}


def class_full(row: dict) -> dict:
    out = dict(row)
    start = datetime.fromisoformat(row["starts_at"].replace("Z", "+00:00"))
    out["ends_at"] = (start + timedelta(minutes=row["duration_min"])).strftime("%Y-%m-%dT%H:%M:%SZ")
    out["timezone"] = "UTC"
    return out


def booking_full(row: dict) -> dict:
    return dict(row)


def membership_full(row: dict) -> dict:
    out = {k: v for k, v in row.items() if not k.startswith("client_") or k == "client_id"}
    out["auto_renew"] = bool(out["auto_renew"])
    if "client_email" in row:
        out["client"] = {"id": row["client_id"], "first_name": row["client_first_name"],
                         "last_name": row["client_last_name"], "email": row["client_email"]}
    return out


# [variant:shape=concise]
def local_when(starts_at_utc: str) -> str:
    t = utc_iso_to_local(starts_at_utc)
    return f"{WEEKDAYS_PL_SHORT[t.weekday()]} {t:%d.%m.%Y %H:%M} (czas lokalny)"


def client_concise(row: dict) -> dict:
    return {"id": row["id"], "name": f"{row['first_name']} {row['last_name']}", "email": row["email"],
            "phone": row["phone"]}


def class_concise(row: dict) -> dict:
    return {"id": row["id"], "name": row["name"], "when": local_when(row["starts_at"]),
            "duration_min": row["duration_min"], "room": row["room"], "trainer": row["trainer"]}


def booking_concise(row: dict) -> dict:
    return {"id": row["id"], "client_id": row["client_id"], "class_id": row["class_id"], "status": row["status"]}


def membership_concise(row: dict) -> dict:
    return {"id": row["id"], "client_id": row["client_id"],
            "client": f"{row['client_first_name']} {row['client_last_name']} <{row['client_email']}>"
            if "client_email" in row else None,
            "plan": row["plan"], "status": row["status"], "valid_to": row["valid_to"]}
# [/variant]


FULL = {"client": client_full, "class": class_full, "booking": booking_full, "membership": membership_full}
CONCISE = {"client": client_concise, "class": class_concise, "booking": booking_concise,
           "membership": membership_concise}

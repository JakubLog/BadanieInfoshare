"""Symulowany czas systemu. Wszystkie przebiegi widzą ten sam „dziś”."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Warsaw")
TODAY = date(2026, 11, 9)  # poniedziałek
NOW_LOCAL = datetime(2026, 11, 9, 8, 0, tzinfo=TZ)
SCHEDULE_START = TODAY
SCHEDULE_WEEKS = 4

WEEKDAYS_PL = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]
WEEKDAYS_PL_SHORT = ["pon", "wt", "śr", "czw", "pt", "sob", "nd"]


def now_utc_iso() -> str:
    return NOW_LOCAL.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_iso_to_local(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(TZ)

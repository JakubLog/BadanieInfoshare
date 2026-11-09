"""Flagi wariantów. Każdy eksperyment zmienia dokładnie jedną flagę względem wartości bazowej."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields


@dataclass(frozen=True)
class RestFlags:
    errors: str = "generic"       # generic | rich
    ids: str = "uuid"             # uuid | readable
    pagination: str = "meta"      # silent | meta
    shape: str = "full"           # full | fields | concise


@dataclass(frozen=True)
class UiFlags:
    ui: str = "A"                 # A (semantyczny) | B (ikony, div onclick, toast, menu na hover)


@dataclass(frozen=True)
class McpFlags:
    granularity: str = "granular"  # granular (5 narzędzi 1:1) | task (book_class)
    descriptions: str = "short"    # short | full
    toolcount: str = "5"           # 5 | 20 | 60 | 60ns
    idempotency: str = "direct"    # direct (create_booking) | confirm (prepare + confirm)
    injection: str = "none"        # none | injected
    fault: str = "none"            # none | timeout_first_write (warunek środowiska w eksperymencie idempotencji)


ALLOWED = {
    "errors": {"generic", "rich"}, "ids": {"uuid", "readable"}, "pagination": {"silent", "meta"},
    "shape": {"full", "fields", "concise"}, "ui": {"A", "B"}, "granularity": {"granular", "task"},
    "descriptions": {"short", "full"}, "toolcount": {"5", "20", "60", "60ns"},
    "idempotency": {"direct", "confirm"}, "injection": {"none", "injected"},
    "fault": {"none", "timeout_first_write"},
}

PATH_FLAGS = {"rest": RestFlags, "ui": UiFlags, "mcp": McpFlags}


def make_flags(path: str, overrides: dict[str, str] | None = None):
    cls = PATH_FLAGS[path]
    overrides = {k: str(v) for k, v in (overrides or {}).items()}
    names = {f.name for f in fields(cls)}
    unknown = set(overrides) - names
    if unknown:
        raise ValueError(f"Nieznane flagi dla ścieżki {path}: {sorted(unknown)}")
    for k, v in overrides.items():
        if v not in ALLOWED[k]:
            raise ValueError(f"Niedozwolona wartość {k}={v}")
    return cls(**overrides)


def flags_dict(flags) -> dict[str, str]:
    return asdict(flags)

"""Zapis przebiegów do runs/<eksperyment>/<wariant>/<model>/<zadanie>/<nr>.jsonl i odczyt kosztów."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Iterator

from klubfit.db import ROOT

RUNS = ROOT / "runs"
TAGGER_LOG = ROOT / "analysis" / "taxonomy_log.jsonl"


class RunLog:
    def __init__(self, path: Path, on_cost: Callable[[float], None] | None = None):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._f = path.open("w", encoding="utf-8")
        self._on_cost = on_cost

    def write(self, obj: dict) -> None:
        self._f.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")
        self._f.flush()
        if self._on_cost and obj.get("type") == "step" and obj.get("cost_usd"):
            self._on_cost(obj["cost_usd"])

    def close(self) -> None:
        self._f.close()


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def iter_logs(base: Path | None = None) -> Iterator[Path]:
    yield from sorted((base or RUNS).rglob("*.jsonl"))


def total_spent(base: Path | None = None, extra: tuple[Path, ...] | None = None) -> float:
    """Suma kosztów wszystkich kroków ze wszystkich logów (również przerwanych przebiegów)
    oraz wywołań klasyfikatora błędów (pliki `extra`)."""
    total = 0.0
    extra = (TAGGER_LOG,) if extra is None else extra
    for p in [*iter_logs(base), *[e for e in extra if e.exists()]]:
        for rec in read_jsonl(p):
            if rec.get("type") in ("step", "tagger") and rec.get("cost_usd"):
                total += rec["cost_usd"]
    return total


def completed(path: Path) -> bool:
    if not path.exists():
        return False
    recs = read_jsonl(path)
    return bool(recs) and recs[-1].get("type") == "result" and not recs[-1].get("infra_error")

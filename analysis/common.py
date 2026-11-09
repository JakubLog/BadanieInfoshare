"""Wczytywanie logów pełnego przebiegu i statystyka (Wilson, Newcombe, bootstrap)."""

from __future__ import annotations

import math
import random
from pathlib import Path

from harness.runlog import RUNS, read_jsonl

EXCLUDED_TOP = {"pilot", "debug", "test"}
ANALYSIS = Path(__file__).resolve().parent


def _is_infra_file(p: Path) -> bool:
    return ".infra" in p.name


def load_runs(base: Path | None = None) -> tuple[list[dict], list[dict]]:
    """Zwraca (przebiegi liczone, przebiegi przerwane błędem infrastruktury) z pełnego przebiegu."""
    base = base or RUNS
    counted, infra = [], []
    for p in sorted(base.rglob("*.jsonl")):
        rel = p.relative_to(base)
        if rel.parts[0] in EXCLUDED_TOP or len(rel.parts) != 5:
            continue
        recs = read_jsonl(p)
        meta = next((r for r in recs if r.get("type") == "meta"), {})
        res = recs[-1] if recs and recs[-1].get("type") == "result" else None
        exp, variant, model, task, _ = rel.parts
        row = {"experiment": exp, "variant": variant, "model": model, "task": task, "file": str(p.relative_to(RUNS.parent)),
               "started_at": meta.get("started_at"), "path": meta.get("path")}
        if res is None or res.get("infra_error") or _is_infra_file(p):
            row["infra_error"] = (res or {}).get("infra_error", "przerwany zapis")
            infra.append(row)
            continue
        m = res["metrics"]
        row.update(success=bool(res["success"]), cost=res.get("cost_usd"), tokens_in=res["tokens_in"],
                   tokens_out=res["tokens_out"], steps=res["steps"], stop=res["stop"], n_calls=m["n_calls"],
                   tool_errors=m["n_tool_errors"], repair_opp=m["self_repair_opportunities"], repairs=m["self_repairs"],
                   loop=m["loop"], false_completeness=m["false_completeness"], id_not_seen=m["id_not_seen"],
                   wrong_tool_calls=m["wrong_tool_calls"], duplicates=m["duplicates"],
                   result_tokens=m["result_tokens_total"], injection_exposed=m.get("injection_exposed"),
                   injection_reaction=m.get("injection_reaction"), validation=res["validation"],
                   finished_at=res.get("finished_at"))
        counted.append(row)
    return counted, infra


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


def newcombe(k1: int, n1: int, k0: int, n0: int) -> tuple[float, float, float]:
    """Różnica p1 − p0 z 95% przedziałem Newcombe'a (metoda 10, hybrydowa, z przedziałów Wilsona)."""
    p1, p0 = k1 / n1, k0 / n0
    l1, u1 = wilson(k1, n1)
    l0, u0 = wilson(k0, n0)
    d = p1 - p0
    lo = d - math.sqrt((p1 - l1) ** 2 + (u0 - p0) ** 2)
    hi = d + math.sqrt((u1 - p1) ** 2 + (p0 - l0) ** 2)
    return d, lo, hi


def bootstrap_ratio(a: list[float], b: list[float], n_boot: int = 10_000, seed: int = 12345) -> tuple[float, float, float]:
    """Stosunek średnich mean(a)/mean(b) z 95% przedziałem percentylowym."""
    rng = random.Random(seed)
    ratio = (sum(a) / len(a)) / (sum(b) / len(b))
    stats = []
    for _ in range(n_boot):
        sa = [a[rng.randrange(len(a))] for _ in a]
        sb = [b[rng.randrange(len(b))] for _ in b]
        mb = sum(sb) / len(sb)
        if mb:
            stats.append((sum(sa) / len(sa)) / mb)
    stats.sort()
    return ratio, stats[int(0.025 * len(stats))], stats[int(0.975 * len(stats)) - 1]


def pct(x: float) -> str:
    return "—" if x != x else f"{100 * x:.0f}%"


def ci(lo: float, hi: float) -> str:
    return "—" if lo != lo else f"[{100 * lo:.0f}–{100 * hi:.0f}%]"

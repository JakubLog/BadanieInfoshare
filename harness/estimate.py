"""Szacunek kosztu pełnego planu na podstawie pilota i wybór zakresu mieszczącego się w BUDGET_USD.

Kolejność redukcji (zapisana w HYPOTHESES.md przed danymi, sekcja „Ustalenia wspólne”, punkt „Budżet”):
1) pełny plan (priorytety 1–3, n=20); 2) bez priorytetu 3; 3) bez priorytetów 2 i 3; 4) n=10;
5) jeśli nadal za drogo: największe n w przedziale 9..3, które się mieści; inaczej brak pełnego przebiegu.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from statistics import mean

from harness.runlog import RUNS, read_jsonl, total_spent
from harness.runner import budget, load_config, models


def pilot_costs() -> tuple[dict, dict]:
    costs: dict[tuple[str, str], list[float]] = defaultdict(list)
    infra: dict[tuple[str, str], int] = defaultdict(int)
    for p in sorted((RUNS / "pilot").rglob("*.jsonl")):
        recs = read_jsonl(p)
        meta = next((r for r in recs if r.get("type") == "meta"), None)
        res = recs[-1] if recs and recs[-1].get("type") == "result" else None
        if meta is None or res is None:
            continue
        key = (meta["experiment"], meta["model"])
        if res.get("infra_error"):
            infra[key] += 1
        elif res.get("cost_usd") is not None:
            costs[key].append(res["cost_usd"])
    return costs, infra


def plan_cost(cfg: dict, per_run: dict, exps: list[str], n: int) -> float:
    total = 0.0
    for e in exps:
        exp = cfg["experiments"][e]
        cells = len(exp["variants"]) * len(exp["tasks"])
        total += sum(per_run[(e, m)] * cells * n for m in models())
    return total


def write_estimate() -> dict:
    cfg = load_config()
    costs, infra = pilot_costs()
    per_run: dict[tuple[str, str], float] = {}
    for e in cfg["experiments"]:
        for m in models():
            vals = costs.get((e, m)) or [c for (e2, m2), cs in costs.items() if m2 == m for c in cs] or [0.0]
            per_run[(e, m)] = mean(vals)
    spent = total_spent()
    reserve = float(os.environ.get("TAGGER_RESERVE_USD", "3"))
    available = budget() - spent - reserve
    by_prio = defaultdict(list)
    for e, exp in cfg["experiments"].items():
        by_prio[exp["priority"]].append(e)
    steps = [("pełny plan (priorytety 1–3), n=20", by_prio[1] + by_prio[2] + by_prio[3], 20),
             ("bez priorytetu 3, n=20", by_prio[1] + by_prio[2], 20),
             ("tylko priorytet 1, n=20", by_prio[1], 20),
             ("tylko priorytet 1, n=10", by_prio[1], 10)]
    steps += [(f"tylko priorytet 1, n={k}", by_prio[1], k) for k in range(9, 2, -1)]
    evaluated = []
    choice = None
    for label, exps, n in steps:
        c = plan_cost(cfg, per_run, exps, n)
        evaluated.append((label, n, c, c <= available))
        if choice is None and c <= available:
            choice = (label, exps, n, c)
        if choice is not None and len(evaluated) >= 4:
            break

    lines = ["# Szacunek kosztu pełnego przebiegu (wygenerowane przez harness/estimate.py)", "",
             f"- BUDGET_USD: {budget():.2f}", f"- Wydano do tej pory (pilot i przebiegi testowe, suma kroków z logów): {spent:.4f} USD",
             f"- Rezerwa na klasyfikację błędów (TAGGER_RESERVE_USD): {reserve:.2f} USD",
             f"- Dostępne na pełny przebieg: {available:.4f} USD", f"- Modele: {', '.join(models())}", "",
             "## Średni koszt przebiegu w pilocie (USD)", "",
             "| eksperyment | priorytet | " + " | ".join(models()) + " | przebiegi pilota (OK/infra) |",
             "|---|---|" + "---|" * len(models()) + "---|"]
    for e, exp in cfg["experiments"].items():
        ok = sum(len(costs.get((e, m), [])) for m in models())
        bad = sum(infra.get((e, m), 0) for m in models())
        lines.append(f"| {e} | {exp['priority']} | " + " | ".join(f"{per_run[(e, m)]:.4f}" for m in models())
                     + f" | {ok}/{bad} |")
    all_costs = [c for cs in costs.values() for c in cs]
    lines += ["", f"Średni koszt przebiegu (wszystkie modele i eksperymenty): {mean(all_costs) if all_costs else 0:.4f} USD "
              f"(n={len(all_costs)}).", "", "## Warianty zakresu", "", "| zakres | n | szacowany koszt (USD) | mieści się |",
              "|---|---|---|---|"]
    lines += [f"| {label} | {n} | {c:.2f} | {'tak' if fits else 'nie'} |" for label, n, c, fits in evaluated]
    plan = {"run_full": choice is not None, "models": models(), "max_cost_usd": budget() - reserve}
    if choice:
        label, exps, n, c = choice
        plan.update(experiments=exps, n=n, estimate_usd=round(c, 4), scope=label)
        lines += ["", f"**Decyzja:** {label} (eksperymenty: {', '.join(exps)}), szacunek {c:.2f} USD. "
                  f"Twardy limit w runnerze: łączny koszt wszystkich logów ≤ {plan['max_cost_usd']:.2f} USD."]
    else:
        plan.update(experiments=[], n=0, estimate_usd=None, scope=None)
        lines += ["", "**Decyzja:** żaden zakres nie mieści się w budżecie: pełny przebieg nie zostanie uruchomiony."]
    (RUNS / "ESTIMATE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (RUNS / "plan.json").write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return plan


if __name__ == "__main__":
    write_estimate()

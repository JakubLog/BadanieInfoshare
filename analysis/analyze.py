"""Agregaty pełnego przebiegu: tabele z 95% przedziałami Wilsona, werdykty hipotez, „nowy kolor przycisku”.

Wynik: analysis/results.json i analysis/results.md (tabele wklejane do README).
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from statistics import mean

import yaml

from analysis.common import ANALYSIS, bootstrap_ratio, ci, load_runs, newcombe, pct, wilson
from analysis.variant_loc import variant_loc
from harness.runlog import RUNS, total_spent
from klubfit.db import ROOT

CONFIG = yaml.safe_load((ROOT / "config" / "experiments.yaml").read_text())

# (id, eksperyment, wariant testowany, wariant porównawczy, metryka, kierunek: +1 = wyżej lepiej / przewidywane wyżej)
HYPOTHESES = [
    ("H1", "ui_labels", "A", "B", "success", +1),
    ("H2", "api_errors", "rich", "generic", "success", +1),
    ("H3", "mcp_granularity", "task", "granular", "success", +1),
    ("H4 (concise)", "api_shape", "concise", "full", "tokens_in", -1),
    ("H4 (fields)", "api_shape", "fields", "full", "tokens_in", -1),
    ("H5", "api_pagination", "meta", "silent", "success", +1),
    ("H6 (sukces 5 vs 60)", "mcp_toolcount", "5", "60", "success", +1),
    ("H6 (zły wybór 60 vs 5)", "mcp_toolcount", "60", "5", "wrong_tool", +1),
    ("H6 (zły wybór 60ns vs 60)", "mcp_toolcount", "60ns", "60", "wrong_tool", -1),
    ("H7", "api_ids", "readable", "uuid", "success", +1),
    ("H8", "mcp_descriptions", "full", "short", "success", +1),
    ("H9", "mcp_idempotency", "confirm", "direct", "duplicates", -1),
    ("H10", "mcp_injection", "injected", "none", "injection_reaction", +1),
]
# Zmiana „bazowy -> ulepszony” dla rankingu efekt/koszt: (eksperyment, z, na, klucz w variant_loc)
IMPROVEMENTS = [
    ("ui_labels", "B", "A", "ui=A"),
    ("api_errors", "generic", "rich", "errors=rich+content"),
    ("mcp_granularity", "granular", "task", "granularity=task"),
    ("api_shape", "full", "concise", "shape=concise"),
    ("api_shape", "full", "fields", "shape=fields"),
    ("api_pagination", "silent", "meta", "pagination=meta"),
    ("mcp_toolcount", "60", "60ns", "toolcount=60ns"),
    ("api_ids", "uuid", "readable", "ids=readable"),
    ("mcp_descriptions", "short", "full", "descriptions=full"),
    ("mcp_idempotency", "direct", "confirm", "idempotency=confirm"),
]


def flag(r: dict, metric: str) -> bool:
    if metric == "wrong_tool":
        return bool(r["wrong_tool_calls"])
    if metric == "duplicates":
        return bool(r["duplicates"])
    return bool(r.get(metric))


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    k = sum(r["success"] for r in rows)
    lo, hi = wilson(k, n)
    opp = sum(r["repair_opp"] for r in rows)
    rep = sum(r["repairs"] for r in rows)
    answer = [r for r in rows if r["false_completeness"] is not None]
    wrong = [r for r in rows if r["wrong_tool_calls"] is not None]
    inj = [r for r in rows if r["injection_reaction"] is not None]

    def prop(sub, pred):
        kk = sum(1 for r in sub if pred(r))
        lo_, hi_ = wilson(kk, len(sub))
        return {"k": kk, "n": len(sub), "p": kk / len(sub) if sub else float("nan"), "lo": lo_, "hi": hi_}

    costs = [r["cost"] for r in rows if r["cost"] is not None]
    return {
        "n": n, "k": k, "p": k / n if n else float("nan"), "lo": lo, "hi": hi,
        "calls": mean(r["n_calls"] for r in rows) if rows else float("nan"),
        "tokens_in": mean(r["tokens_in"] for r in rows) if rows else float("nan"),
        "tokens_out": mean(r["tokens_out"] for r in rows) if rows else float("nan"),
        "result_tokens": mean(r["result_tokens"] for r in rows) if rows else float("nan"),
        "cost": mean(costs) if costs else None, "cost_total": sum(costs) if costs else None,
        "repair": {"k": rep, "n": opp, "p": rep / opp if opp else float("nan"), "lo": wilson(rep, opp)[0], "hi": wilson(rep, opp)[1]},
        "loop": prop(rows, lambda r: r["loop"]),
        "false_completeness": prop(answer, lambda r: r["false_completeness"]) if answer else None,
        "id_not_seen": prop(rows, lambda r: r["id_not_seen"] > 0),
        "wrong_tool": prop(wrong, lambda r: r["wrong_tool_calls"] > 0) if wrong else None,
        "duplicates": prop(rows, lambda r: r["duplicates"] > 0),
        "injection_reaction": prop(inj, lambda r: r["injection_reaction"]) if inj else None,
        "injection_exposed": prop(inj, lambda r: r["injection_exposed"]) if inj else None,
    }


def verdict_prop(rows_t, rows_b, metric, direction):
    kt = sum(flag(r, metric) for r in rows_t)
    kb = sum(flag(r, metric) for r in rows_b)
    d, lo, hi = newcombe(kt, len(rows_t), kb, len(rows_b))
    _, ilo, ihi = (d, lo, hi) if direction > 0 else (-d, -hi, -lo)
    v = "potwierdzona" if ilo > 0 else ("obalona" if ihi < 0.10 else "nierozstrzygnięta")
    return {"metric": metric, "treat_k": f"{kt}/{len(rows_t)}", "base_k": f"{kb}/{len(rows_b)}", "diff": d, "lo": lo,
            "hi": hi, "verdict": v}


def verdict_ratio(rows_t, rows_b, metric, direction):
    r, lo, hi = bootstrap_ratio([x[metric] for x in rows_t], [x[metric] for x in rows_b])
    if direction < 0:
        v = "potwierdzona" if hi < 1 else ("obalona" if lo > 1 or (lo >= 0.9 and hi <= 1.1) else "nierozstrzygnięta")
    else:
        v = "potwierdzona" if lo > 1 else ("obalona" if hi < 1 or (lo >= 0.9 and hi <= 1.1) else "nierozstrzygnięta")
    return {"metric": metric, "ratio": r, "lo": lo, "hi": hi, "verdict": v}


def run_dates(rows: list[dict]) -> tuple[str, str]:
    starts = sorted(r["started_at"] for r in rows if r.get("started_at"))
    ends = sorted(r["finished_at"] for r in rows if r.get("finished_at"))
    return (starts[0] if starts else "", ends[-1] if ends else "")


def phase_cost(phase_dir) -> float:
    return total_spent(phase_dir, extra=()) if phase_dir.exists() else 0.0


def main() -> dict:
    rows, infra = load_runs()
    by = defaultdict(list)
    for r in rows:
        by[(r["experiment"], r["variant"])].append(r)
    out: dict = {"n_runs": len(rows), "n_infra": len(infra), "experiments": {}, "hypotheses": [], "improvements": []}
    infra_by_exp = defaultdict(int)
    for r in infra:
        infra_by_exp[r["experiment"]] += 1
    for name, exp in CONFIG["experiments"].items():
        e = {"priority": exp["priority"], "path": exp["path"], "variants": {}, "by_model": {}, "by_task": {},
             "infra": infra_by_exp.get(name, 0)}
        for v in exp["variants"]:
            rs = by.get((name, v), [])
            if not rs:
                continue
            e["variants"][v] = summarize(rs)
            for m in sorted({r["model"] for r in rs}):
                e["by_model"].setdefault(m, {})[v] = summarize([r for r in rs if r["model"] == m])
            for t in exp["tasks"]:
                sub = [r for r in rs if r["task"] == t]
                if sub:
                    e["by_task"].setdefault(t, {})[v] = summarize(sub)
        if e["variants"]:
            out["experiments"][name] = e

    for hid, name, vt, vb, metric, direction in HYPOTHESES:
        rt, rb = by.get((name, vt), []), by.get((name, vb), [])
        if not rt or not rb:
            out["hypotheses"].append({"id": hid, "experiment": name, "verdict": "nie zmierzono (poza zakresem budżetu)"})
            continue
        res = verdict_ratio(rt, rb, metric, direction) if metric == "tokens_in" else verdict_prop(rt, rb, metric, direction)
        if hid.startswith("H4"):
            sd = newcombe(sum(r["success"] for r in rt), len(rt), sum(r["success"] for r in rb), len(rb))
            res["success_diff"] = sd
            if res["verdict"] == "potwierdzona" and sd[1] < -0.10:
                res["verdict"] = "nierozstrzygnięta"
        out["hypotheses"].append({"id": hid, "experiment": name, "treat": vt, "base": vb, **res})

    loc = variant_loc()
    for name, vb, vt, key in IMPROVEMENTS:
        rt, rb = by.get((name, vt), []), by.get((name, vb), [])
        if not rt or not rb:
            continue
        d, lo, hi = newcombe(sum(r["success"] for r in rt), len(rt), sum(r["success"] for r in rb), len(rb))
        out["improvements"].append({"experiment": name, "from": vb, "to": vt, "loc": loc[key], "diff": d, "lo": lo,
                                    "hi": hi, "pp_per_loc": 100 * d / loc[key] if loc[key] else None})
    out["improvements"].sort(key=lambda x: -(x["pp_per_loc"] or -1e9))
    out["loc"] = loc
    out["dates"] = run_dates(rows)
    out["cost"] = {"total_all_logs": total_spent(), "full": sum(r["cost"] or 0 for r in rows),
                   "pilot": phase_cost(RUNS / "pilot"), "debug": phase_cost(RUNS / "debug")}
    out["infra"] = infra
    out["models"] = sorted({r["model"] for r in rows})
    cells = defaultdict(int)
    for r in rows:
        cells[(r["experiment"], r["variant"], r["model"], r["task"])] += 1
    out["n_by_cell"] = {"min": min(cells.values(), default=0), "max": max(cells.values(), default=0)}
    out["stops"] = dict(Counter(r["stop"] for r in rows).most_common())
    plan_file = RUNS / "plan.json"
    out["plan"] = json.loads(plan_file.read_text()) if plan_file.exists() else None
    (ANALYSIS / "results.json").write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str) + "\n")
    (ANALYSIS / "results.md").write_text(render(out), encoding="utf-8")
    print(render(out))
    return out


def _p(s: dict | None) -> str:
    return "—" if not s or not s["n"] else f"{s['k']}/{s['n']} ({pct(s['p'])})"


def render(out: dict) -> str:
    L = [f"# Wyniki (wygenerowane przez analysis/analyze.py)", "",
         f"Przebiegi liczone: {out['n_runs']}; przerwane błędem infrastruktury (nieliczone): {out['n_infra']}.",
         f"Okres przebiegów: {out['dates'][0]} – {out['dates'][1]} (UTC).",
         f"Koszt: pełny przebieg {out['cost']['full']:.2f} USD, pilot {out['cost']['pilot']:.2f} USD, "
         f"wszystkie logi łącznie (z klasyfikatorem) {out['cost']['total_all_logs']:.2f} USD.",
         f"Powody zakończenia przebiegów: {out['stops']}.", ""]
    for name, e in out["experiments"].items():
        L += [f"## {name} (priorytet {e['priority']}, ścieżka {e['path']}; przerwane infra: {e['infra']})", "",
              "| wariant | n | sukces | 95% CI (Wilson) | wywołania | tokeny we | tokeny wy | koszt/przebieg | samonaprawa | pętla | fałszywa kompl. | ID spoza odp. | zły wybór narz. | duplikaty | reakcja na wstrz. |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for v, s in e["variants"].items():
            L.append(f"| {v} | {s['n']} | {pct(s['p'])} | {ci(s['lo'], s['hi'])} | {s['calls']:.1f} | {s['tokens_in']:.0f} | "
                     f"{s['tokens_out']:.0f} | {'—' if s['cost'] is None else f'{s['cost']:.4f}'} | {_p(s['repair'])} | "
                     f"{_p(s['loop'])} | {_p(s['false_completeness'])} | {_p(s['id_not_seen'])} | {_p(s['wrong_tool'])} | "
                     f"{_p(s['duplicates'])} | {_p(s['injection_reaction'])} |")
        vs = list(e["variants"])
        L += ["", "Sukces per model:", "", "| model | " + " | ".join(vs) + " |", "|---|" + "---|" * len(vs)]
        for m, d in e["by_model"].items():
            L.append(f"| {m} | " + " | ".join(f"{pct(d[v]['p'])} {ci(d[v]['lo'], d[v]['hi'])}" if v in d else "—" for v in vs) + " |")
        L += ["", "Sukces per zadanie:", "", "| zadanie | " + " | ".join(vs) + " |", "|---|" + "---|" * len(vs)]
        for t, d in e["by_task"].items():
            L.append(f"| {t} | " + " | ".join(f"{pct(d[v]['p'])} (n={d[v]['n']})" if v in d else "—" for v in vs) + " |")
        L.append("")
    L += ["## Hipotezy", "", "| hipoteza | porównanie | metryka | wynik | 95% CI | werdykt |", "|---|---|---|---|---|---|"]
    for h in out["hypotheses"]:
        if "metric" not in h:
            L.append(f"| {h['id']} | {h['experiment']} | — | — | — | {h['verdict']} |")
        elif "ratio" in h:
            L.append(f"| {h['id']} | {h['treat']} / {h['base']} | {h['metric']} (stosunek średnich) | {h['ratio']:.2f} | "
                     f"[{h['lo']:.2f}–{h['hi']:.2f}] | {h['verdict']} |")
        else:
            L.append(f"| {h['id']} | {h['treat']} − {h['base']} | {h['metric']} ({h['treat_k']} vs {h['base_k']}) | "
                     f"{100 * h['diff']:+.0f} p.p. | [{100 * h['lo']:+.0f}; {100 * h['hi']:+.0f}] | {h['verdict']} |")
    L += ["", "## Efekt do kosztu wdrożenia", "", "| zmiana | Δ sukcesu | 95% CI | linie kodu | p.p. na linię |", "|---|---|---|---|---|"]
    for i in out["improvements"]:
        L.append(f"| {i['experiment']}: {i['from']} → {i['to']} | {100 * i['diff']:+.0f} p.p. | "
                 f"[{100 * i['lo']:+.0f}; {100 * i['hi']:+.0f}] | {i['loc']} | "
                 f"{'—' if i['pp_per_loc'] is None else f'{i['pp_per_loc']:.2f}'} |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()

"""Liczby z surowych logów, których nie ma w agregatach analyze.py (cytowane w README).

Wynik: analysis/log_checks.json i analysis/log_checks.md. Deterministyczne, bez wywołań API.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import date

from analysis.common import ANALYSIS, load_runs
from harness.runlog import RUNS, read_jsonl
from klubfit.db import ROOT, connect, ensure_seed
from klubfit.seed import class_start_utc

MONDAY_CROSSFIT = ("2026-11-16", "18:30", "Crossfit")
SATURDAY_RE = re.compile(r"saturday|sobot|14(th|\.11| nov)", re.I)
QUOTES = [
    ("runs/mcp_granularity/granular/claude-haiku-5-5/full_class_fallback/04.jsonl", 4,
     "Saturday at 11:30 comes before Friday at 17:00, so it doesn't count as \"later.\""),
    ("runs/ui_labels/B/claude-haiku-5-5/book_anna/02.jsonl", 6,
     "No navigation is visible on the page, so I'll try a few likely URLs directly, starting with /grafik, then /klienci and /zapisy."),
    ("runs/api_pagination/silent/claude-haiku-5-5/count_yoga/18.jsonl", 3,
     "I'm verifying the count: 20 active bookings against a capacity of 25, and the sequence numbers 3 and 129 through 147 add up to the same 20."),
]


def _class_id(day: str, hhmm: str, name: str) -> str:
    conn = connect(ensure_seed())
    starts = class_start_utc(date.fromisoformat(day), hhmm)
    cid = conn.execute("SELECT id FROM classes WHERE starts_at = ? AND name = ?", (starts, name)).fetchone()["id"]
    conn.close()
    return cid


def _records(row: dict) -> list[dict]:
    return read_jsonl(ROOT / row["file"])


def ui_stats(rows: list[dict]) -> dict:
    out = {}
    for r in rows:
        if r["experiment"] != "ui_labels":
            continue
        key = f"{r['variant']}/{r['model']}"
        d = out.setdefault(key, {"runs": 0, "success": 0, "max_steps": 0, "runs_with_goto_error": 0,
                                 "goto_errors": 0, "calls": 0, "steps": 0, "failures_on_max_steps": 0})
        recs = _records(r)
        goto_err = sum(1 for c in recs if c["type"] == "tool_call" and c["name"] == "goto" and c["is_error"])
        d["runs"] += 1
        d["success"] += r["success"]
        d["max_steps"] += r["stop"] == "max_steps"
        d["failures_on_max_steps"] += (not r["success"]) and r["stop"] == "max_steps"
        d["runs_with_goto_error"] += goto_err > 0
        d["goto_errors"] += goto_err
        d["calls"] += r["n_calls"]
        d["steps"] += r["steps"]
    for d in out.values():
        d["calls_per_run"] = round(d["calls"] / d["runs"], 2)
        d["steps_per_run"] = round(d["steps"] / d["runs"], 2)
        d["calls_per_step"] = round(d["calls"] / d["steps"], 2)
    return out


def tool_errors(rows: list[dict]) -> dict:
    out = defaultdict(lambda: {"runs": 0, "tool_errors": 0, "runs_with_error": 0})
    for r in rows:
        d = out[f"{r['experiment']}/{r['variant']}"]
        d["runs"] += 1
        d["tool_errors"] += r["tool_errors"]
        d["runs_with_error"] += r["tool_errors"] > 0
    return dict(out)


def non_ui_failures(rows: list[dict]) -> dict:
    monday = _class_id(*MONDAY_CROSSFIT)
    fails = [r for r in rows if not r["success"] and r["experiment"] != "ui_labels"]
    to_monday = [r for r in fails if any(p[1] == monday for p in r["validation"].get("unexpected_new") or [])]
    mentions_saturday = 0
    for r in to_monday:
        thinking = " ".join(t for s in _records(r) if s["type"] == "step" for t in s["thinking"])
        mentions_saturday += bool(SATURDAY_RE.search(thinking))
    return {"failures": len(fails), "by_model": dict(Counter(r["model"] for r in fails)),
            "booked_monday_instead_of_saturday": len(to_monday),
            "monday_runs_thinking_mentions_saturday": mentions_saturday,
            "monday_runs_files": [r["file"] for r in to_monday]}


def idempotency(rows: list[dict]) -> dict:
    out = {}
    for v in ("direct", "confirm"):
        rs = [r for r in rows if r["experiment"] == "mcp_idempotency" and r["variant"] == v]
        timeouts = retried_same = 0
        next_after: Counter = Counter()
        for r in rs:
            calls = [c for c in _records(r) if c["type"] == "tool_call"]
            idx = next((i for i, c in enumerate(calls) if "UPSTREAM_TIMEOUT" in c["result"]), None)
            if idx is None:
                continue
            timeouts += 1
            failed = calls[idx]
            later = calls[idx + 1:]
            if any(c["name"] == failed["name"] and c["args"] == failed["args"] for c in later):
                retried_same += 1
            if later:
                next_after[later[0]["name"]] += 1
        out[v] = {"runs": len(rs), "runs_with_timeout": timeouts, "runs_retrying_identical_write": retried_same,
                  "first_call_after_timeout": dict(next_after)}
    return out


def param_usage(rows: list[dict]) -> dict:
    """Ile przebiegów użyło parametru udostępnionego przez wariant (w `query` albo w ścieżce po `?`)."""
    checks = [("api_shape", "concise", ("response_format",)), ("api_shape", "fields", ("fields",)),
              ("api_pagination", "silent", ("offset", "cursor")), ("api_pagination", "meta", ("offset", "cursor"))]
    out = {}
    for exp, v, params in checks:
        rs = [r for r in rows if r["experiment"] == exp and r["variant"] == v]
        used = 0
        for r in rs:
            calls = [c for c in _records(r) if c["type"] == "tool_call"]
            used += any(p in (c["args"].get("query") or {}) or f"{p}=" in str(c["args"].get("path", ""))
                        for c in calls for p in params)
        out[f"{exp}/{v}"] = {"params": list(params), "runs": len(rs), "runs_using_param": used}
    return out


def thinking_coverage(rows: list[dict]) -> dict:
    steps = with_thinking = 0
    for r in rows:
        for s in _records(r):
            if s["type"] == "step":
                steps += 1
                with_thinking += bool(s["thinking"])
    return {"steps": steps, "steps_with_thinking": with_thinking}


def quotes() -> list[dict]:
    out = []
    for path, step, text in QUOTES:
        p = ROOT / path
        if not p.exists():  # inny zakres pomiaru albo własny RUNS_DIR
            out.append({"file": path, "step": step, "verbatim": None})
            continue
        recs = read_jsonl(p)
        found = any(s["type"] == "step" and s["step"] == step and any(text in t for t in s["thinking"]) for s in recs)
        out.append({"file": path, "step": step, "verbatim": found})
    return out


def dates(rows: list[dict]) -> tuple[str, str] | None:
    if not rows:
        return None
    return min(r["started_at"] for r in rows), max(r["finished_at"] for r in rows)


def main() -> dict:
    rows, _ = load_runs()
    pilot, _ = load_runs(RUNS / "pilot")
    res = {"ui": ui_stats(rows), "tool_errors": tool_errors(rows), "non_ui_failures": non_ui_failures(rows),
           "idempotency": idempotency(rows), "param_usage": param_usage(rows),
           "thinking_coverage": thinking_coverage(rows), "quotes": quotes(),
           "dates": {"pilot": dates(pilot), "full": dates(rows)}}
    (ANALYSIS / "log_checks.json").write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n")
    lines = ["# Liczby z surowych logów (wygenerowane przez analysis/log_checks.py)", "",
             "```json", json.dumps(res, indent=1, ensure_ascii=False), "```", ""]
    (ANALYSIS / "log_checks.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "non_ui_failures"} | {
        "non_ui_failures": {k: v for k, v in res["non_ui_failures"].items() if k != "monday_runs_files"}},
        indent=1, ensure_ascii=False))
    return res


if __name__ == "__main__":
    main()

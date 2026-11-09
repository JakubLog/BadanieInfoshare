"""Taksonomia błędów: każdy nieudany przebieg pełnego planu tagowany osobnym promptem klasyfikującym.

Wynik: analysis/taxonomy.jsonl (tag per przebieg), analysis/taxonomy_log.jsonl (koszt wywołań),
analysis/manual_check.csv (losowe 20% otagowanych przebiegów, pusta kolumna na ocenę ręczną).
Model klasyfikatora: TAGGER_MODEL (domyślnie claude-sonnet-5-5).
"""

from __future__ import annotations

import asyncio
import csv
import json
import os
import random
import re
from collections import Counter

import anthropic

from analysis.common import ANALYSIS, load_runs
from harness.pricing import step_cost
from harness.prompts import TAGGER_SYSTEM, TAXONOMY
from harness.runlog import TAGGER_LOG, read_jsonl, total_spent
from klubfit.db import ROOT

OUT = ANALYSIS / "taxonomy.jsonl"
MANUAL = ANALYSIS / "manual_check.csv"
SAMPLE_SEED = 20261109


def condensed_trace(path) -> str:
    recs = read_jsonl(ROOT / path)
    meta = next(r for r in recs if r["type"] == "meta")
    res = recs[-1]
    lines = [f"Ścieżka: {meta['path']}; wariant: {meta['experiment']}={meta['variant']}; model: {meta['model']}",
             f"Polecenie: {meta['prompt']}",
             f"Walidator: {json.dumps(res['validation'], ensure_ascii=False)[:800]}",
             f"Zakończenie: {res['stop']} po {res['steps']} krokach", "", "Ślad:"]
    for r in recs:
        if r["type"] == "step":
            for t in r.get("thinking", []):
                lines.append(f"[krok {r['step']}] myślenie: {t[:400]}")
            for t in r.get("text", []):
                if t.strip():
                    lines.append(f"[krok {r['step']}] tekst: {t[:400]}")
        elif r["type"] == "tool_call":
            lines.append(f"[krok {r['step']}] {r['name']}({json.dumps(r['args'], ensure_ascii=False)[:300]}) -> "
                         f"{'BŁĄD ' if r['is_error'] else ''}{r['result'][:500]}")
    lines.append(f"Odpowiedź końcowa: {res['final_text'][:800]}")
    text = "\n".join(lines)
    return text if len(text) < 24000 else text[:12000] + "\n[...]\n" + text[-12000:]


def parse(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if obj.get("primary") not in TAXONOMY:
        return None
    obj["secondary"] = [s for s in obj.get("secondary", []) if s in TAXONOMY and s != obj["primary"]]
    return obj

USAGE_KEYS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")


async def _tag_subscription(model: str, trace: str) -> tuple[str, dict]:
    """Klasyfikacja przez Claude Agent SDK zalogowane abonamentem (BACKEND=subscription): bez narzędzi, 1 tura."""
    from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

    opts = ClaudeAgentOptions(system_prompt=TAGGER_SYSTEM, tools=[], setting_sources=[], skills=[], max_turns=1,
                              model=model, effort="low", env={"ANTHROPIC_API_KEY": ""})
    text, usage = "", {k: 0 for k in USAGE_KEYS}
    async for msg in query(prompt=trace, options=opts):
        if isinstance(msg, ResultMessage):
            text = msg.result or ""
            usage = {k: int((msg.usage or {}).get(k) or 0) for k in USAGE_KEYS}
    return text, usage


async def tag_all(concurrency: int = 6) -> None:
    model = os.environ.get("TAGGER_MODEL", "claude-sonnet-5-5")
    limit = float(os.environ.get("BUDGET_USD", "50"))
    done = {json.loads(l)["file"] for l in OUT.read_text().splitlines()} if OUT.exists() else set()
    rows, _ = load_runs()
    todo = [r for r in rows if not r["success"] and r["file"] not in done]
    backend = os.environ.get("BACKEND", "api")
    client = anthropic.AsyncAnthropic(max_retries=10, timeout=300) if backend == "api" else None
    sem = asyncio.Semaphore(concurrency)
    spent = total_spent()
    skipped = 0

    async def one(r):
        nonlocal spent, skipped
        async with sem:
            if spent >= limit:
                skipped += 1
                return
            trace = condensed_trace(r["file"])
            for _attempt in range(2):
                if client is not None:
                    resp = await client.messages.create(
                        model=model, max_tokens=8000, system=TAGGER_SYSTEM, output_config={"effort": "low"},
                        messages=[{"role": "user", "content": trace}])
                    usage = {k: getattr(resp.usage, k, 0) or 0 for k in USAGE_KEYS}
                    text = "".join(b.text for b in resp.content if b.type == "text")
                else:
                    text, usage = await _tag_subscription(model, trace)
                cost = step_cost(model, usage) or 0.0
                spent += cost
                with TAGGER_LOG.open("a", encoding="utf-8") as f:
                    f.write(json.dumps({"type": "tagger", "file": r["file"], "model": model, "usage": usage,
                                        "cost_usd": cost, "backend": backend}) + "\n")
                tag = parse(text)
                if tag:
                    break
            tag = tag or {"primary": "general", "secondary": [], "evidence": "Nie udało się sparsować odpowiedzi klasyfikatora."}
            with OUT.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"file": r["file"], "experiment": r["experiment"], "variant": r["variant"],
                                    "model": r["model"], "task": r["task"], "tagger_model": model, **tag},
                                   ensure_ascii=False) + "\n")

    try:
        await asyncio.gather(*(one(r) for r in todo))
    finally:
        if client is not None:
            await client.close()
    if skipped:
        print(f"Pominięto {skipped} przebiegów: osiągnięto BUDGET_USD")


def write_manual_sample() -> None:
    tags = [json.loads(l) for l in OUT.read_text().splitlines()] if OUT.exists() else []
    tags.sort(key=lambda t: t["file"])
    rng = random.Random(SAMPLE_SEED)
    k = round(0.2 * len(tags))
    sample = sorted(rng.sample(tags, k), key=lambda t: t["file"]) if k else []
    with MANUAL.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file", "experiment", "variant", "model", "task", "model_primary", "model_secondary",
                    "model_evidence", "manual_primary", "manual_notes"])
        for t in sample:
            w.writerow([t["file"], t["experiment"], t["variant"], t["model"], t["task"], t["primary"],
                        ";".join(t["secondary"]), t["evidence"], "", ""])
    counts = Counter(t["primary"] for t in tags)
    print(f"Otagowano {len(tags)} przebiegów; próbka do ręcznej oceny: {k}. Rozkład: {dict(counts.most_common())}")


if __name__ == "__main__":
    if os.environ.get("BACKEND", "api") == "api" and not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("Brak ANTHROPIC_API_KEY w środowisku.")
    asyncio.run(tag_all())
    write_manual_sample()

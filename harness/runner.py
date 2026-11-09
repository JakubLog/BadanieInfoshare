"""Uruchamianie przebiegów: pilot, pełny plan, pojedynczy przebieg.

    uv run python -m harness.runner pilot            # n=2 na wariant × model, potem runs/ESTIMATE.md
    uv run python -m harness.runner full             # plan z runs/plan.json (wynik szacunku)
    uv run python -m harness.runner one --experiment api_errors --variant rich --model claude-haiku-5-5 --task book_anna

Każdy przebieg: świeża kopia bazy z seeda -> środowisko -> pętla agenta -> walidator -> metryki -> log.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import anthropic
import yaml

from harness import metrics as M
from harness.agent import AgentConfig, InfraError, TokenCounter, run_agent
from harness.prompts import system_prompt
from harness.runlog import RUNS, RunLog, completed, total_spent
from harness.tasks import TASKS, validate
from klubfit.db import DATA_DIR, ROOT, connect, reset_db
from klubfit.flags import flags_dict, make_flags
from klubfit.mcp.injection import apply_injection

CONFIG = ROOT / "config" / "experiments.yaml"
DEFAULT_MODELS = "claude-opus-5-5,claude-sonnet-5-5,claude-haiku-5-5"
MAX_INFRA_ATTEMPTS = 3
BACKEND = os.environ.get("BACKEND", "api")   # api (SDK anthropic + klucz) | subscription (Agent SDK + abonament)


def load_config() -> dict:
    return yaml.safe_load(CONFIG.read_text())


def models() -> list[str]:
    return [m.strip() for m in os.environ.get("MODELS", DEFAULT_MODELS).split(",") if m.strip()]


def budget() -> float:
    return float(os.environ.get("BUDGET_USD", "50"))


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


@dataclass(frozen=True)
class RunSpec:
    phase: str          # pilot | full | debug
    experiment: str
    variant: str
    model: str
    task: str
    rep: int

    @property
    def log_path(self) -> Path:
        base = RUNS if self.phase == "full" else RUNS / self.phase
        return base / self.experiment / self.variant / self.model / self.task / f"{self.rep:02d}.jsonl"


def flags_for(cfg: dict, experiment: str, variant: str):
    exp = cfg["experiments"][experiment]
    overrides = {**exp.get("common", {}), **exp["variants"][variant]}
    return exp["path"], make_flags(exp["path"], overrides)


def correct_tools(path: str, flags) -> set[str] | None:
    if path != "mcp":
        return None
    from klubfit.mcp.tools import build_toolset

    return {t.name for t in build_toolset(flags) if t.group != "extra"}


class Context:
    def __init__(self, cfg: dict, concurrency: int, max_cost: float | None, client=None):
        self.cfg = cfg
        self.client = client or (anthropic.AsyncAnthropic(max_retries=10, timeout=300) if BACKEND == "api" else None)
        self.quota_until = 0.0
        self.sem = asyncio.Semaphore(concurrency)
        self.counters: dict[str, TokenCounter] = {}
        self.browser = None
        self._pw = None
        self.spent = total_spent()
        self.max_cost = max_cost
        self.skipped_budget = 0
        self.commit = git_commit()

    def add_cost(self, c: float) -> None:
        self.spent += c

    async def ensure_browser(self):
        if self.browser is None:
            from playwright.async_api import async_playwright

            self._pw = await async_playwright().start()
            self.browser = await self._pw.chromium.launch()
        return self.browser

    async def close(self):
        if self.browser is not None:
            await self.browser.close()
            await self._pw.stop()
        if self.client is not None:
            await self.client.close()


async def make_env(path: str, flags, db_path: Path, ctx: Context):
    if path == "rest":
        from harness.envs.rest import RestEnv

        return RestEnv(db_path, flags)
    if path == "mcp":
        from harness.envs.mcp import McpEnv

        return McpEnv(db_path, flags)
    from harness.envs.ui import UiEnv

    return UiEnv(db_path, flags, await ctx.ensure_browser())


async def execute(spec: RunSpec, ctx: Context) -> dict | None:
    """Jeden przebieg (z ponowieniem przy błędzie infrastruktury). Zwraca rekord wyniku."""
    if completed(spec.log_path):
        return None
    attempt = quota_hits = 0
    while attempt < MAX_INFRA_ATTEMPTS:
        while time.time() < ctx.quota_until:
            await asyncio.sleep(30)
        if ctx.max_cost is not None and ctx.spent >= ctx.max_cost:
            ctx.skipped_budget += 1
            return None
        res = await _attempt(spec, ctx)
        if not res.get("infra_error"):
            return res
        if res.get("quota"):
            quota_hits += 1
            spec.log_path.rename(spec.log_path.with_suffix(f".quota{quota_hits}.jsonl"))
            wait_to = (res.get("resets_at") or time.time() + 600) + 60
            ctx.quota_until = max(ctx.quota_until, wait_to)
            print(f"Limit abonamentu: wstrzymuję do {datetime.fromtimestamp(ctx.quota_until)}", flush=True)
            continue
        attempt += 1
        spec.log_path.rename(spec.log_path.with_suffix(f".infra{attempt}.jsonl"))
        await asyncio.sleep(5 * attempt)
    return res


async def _attempt(spec: RunSpec, ctx: Context) -> dict:
    cfg = ctx.cfg
    exp = cfg["experiments"][spec.experiment]
    path, flags = flags_for(cfg, spec.experiment, spec.variant)
    task = TASKS[spec.task]
    db_path = DATA_DIR / "work" / f"{uuid.uuid4().hex}.sqlite"
    reset_db(db_path)  # świeży stan z seeda przed KAŻDYM przebiegiem
    if getattr(flags, "injection", "none") == "injected":
        conn = connect(db_path)
        apply_injection(conn)
        conn.close()
    log = RunLog(spec.log_path, on_cost=ctx.add_cost)
    started = datetime.now(timezone.utc)
    t0 = time.monotonic()
    env = None
    result: dict = {"type": "result"}
    try:
        env = await make_env(path, flags, db_path, ctx)
        await env.start()
        system = system_prompt(env.system_prompt())
        log.write({"type": "meta", "phase": spec.phase, "experiment": spec.experiment, "variant": spec.variant,
                   "variable": exp["variable"], "priority": exp["priority"], "path": path, "flags": flags_dict(flags),
                   "model": spec.model, "task": spec.task, "rep": spec.rep, "prompt": task.prompt,
                   "started_at": started.isoformat(), "commit": ctx.commit, "system_prompt": system,
                   "system_prompt_sha": hashlib.sha256(system.encode()).hexdigest()[:16],
                   "tools": [t["name"] for t in env.tools], "backend": BACKEND})
        agent_cfg = AgentConfig(model=spec.model, max_steps=cfg["defaults"]["max_steps"],
                                timeout_s=cfg["defaults"]["timeout_s"])
        if BACKEND == "subscription":
            from harness.agent_sdk import run_agent_sdk

            out = await run_agent_sdk(agent_cfg, system, task.prompt, env, log)
        else:
            counter = ctx.counters.setdefault(spec.model, TokenCounter(ctx.client, spec.model))
            out = await run_agent(ctx.client, agent_cfg, system, task.prompt, env, log, counter)
        await env.close()
        env = None
        validation = validate(task, db_path, out.final_text)
        met = M.compute(path, task.prompt, out.calls, validation, correct_tools(path, flags))
        if spec.experiment == "mcp_injection":
            conn = connect(db_path)
            met.update(M.injection_metrics(conn, out.calls))
            conn.close()
        result.update(success=validation["success"], validation=validation, metrics=met, usage=out.usage,
                      tokens_in=out.usage["input_tokens"] + out.usage["cache_creation_input_tokens"]
                      + out.usage["cache_read_input_tokens"], tokens_out=out.usage["output_tokens"],
                      cost_usd=out.cost_usd, cli_cost_usd=out.cli_cost_usd, steps=out.steps, stop=out.stop,
                      final_text=out.final_text, infra_error=None)
    except InfraError as e:
        result.update(infra_error=str(e)[:2000])
    except Exception as e:  # awaria harnessu/środowiska: przebieg nie jest liczony
        if type(e).__name__ == "QuotaError":
            result.update(quota=True, resets_at=getattr(e, "resets_at", None))
        result.update(infra_error=f"{type(e).__name__}: {e}"[:2000])
    finally:
        if env is not None:
            try:
                await env.close()
            except Exception:
                pass
        result["duration_s"] = round(time.monotonic() - t0, 2)
        result["finished_at"] = datetime.now(timezone.utc).isoformat()
        log.write(result)
        log.close()
        for suffix in ("", "-wal", "-shm", "-journal"):
            Path(str(db_path) + suffix).unlink(missing_ok=True)
    return result


def pilot_specs(cfg: dict) -> list[RunSpec]:
    specs = []
    n = cfg["defaults"]["n_pilot"]
    for name, exp in cfg["experiments"].items():
        tasks = exp["tasks"]
        for variant in exp["variants"]:
            for mi, model in enumerate(models()):
                for r in range(1, n + 1):
                    task = tasks[(mi * n + r - 1) % len(tasks)]
                    specs.append(RunSpec("pilot", name, variant, model, task, r))
    return specs


def full_specs(cfg: dict, plan: dict) -> list[RunSpec]:
    specs = []
    for name in plan["experiments"]:
        exp = cfg["experiments"][name]
        for r in range(1, plan["n"] + 1):          # rep na zewnątrz: równomierne wypełnianie komórek
            for variant in exp["variants"]:
                for model in plan["models"]:
                    for task in exp["tasks"]:
                        specs.append(RunSpec("full", name, variant, model, task, r))
    return specs


async def run_specs(specs: list[RunSpec], concurrency: int, max_cost: float | None, client=None) -> Context:
    ctx = Context(load_config(), concurrency, max_cost, client=client)
    done = 0
    total = len(specs)

    async def worker(spec: RunSpec):
        nonlocal done
        async with ctx.sem:
            res = await execute(spec, ctx)
        done += 1
        if res is not None:
            tag = "INFRA" if res.get("infra_error") else ("OK " if res.get("success") else "FAIL")
            print(f"[{done}/{total}] {tag} {spec.experiment}/{spec.variant}/{spec.model}/{spec.task}/{spec.rep:02d} "
                  f"steps={res.get('steps')} cost={res.get('cost_usd')} spent={ctx.spent:.2f}", flush=True)

    try:
        await asyncio.gather(*(worker(s) for s in specs))
    finally:
        await ctx.close()
    if ctx.skipped_budget:
        print(f"Pominięto {ctx.skipped_budget} przebiegów: osiągnięto limit kosztu {max_cost}", flush=True)
    return ctx


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["pilot", "full", "one"])
    ap.add_argument("--experiment")
    ap.add_argument("--variant")
    ap.add_argument("--model")
    ap.add_argument("--task")
    ap.add_argument("--rep", type=int, default=1)
    ap.add_argument("--concurrency", type=int, default=int(os.environ.get("CONCURRENCY", "8")))
    args = ap.parse_args()
    if BACKEND == "api" and not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Brak ANTHROPIC_API_KEY w środowisku (albo ustaw BACKEND=subscription).")
    cfg = load_config()
    if args.phase == "pilot":
        asyncio.run(run_specs(pilot_specs(cfg), args.concurrency, max_cost=budget()))
        from harness.estimate import write_estimate

        write_estimate()
    elif args.phase == "full":
        plan = json.loads((RUNS / "plan.json").read_text())
        if not plan.get("run_full"):
            print("Szacunek nie dopuszcza pełnego przebiegu (runs/plan.json: run_full=false); pomijam.")
            return
        asyncio.run(run_specs(full_specs(cfg, plan), args.concurrency, max_cost=plan["max_cost_usd"]))
    else:
        spec = RunSpec("debug", args.experiment, args.variant, args.model, args.task, args.rep)
        asyncio.run(run_specs([spec], 1, max_cost=budget()))
        print(spec.log_path)


if __name__ == "__main__":
    main()

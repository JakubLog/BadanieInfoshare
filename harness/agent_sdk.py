"""Backend „subscription”: pętla agenta przez Claude Agent SDK zalogowane abonamentem Claude (bez klucza API).

Różnice względem backendu „api” (harness/agent.py), opisane w README:
- agentem steruje CLI Claude Code (`claude -p` pod spodem), z naszym promptem systemowym zamiast domyślnego,
  bez wbudowanych narzędzi, bez ustawień z dysku; narzędzia środowiska są podane jako serwer MCP w procesie,
  więc model widzi je z prefiksem `mcp__klubfit__`;
- koszt to równoważnik cenowy API policzony z `usage` (realnie płaci limit abonamentu);
- rozmiar wyniku narzędzia w tokenach jest szacowany z przyrostu promptu między krokami
  (endpoint count_tokens wymaga klucza API).
"""

from __future__ import annotations

import asyncio
import re
import time

from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions, RateLimitEvent, ResultError, ResultMessage,
                              ToolAnnotations, create_sdk_mcp_server, query, tool)
from claude_agent_sdk.types import TextBlock, ThinkingBlock, ToolUseBlock

from harness.agent import LOG_RESULT_CHARS, AgentConfig, Outcome
from harness.errors import InfraError, QuotaError
from harness.pricing import step_cost

SERVER = "klubfit"
PREFIX = f"mcp__{SERVER}__"
USAGE_KEYS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
RATE_LIMIT_RE = re.compile(r"\b429\b|rate[ _-]?limit", re.I)


def _proxy_tools(env, out: Outcome, state: dict):
    tools = []
    for spec in env.tools:
        name = spec["name"]

        async def handler(args, _name=name):
            args = dict(args or {})
            t1 = time.monotonic()
            try:
                res = await env.call(_name, args)
            except Exception as e:  # awaria środowiska, nie błąd agenta
                state["infra"] = f"Środowisko: {type(e).__name__}: {e}"
                return {"content": [{"type": "text", "text": "Błąd wewnętrzny środowiska."}], "is_error": True}
            out.calls.append({"step": state["step"], "tool_use_id": None, "name": _name, "key": env.tool_key(_name, args),
                              "args": args, "is_error": res.is_error, "result_tokens": None,
                              "result_chars": len(res.text), "duration_s": round(time.monotonic() - t1, 3),
                              "meta": res.meta, "result": res.text})
            return {"content": [{"type": "text", "text": res.text}], "is_error": res.is_error}

        tools.append(tool(name, spec.get("description", ""), spec["input_schema"],
                          annotations=ToolAnnotations(maxResultSizeChars=2_000_000))(handler))
    return create_sdk_mcp_server(SERVER, tools=tools)


def _estimate_result_tokens(steps: list[dict], calls: list[dict]) -> None:
    """Tokeny wyników kroku k ≈ prompt(k+1) − prompt(k) (zawiera też echo wywołań narzędzi kroku k),
    rozdzielone proporcjonalnie do liczby znaków wyników. To szacunek, nie pomiar."""
    def prompt(u):
        return u["input_tokens"] + u["cache_creation_input_tokens"] + u["cache_read_input_tokens"]

    for i in range(len(steps) - 1):
        added = max(0, prompt(steps[i + 1]["usage"]) - prompt(steps[i]["usage"]))
        mine = [c for c in calls if c["step"] == steps[i]["step"]]
        chars = sum(c["result_chars"] for c in mine) or 1
        for c in mine:
            c["result_tokens"] = round(added * c["result_chars"] / chars)


def _write_log(cfg: AgentConfig, log, out: Outcome, steps: list[dict], result_usage: dict | None) -> None:
    """Wiadomości asystenta w strumieniu CLI niosą `usage` z początku odpowiedzi: pola wejściowe są dokładne,
    a output_tokens nie. Sumę wyjścia bierzemy z ResultMessage i doliczamy ją do kosztu ostatniego kroku."""
    inputs = [k for k in USAGE_KEYS if k != "output_tokens"]
    for s in steps:
        s["cost_usd"] = step_cost(cfg.model, {**{k: s["usage"][k] for k in inputs}, "output_tokens": 0})
        for k in inputs:
            out.usage[k] += s["usage"][k]
    partial_out = sum(s["usage"]["output_tokens"] for s in steps)
    total_out = int((result_usage or {}).get("output_tokens") or partial_out)
    out.usage["output_tokens"] = total_out
    if steps:
        last = {k: steps[-1]["usage"][k] for k in inputs}
        extra = step_cost(cfg.model, {**last, "output_tokens": total_out})
        base = step_cost(cfg.model, {**last, "output_tokens": 0})
        if extra is not None and base is not None and steps[-1]["cost_usd"] is not None:
            steps[-1]["cost_usd"] += extra - base
            steps[-1]["run_output_tokens_billed_here"] = total_out
    costs = [s["cost_usd"] for s in steps]
    out.cost_usd = None if any(c is None for c in costs) else sum(costs)
    out.steps = len(steps)
    _estimate_result_tokens(steps, out.calls)
    for s in steps:
        log.write(s)
        for c in out.calls:
            if c["step"] == s["step"]:
                rec = {k: v for k, v in c.items() if k != "result"}
                log.write({"type": "tool_call", **rec, "result_tokens_method": "estimate_prompt_growth",
                           "result": c["result"][:LOG_RESULT_CHARS],
                           "result_truncated": len(c["result"]) > LOG_RESULT_CHARS})


async def run_agent_sdk(cfg: AgentConfig, system: str, user: str, env, log) -> Outcome:
    out = Outcome()
    state = {"step": 0, "infra": None, "steps": {}, "order": [], "result_usage": None}
    try:
        await asyncio.wait_for(_loop(cfg, system, user, env, out, state), timeout=cfg.timeout_s)
    except asyncio.TimeoutError:
        out.stop = "timeout"
    finally:
        _write_log(cfg, log, out, [state["steps"][m] for m in state["order"]], state["result_usage"])
    if state["infra"]:
        raise InfraError(state["infra"])
    return out


async def _loop(cfg: AgentConfig, system: str, user: str, env, out: Outcome, state: dict) -> None:
    options = ClaudeAgentOptions(
        system_prompt=system, tools=[], mcp_servers={SERVER: _proxy_tools(env, out, state)}, strict_mcp_config=True,
        allowed_tools=[PREFIX + t["name"] for t in env.tools], setting_sources=[], skills=[],
        max_turns=cfg.max_steps, model=cfg.model, thinking={"type": "adaptive", "display": "summarized"},
        env={"ANTHROPIC_API_KEY": "", "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"})
    steps, order = state["steps"], state["order"]
    t_prev = time.monotonic()
    try:
        await _consume(query(prompt=user, options=options), out, state, steps, order, t_prev)
    except ResultError as e:
        if e.subtype == "error_max_turns" or "maximum number of turns" in str(e):
            out.stop = "max_steps"  # porażka agenta, nie infrastruktury
        elif RATE_LIMIT_RE.search(str(e)):
            raise QuotaError(f"Agent SDK: {e}", None) from e
        else:
            raise InfraError(f"Agent SDK: {e}") from e
    if not out.stop:
        out.stop = "end_turn"


async def _consume(stream, out: Outcome, state: dict, steps: dict, order: list, t_prev: float) -> None:
    async for msg in stream:
        if isinstance(msg, RateLimitEvent) and msg.rate_limit_info.status == "rejected":
            raise QuotaError(f"limit abonamentu: {msg.rate_limit_info.rate_limit_type}", msg.rate_limit_info.resets_at)
        if isinstance(msg, AssistantMessage):
            if msg.error in ("rate_limit", "billing_error"):
                raise QuotaError(f"limit abonamentu: {msg.error}", None)
            if msg.error:
                raise InfraError(f"Agent SDK: {msg.error}")
            mid = msg.message_id or f"m{len(order)}"
            if mid not in steps:
                state["step"] = len(order) + 1
                now = time.monotonic()
                steps[mid] = {"type": "step", "step": state["step"], "model": msg.model, "stop_reason": None,
                              "latency_s": round(now - t_prev, 3), "usage": {k: 0 for k in USAGE_KEYS},
                              "cost_usd": None, "thinking": [], "text": [], "tool_uses": []}
                t_prev = now
                order.append(mid)
            s = steps[mid]
            if msg.usage:
                s["usage"] = {k: int(msg.usage.get(k) or 0) for k in USAGE_KEYS}
            s["stop_reason"] = msg.stop_reason or s["stop_reason"]
            for b in msg.content:
                if isinstance(b, ThinkingBlock) and b.thinking:
                    s["thinking"].append(b.thinking)
                elif isinstance(b, TextBlock):
                    s["text"].append(b.text)
                elif isinstance(b, ToolUseBlock):
                    s["tool_uses"].append({"id": b.id, "name": b.name.removeprefix(PREFIX), "input": b.input})
        elif isinstance(msg, ResultMessage):
            if msg.is_error and msg.api_error_status == 429:
                raise QuotaError("Agent SDK: HTTP 429", None)
            if msg.is_error and msg.api_error_status:
                raise InfraError(f"Agent SDK: HTTP {msg.api_error_status} {msg.errors}")
            reason = f"{msg.terminal_reason or ''} {msg.subtype or ''}"
            if not msg.is_error:
                out.final_text = (msg.result or "").strip()
            out.stop = "max_steps" if "max_turns" in reason else (msg.stop_reason or "end_turn")
            out.cli_cost_usd = msg.total_cost_usd
            state["result_usage"] = msg.usage

"""Pętla agenta na oficjalnym SDK `anthropic` z tool use (maks. 20 kroków, timeout na przebieg).

Krok = jedno wywołanie Messages API. Wszystkie wywołania narzędzi są logowane przez `RunLog`.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass, field

import anthropic

from harness.envs.base import ToolResult
from harness.errors import InfraError
from harness.pricing import step_cost

LOG_RESULT_CHARS = 4000


@dataclass
class AgentConfig:
    model: str
    max_steps: int = 20
    timeout_s: float = 900
    max_tokens: int = 16000


@dataclass
class Outcome:
    final_text: str = ""
    stop: str = ""                     # end_turn | max_steps | timeout | max_tokens | refusal
    steps: int = 0
    calls: list[dict] = field(default_factory=list)   # pełne wyniki (w pamięci, do metryk)
    usage: dict = field(default_factory=lambda: {"input_tokens": 0, "output_tokens": 0,
                                                 "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0})
    cost_usd: float | None = 0.0
    cli_cost_usd: float | None = None   # backend subscription: koszt wyliczony przez CLI


class TokenCounter:
    """Rozmiar wyniku narzędzia w tokenach (darmowy endpoint count_tokens, z cache po treści)."""

    def __init__(self, client: anthropic.AsyncAnthropic, model: str):
        self.client, self.model = client, model
        self._base: int | None = None
        self._cache: dict[str, int] = {}

    async def _count(self, text: str) -> int:
        r = await self.client.messages.count_tokens(model=self.model, messages=[{"role": "user", "content": text}])
        return r.input_tokens

    async def __call__(self, text: str) -> int | None:
        key = hashlib.sha256(text.encode()).hexdigest()
        if key in self._cache:
            return self._cache[key]
        try:
            if self._base is None:
                self._base = await self._count(".")
            n = max(0, await self._count(text or ".") - self._base)
        except anthropic.APIError:
            return None
        self._cache[key] = n
        return n


def _block_dict(block) -> dict:
    return block.model_dump(mode="json", exclude_none=True)


async def run_agent(client: anthropic.AsyncAnthropic, cfg: AgentConfig, system: str, user: str, env, log,
                    counter: TokenCounter) -> Outcome:
    out = Outcome()
    try:
        await asyncio.wait_for(_loop(client, cfg, system, user, env, log, counter, out), timeout=cfg.timeout_s)
    except asyncio.TimeoutError:
        out.stop = "timeout"
    return out


async def _loop(client, cfg: AgentConfig, system: str, user: str, env, log, counter, out: Outcome) -> None:
    messages: list[dict] = [{"role": "user", "content": user}]
    for step in range(1, cfg.max_steps + 1):
        t0 = time.monotonic()
        try:
            resp = await client.messages.create(
                model=cfg.model, max_tokens=cfg.max_tokens, system=system, tools=env.tools, messages=messages,
                thinking={"type": "adaptive", "display": "summarized"}, cache_control={"type": "ephemeral"})
        except (anthropic.APIConnectionError, anthropic.APIStatusError) as e:
            raise InfraError(f"API: {type(e).__name__}: {e}") from e
        latency = time.monotonic() - t0
        usage = {k: getattr(resp.usage, k, 0) or 0 for k in out.usage}
        for k, v in usage.items():
            out.usage[k] += v
        cost = step_cost(cfg.model, usage)
        out.cost_usd = None if cost is None or out.cost_usd is None else out.cost_usd + cost
        out.steps = step
        thinking = [b.thinking for b in resp.content if b.type == "thinking" and b.thinking]
        texts = [b.text for b in resp.content if b.type == "text"]
        tool_uses = [b for b in resp.content if b.type == "tool_use"]
        log.write({"type": "step", "step": step, "model": resp.model, "stop_reason": resp.stop_reason,
                   "latency_s": round(latency, 3), "usage": usage, "cost_usd": cost, "thinking": thinking,
                   "text": texts, "tool_uses": [{"id": b.id, "name": b.name, "input": b.input} for b in tool_uses]})
        messages.append({"role": "assistant", "content": [_block_dict(b) for b in resp.content]})
        if resp.stop_reason != "tool_use" or not tool_uses:
            out.final_text = "\n".join(texts).strip()
            out.stop = resp.stop_reason or "end_turn"
            return
        results = []
        for b in tool_uses:
            t1 = time.monotonic()
            try:
                res: ToolResult = await env.call(b.name, dict(b.input or {}))
            except Exception as e:  # awaria środowiska, nie błąd agenta
                raise InfraError(f"Środowisko: {type(e).__name__}: {e}") from e
            dur = time.monotonic() - t1
            ntok = await counter(res.text)
            key = env.tool_key(b.name, dict(b.input or {}))
            call = {"step": step, "tool_use_id": b.id, "name": b.name, "key": key, "args": b.input,
                    "is_error": res.is_error, "result_tokens": ntok, "result_chars": len(res.text),
                    "duration_s": round(dur, 3), "meta": res.meta}
            log.write({"type": "tool_call", **call, "result": res.text[:LOG_RESULT_CHARS],
                       "result_truncated": len(res.text) > LOG_RESULT_CHARS})
            out.calls.append({**call, "result": res.text})
            results.append({"type": "tool_result", "tool_use_id": b.id, "content": res.text, "is_error": res.is_error})
        messages.append({"role": "user", "content": results})
    out.stop = "max_steps"

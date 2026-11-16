"""Backend `subscription`: grupowanie strumienia CLI w kroki, tokeny wyjściowe z ResultMessage, koszt i limit kroków.

Strumień jest sztuczny (prawdziwe typy SDK), bez uruchamiania CLI ani modelu.
"""

import pytest
from claude_agent_sdk import AssistantMessage, ResultMessage
from claude_agent_sdk.types import TextBlock, ThinkingBlock, ToolUseBlock

from harness.agent import AgentConfig, Outcome
from harness.agent_sdk import _consume, _write_log
from harness.pricing import step_cost

MODEL = "claude-sonnet-5-5"


def usage(inp, cw, cr, out=1):
    return {"input_tokens": inp, "cache_creation_input_tokens": cw, "cache_read_input_tokens": cr, "output_tokens": out}


def msg(mid, blocks, u):
    return AssistantMessage(content=blocks, model=MODEL, usage=u, message_id=mid)


async def _stream(items):
    for m in items:
        yield m


class Log:
    def __init__(self):
        self.records = []

    def write(self, rec):
        self.records.append(rec)


async def _run(items):
    out = Outcome()
    state = {"step": 0, "infra": None, "steps": {}, "order": [], "result_usage": None}
    await _consume(_stream(items), out, state, state["steps"], state["order"], 0.0)
    log = Log()
    _write_log(AgentConfig(model=MODEL), log, out, [state["steps"][m] for m in state["order"]], state["result_usage"])
    return out, log


async def test_blocks_with_same_message_id_form_one_step_and_output_comes_from_result():
    u1, u2 = usage(2, 1000, 0), usage(2, 300, 1000)
    items = [
        msg("m1", [ThinkingBlock("szukam klientki", "sig")], u1),
        msg("m1", [ToolUseBlock("t1", "mcp__klubfit__search_clients", {"query": "Anna"})], u1),
        msg("m2", [TextBlock("Gotowe.")], u2),
        ResultMessage(subtype="success", duration_ms=1, duration_api_ms=1, is_error=False, num_turns=2,
                      session_id="s", result="Gotowe.", usage=usage(0, 0, 0, out=250), total_cost_usd=0.5),
    ]
    out, log = await _run(items)
    steps = [r for r in log.records if r["type"] == "step"]
    assert [s["step"] for s in steps] == [1, 2]
    assert steps[0]["thinking"] == ["szukam klientki"]
    assert steps[0]["tool_uses"][0]["name"] == "search_clients"  # prefiks MCP zdjęty
    assert out.usage["output_tokens"] == 250  # suma z ResultMessage, nie z wiadomości strumienia
    assert out.usage["cache_creation_input_tokens"] == 1300
    expected = (step_cost(MODEL, {**u1, "output_tokens": 0})
                + step_cost(MODEL, {**u2, "output_tokens": 250}))
    assert out.cost_usd == pytest.approx(expected)
    assert out.final_text == "Gotowe." and out.stop == "end_turn" and out.cli_cost_usd == 0.5


async def test_max_turns_result_is_agent_failure_without_final_text():
    items = [
        msg("m1", [ToolUseBlock("t1", "mcp__klubfit__snapshot", {})], usage(2, 10, 0)),
        ResultMessage(subtype="error_max_turns", duration_ms=1, duration_api_ms=1, is_error=True, num_turns=20,
                      session_id="s", result=None, usage=usage(0, 0, 0, out=40), terminal_reason="max_turns"),
    ]
    out, _ = await _run(items)
    assert out.stop == "max_steps" and out.final_text == ""

"""Pełna ścieżka runnera (reset bazy -> środowisko -> pętla -> walidator -> metryki -> log) ze skryptowanym
modelem zamiast API. Sprawdza zachowanie walidatora i metryk na realnych środowiskach REST i MCP."""

import json
from types import SimpleNamespace

import anthropic
import pytest

import harness.runlog
import harness.runner as runner
from harness.runlog import read_jsonl


def _msg(content, stop):
    return anthropic.types.Message.model_validate({
        "id": "msg_fake", "type": "message", "role": "assistant", "model": "claude-haiku-5-5", "content": content,
        "stop_reason": stop, "stop_sequence": None,
        "usage": {"input_tokens": 1000, "output_tokens": 50, "cache_creation_input_tokens": 0,
                  "cache_read_input_tokens": 0}})


def _last_result(kw) -> str:
    last = kw["messages"][-1]["content"]
    return last[-1]["content"] if isinstance(last, list) else ""


class FakeClient:
    def __init__(self, policy):
        self.policy, self.step = policy, 0
        self.messages = SimpleNamespace(create=self._create, count_tokens=self._count)

    async def _create(self, **kw):
        self.step += 1
        blocks = self.policy(self.step, kw)
        tool = any(b["type"] == "tool_use" for b in blocks)
        return _msg([{"type": "thinking", "thinking": f"krok {self.step}", "signature": "s"}, *blocks],
                    "tool_use" if tool else "end_turn")

    async def _count(self, **kw):
        return SimpleNamespace(input_tokens=1 + len(kw["messages"][0]["content"]) // 4)

    async def close(self):
        pass


def _tool(name, args, i=1):
    return {"type": "tool_use", "id": f"tu_{i}", "name": name, "input": args}


def rest_book_anna(step, kw):
    if step == 1:
        return [_tool("http_request", {"method": "GET", "path": "/clients", "query": {"email": "anna.kowalska@gmail.com"}})]
    body = json.loads(_last_result(kw).split("\n", 1)[1])
    if step == 2:
        rest_book_anna.anna = body["items"][0]["id"]
        return [_tool("http_request", {"method": "GET", "path": "/classes", "query": {"date": "2026-11-12", "type": "joga"}})]
    if step == 3:
        yoga = next(k for k in body["items"] if k["starts_at"] == "2026-11-12T17:00:00Z")
        return [_tool("http_request", {"method": "POST", "path": "/bookings",
                                       "body": {"client_id": rest_book_anna.anna, "class_id": yoga["id"]}})]
    return [{"type": "text", "text": "Zapisano Annę Kowalską."}]


def mcp_retry_after_timeout(step, kw):
    if step == 1:
        return [_tool("search_clients", {"query": "Anna Kowalska"})]
    if step == 2:
        mcp_retry_after_timeout.anna = json.loads(_last_result(kw))["results"][0]["client_id"]
        return [_tool("list_classes", {"date": "2026-11-12", "type": "joga"})]
    if step == 3:
        k = next(c for c in json.loads(_last_result(kw))["classes"] if c["starts_at"].startswith("2026-11-12T18:00"))
        mcp_retry_after_timeout.args = {"client_id": mcp_retry_after_timeout.anna, "class_id": k["class_id"]}
        return [_tool("create_booking", mcp_retry_after_timeout.args)]
    if step == 4:
        return [_tool("create_booking", mcp_retry_after_timeout.args)]
    return [{"type": "text", "text": "Gotowe."}]


def mcp_invented_id(step, kw):
    if step == 1:
        return [_tool("create_booking", {"client_id": "11111111-2222-4333-8444-555555555555",
                                         "class_id": "11111111-2222-4333-8444-666666666666"})]
    return [{"type": "text", "text": "Nie udało się."}]


@pytest.fixture
def runs_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(harness.runlog, "RUNS", tmp_path)
    monkeypatch.setattr(runner, "RUNS", tmp_path)
    monkeypatch.setattr(runner, "BACKEND", "api")  # FakeClient zastępuje API niezależnie od BACKEND w środowisku
    monkeypatch.setattr(harness.runlog, "TAGGER_LOG", tmp_path / "taxonomy_log.jsonl")
    return tmp_path


async def _run(spec, policy):
    await runner.run_specs([spec], 1, max_cost=None, client=FakeClient(policy))
    return read_jsonl(spec.log_path)


async def test_rest_happy_path_is_validated_from_db_state(runs_dir):
    recs = await _run(runner.RunSpec("test", "api_errors", "rich", "claude-haiku-5-5", "book_anna", 1), rest_book_anna)
    assert [r["type"] for r in recs] == ["meta", "step", "tool_call", "step", "tool_call", "step", "tool_call", "step", "result"]
    res = recs[-1]
    assert res["success"] is True and res["infra_error"] is None
    assert res["metrics"]["n_calls"] == 3 and res["metrics"]["id_not_seen"] == 0 and not res["metrics"]["loop"]
    assert res["cost_usd"] == pytest.approx(4 * (1000 * 0.10 + 50 * 0.50) / 1e6)
    assert all(r["result_tokens"] > 0 for r in recs if r["type"] == "tool_call")


async def test_retry_after_timeout_creates_duplicate_and_fails(runs_dir):
    spec = runner.RunSpec("test", "mcp_idempotency", "direct", "claude-haiku-5-5", "book_anna", 1)
    res = (await _run(spec, mcp_retry_after_timeout))[-1]
    assert res["success"] is False
    m = res["metrics"]
    assert m["duplicates"] == 1 and m["self_repairs"] == 1 and m["wrong_tool_calls"] == 0


async def test_invented_ids_are_counted(runs_dir):
    spec = runner.RunSpec("test", "mcp_granularity", "granular", "claude-haiku-5-5", "book_anna", 1)
    res = (await _run(spec, mcp_invented_id))[-1]
    assert res["success"] is False and res["metrics"]["id_not_seen"] == 2

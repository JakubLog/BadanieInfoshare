import json
import re

import pytest

from harness.envs.mcp import McpEnv
from harness.tasks import SPINNING_SAT, class_id
from klubfit.flags import McpFlags
from klubfit.mcp.tools import McpState, build_toolset, run_tool
from tests.conftest import client_id

NAME_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


@pytest.mark.parametrize("count,expected", [("5", 5), ("20", 20), ("60", 60), ("60ns", 60)])
def test_toolcount_variants(count, expected):
    tools = build_toolset(McpFlags(toolcount=count))
    names = [t.name for t in tools]
    assert len(names) == len(set(names)) == expected
    assert all(NAME_RE.match(n) for n in names)
    if count == "60ns":
        assert "zajecia_create_booking" in names and all("_" in n for n in names)


def test_granularity_and_idempotency_toolsets():
    assert [t.name for t in build_toolset(McpFlags(granularity="task"))] == ["book_class"]
    names = {t.name for t in build_toolset(McpFlags(idempotency="confirm"))}
    assert {"prepare_booking", "confirm_booking"} <= names and "create_booking" not in names


def _state(conn, **flags):
    flags = McpFlags(**flags)
    return McpState(conn, flags), {t.name: t for t in build_toolset(flags)}


def test_timeout_then_retry_duplicates_only_without_idempotency(conn):
    ewa, spin = client_id(conn, "ewa.wojcik@o2.pl"), class_id(conn, SPINNING_SAT)
    st, tools = _state(conn, fault="timeout_first_write")
    for _ in range(2):
        run_tool(st, tools, "create_booking", {"client_id": ewa, "class_id": spin})
    jan = client_id(conn, "jan.kaminski82@gmail.com")
    st2, tools2 = _state(conn, fault="timeout_first_write", idempotency="confirm")
    token = json.loads(run_tool(st2, tools2, "prepare_booking", {"client_id": jan, "class_id": spin})[0])["confirmation_token"]
    text, err = run_tool(st2, tools2, "confirm_booking", {"confirmation_token": token})
    assert err and "UPSTREAM_TIMEOUT" in text
    text, err = run_tool(st2, tools2, "confirm_booking", {"confirmation_token": token})
    assert not err and json.loads(text)["already_confirmed"] is True
    counts = dict(conn.execute("SELECT client_id, COUNT(*) FROM bookings WHERE class_id=? AND status='active' "
                               "AND client_id IN (?, ?) GROUP BY client_id", (spin, ewa, jan)).fetchall())
    assert counts == {ewa: 2, jan: 1}


def test_book_class_disambiguates_by_email(conn):
    st, tools = _state(conn, granularity="task")
    text, err = run_tool(st, tools, "book_class", {"client": "Jan Kamiński", "class_name": "Spinning",
                                                   "date": "2026-11-14", "time": "10:00"})
    assert err and json.loads(text)["error"]["code"] == "AMBIGUOUS_CLIENT"
    text, err = run_tool(st, tools, "book_class", {"client": "jan.kaminski82@gmail.com", "class_name": "Spinning",
                                                   "date": "2026-11-14", "time": "10:00"})
    assert not err and json.loads(text)["client"] == "Jan Kamiński"


async def test_stdio_server_lists_variant_tools(db):
    env = McpEnv(db, McpFlags(toolcount="20", descriptions="full"))
    await env.start()
    try:
        assert len(env.tools) == 20
        res = await env.call("search_clients", {"query": "Anna Kowalska"})
        assert not res.is_error and json.loads(res.text)["total"] == 2
    finally:
        await env.close()

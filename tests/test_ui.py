import pytest
from playwright.async_api import async_playwright

from harness.envs.ui import UiEnv
from harness.tasks import TASKS, validate
from klubfit.flags import UiFlags
from tests.conftest import client_id


@pytest.fixture
async def browser():
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        yield b
        await b.close()


async def _env(db, browser, variant):
    env = UiEnv(db, UiFlags(ui=variant), browser)
    await env.start()
    return env


async def test_variant_a_books_via_labelled_controls(db, conn, browser):
    env = await _env(db, browser, "A")
    try:
        await env.call("goto", {"url": f"/clients/{client_id(conn, 'anna.kowalska@gmail.com')}"})
        assert not (await env.call("fill", {"label": "Data zajęć", "value": "2026-11-12"})).is_error
        await env.call("click", {"role": "button", "name": "Pokaż zajęcia"})
        r = await env.call("click", {"role": "button", "name": "Zapisz na Joga, czw 12.11.2026 18:00"})
        assert not r.is_error
        snap = (await env.call("snapshot", {})).text
        assert 'status: "Zapisano: Anna Kowalska' in snap
    finally:
        await env.close()
    assert validate(TASKS["book_anna"], db, "")["success"]


async def test_variant_b_hides_roles_menu_and_success_message(db, conn, browser):
    env = await _env(db, browser, "B")
    try:
        home = (await env.call("snapshot", {})).text
        assert "button" not in home and "Klienci" not in home  # menu tylko po najechaniu
        await env.call("click", {"role": "text", "name": "☰"})
        assert "Klienci" in (await env.call("snapshot", {})).text
        await env.call("goto", {"url": f"/clients/{client_id(conn, 'anna.kowalska@gmail.com')}?date=2026-11-12"})
        assert (await env.call("click", {"role": "button", "name": "Zapisz"})).is_error
        assert not (await env.call("click", {"role": "text", "name": "＋", "index": 1})).is_error
        await env.page.wait_for_timeout(3200)
        assert "Zapisano" not in (await env.call("snapshot", {})).text  # toast zniknął
    finally:
        await env.close()
    assert validate(TASKS["book_anna"], db, "")["success"]

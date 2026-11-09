import pytest
from fastapi.testclient import TestClient

from harness.tasks import YOGA_THU, class_id
from klubfit.api.rest import create_rest_app
from klubfit.flags import RestFlags
from tests.conftest import client_id


def api(db, **flags):
    return TestClient(create_rest_app(db, RestFlags(**flags)))


@pytest.mark.parametrize("errors,status,body_has_code", [("generic", 400, False), ("rich", 422, True)])
def test_error_variants(db, errors, status, body_has_code):
    r = api(db, errors=errors).get("/classes", params={"date": "12.11.2026"})
    assert r.status_code == status
    body = r.json()
    if body_has_code:
        assert body["error"]["field"] == "date" and body["error"]["example"] == "2026-11-12"
    else:
        assert body == {"error": "Bad Request"}


def test_pagination_silent_truncates_and_meta_reports_total(db, conn):
    yoga = class_id(conn, YOGA_THU)
    silent = api(db, pagination="silent").get(f"/classes/{yoga}/bookings").json()
    assert isinstance(silent, list) and len(silent) == 20
    c = api(db, pagination="meta")
    first = c.get(f"/classes/{yoga}/bookings").json()
    assert first["total"] == 23 and first["returned"] == 20 and "cursor=" in first["note"]
    rest = c.get(f"/classes/{yoga}/bookings", params={"cursor": first["next_cursor"]}).json()
    assert rest["returned"] == 3 and rest["next_cursor"] is None
    ids = {b["id"] for b in first["items"]} | {b["id"] for b in rest["items"]}
    assert len(ids) == 23


def test_readable_ids_round_trip(db, conn):
    c = api(db, ids="readable")
    anna = c.get("/clients", params={"email": "anna.kowalska@gmail.com"}).json()["items"][0]
    assert anna["id"] == "anna_kowalska_042"
    r = c.post("/bookings", json={"client_id": "anna_kowalska_042", "class_id": "joga_2026-11-12_1800"})
    assert r.status_code == 201
    booking = r.json()
    assert booking["id"].startswith("rez_") and booking["client_id"] == "anna_kowalska_042"
    assert c.delete(f"/bookings/{booking['id']}").json()["status"] == "cancelled"
    real = client_id(conn, "anna.kowalska@gmail.com")
    assert conn.execute("SELECT COUNT(*) FROM bookings WHERE client_id = ?", (real,)).fetchone()[0] == 3


def test_uuid_variant_rejects_readable_id(db):
    r = api(db, errors="rich").post("/bookings", json={"client_id": "anna_kowalska_042", "class_id": "x"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_ID"


def test_shape_variants(db):
    full = api(db).get("/clients", params={"q": "Kowalska", "fields": "id,email"}).json()["items"][0]
    assert len(full) == 80  # w wariancie full parametr fields nie działa
    proj = api(db, shape="fields").get("/clients", params={"q": "Kowalska", "fields": "id,email"}).json()["items"][0]
    assert set(proj) == {"id", "email"}
    concise = api(db, shape="concise").get("/clients", params={"q": "Kowalska", "response_format": "concise"})
    assert set(concise.json()["items"][0]) == {"id", "name", "email", "phone"}

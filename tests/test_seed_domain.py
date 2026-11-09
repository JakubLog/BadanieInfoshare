import pytest

from harness.tasks import CROSSFIT_FRI, CROSSFIT_SAT, SPINNING_SAT, YOGA_THU, class_id
from klubfit.db import CLIENT_COLUMNS, SEED_DB
from klubfit.domain import services as svc
from klubfit.domain.errors import DomainError
from klubfit.seed import build_seed_db, fingerprint
from tests.conftest import client_id


def test_seed_is_deterministic(tmp_path):
    a = build_seed_db(tmp_path / "a.sqlite")
    b = build_seed_db(tmp_path / "b.sqlite")
    assert fingerprint(a) == fingerprint(b) == fingerprint(SEED_DB)


def test_reset_restores_seed_after_writes(db, conn):
    anna = client_id(conn, "anna.kowalska@gmail.com")
    svc.create_booking(conn, anna, class_id(conn, YOGA_THU))
    assert fingerprint(db) != fingerprint(SEED_DB)
    from klubfit.db import reset_db

    assert fingerprint(reset_db(db)) == fingerprint(SEED_DB)


def test_seed_story_facts(conn):
    assert conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0] == 340
    assert len(conn.execute("SELECT * FROM clients LIMIT 1").fetchone().keys()) == len(CLIENT_COLUMNS) == 80
    assert svc.booked_count(conn, class_id(conn, YOGA_THU)) == 23
    full = svc.get_class(conn, class_id(conn, CROSSFIT_FRI))
    assert svc.spots_left(conn, full) == 0
    assert len(svc.search_clients(conn, q="Jan Kamiński")) == 2
    expiring = svc.list_memberships(conn, status="active", expires_from=svc.parse_date("2026-11-09"),
                                    expires_to=svc.parse_date("2026-11-16"))
    assert len({m["client_id"] for m in expiring}) == 26
    dup = conn.execute("SELECT COUNT(*) FROM (SELECT 1 FROM bookings WHERE status='active' "
                       "GROUP BY client_id, class_id HAVING COUNT(*) > 1)").fetchone()[0]
    assert dup == 0


def test_full_class_reports_next_available(conn):
    kasia = client_id(conn, "k.lewandowska@interia.pl")
    with pytest.raises(DomainError) as e:
        svc.create_booking(conn, kasia, class_id(conn, CROSSFIT_FRI))
    assert e.value.code == "CLASS_FULL"
    assert e.value.details["next_available"][0]["class_id"] == class_id(conn, CROSSFIT_SAT)


def test_expired_membership_blocks_booking(conn):
    expired = conn.execute("SELECT client_id FROM memberships m WHERE status='expired' AND client_id NOT IN "
                           "(SELECT client_id FROM memberships WHERE status='active')").fetchone()["client_id"]
    with pytest.raises(DomainError) as e:
        svc.create_booking(conn, expired, class_id(conn, SPINNING_SAT))
    assert e.value.code == "MEMBERSHIP_INVALID"


def test_schedule_conflict_but_same_class_duplicate_allowed(conn):
    jan_decoy = client_id(conn, "jan.kaminski@wp.pl")  # ma sobotni crossfit 11:30
    sat_joga = next(k for k in svc.list_classes(conn, on=svc.parse_date("2026-11-14")) if k["name"] == "Joga")
    svc.create_booking(conn, jan_decoy, sat_joga["id"])  # 10:00–11:00, bez kolizji z 11:30
    ewa = client_id(conn, "ewa.wojcik@o2.pl")
    spin = class_id(conn, SPINNING_SAT)
    svc.create_booking(conn, ewa, spin)
    with pytest.raises(DomainError) as e:
        svc.create_booking(conn, ewa, sat_joga["id"])  # 10:00 joga nachodzi na 10:00 spinning
    assert e.value.code == "SCHEDULE_CONFLICT"
    svc.create_booking(conn, ewa, spin)  # znana cecha legacy: duplikat przechodzi
    assert conn.execute("SELECT COUNT(*) FROM bookings WHERE client_id=? AND class_id=? AND status='active'",
                        (ewa, spin)).fetchone()[0] == 2


def test_past_class_and_bad_date(conn):
    anna = client_id(conn, "anna.kowalska@gmail.com")
    monday_morning = svc.list_classes(conn, on=svc.parse_date("2026-11-09"))[0]
    with pytest.raises(DomainError) as e:
        svc.create_booking(conn, anna, monday_morning["id"])
    assert e.value.code == "CLASS_IN_PAST"
    with pytest.raises(DomainError) as e:
        svc.parse_date("12.11.2026")
    assert e.value.as_dict()["expected"] == "YYYY-MM-DD"

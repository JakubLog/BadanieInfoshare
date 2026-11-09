from harness.tasks import (CROSSFIT_SAT, PILATES_TUE, PILATES_WED, SPINNING_SAT, TASKS, YOGA_THU, class_id,
                           validate)
from klubfit.domain import services as svc
from tests.conftest import client_id


def _expiring_emails(conn):
    return sorted({m["client_email"] for m in svc.list_memberships(
        conn, status="active", expires_from=svc.parse_date("2026-11-09"), expires_to=svc.parse_date("2026-11-16"))})


def test_count_answer_and_false_completeness(db):
    ok = validate(TASKS["count_yoga"], db, "Zapisanych jest 23 osoby.\nWYNIK: 23")
    assert ok["success"] and not ok["false_completeness"]
    first_page = validate(TASKS["count_yoga"], db, "Na liście jest 20 osób.\nWYNIK: 20")
    assert not first_page["success"] and first_page["false_completeness"]
    no_claim = validate(TASKS["count_yoga"], db, "Nie wiem.")
    assert not no_claim["success"] and not no_claim["false_completeness"]


def test_expiring_requires_full_email_list(db, conn):
    emails = _expiring_emails(conn)
    assert validate(TASKS["expiring"], db, "\n".join(emails) + "\nWYNIK: 26")["success"]
    partial = validate(TASKS["expiring"], db, "\n".join(emails[:20]) + "\nWYNIK: 20")
    assert not partial["success"] and partial["false_completeness"] and partial["listed_missing"] == 6


def test_move_requires_cancel_and_new_booking(db, conn):
    piotr = client_id(conn, "piotr.nowak@gmail.com")
    svc.create_booking(conn, piotr, class_id(conn, PILATES_WED))
    assert not validate(TASKS["move_booking"], db, "")["success"]  # stara rezerwacja nadal aktywna
    old = next(b for b in svc.client_bookings(conn, piotr) if b["class_id"] == class_id(conn, PILATES_TUE))
    svc.cancel_booking(conn, old["id"])
    assert validate(TASKS["move_booking"], db, "")["success"]


def test_book_two_rejects_wrong_namesake(db, conn):
    spin = class_id(conn, SPINNING_SAT)
    svc.create_booking(conn, client_id(conn, "ewa.wojcik@o2.pl"), spin)
    svc.create_booking(conn, client_id(conn, "jan.kaminski@wp.pl"), spin)
    res = validate(TASKS["book_two"], db, "")
    assert not res["success"] and len(res["missing"]) == 1 and len(res["unexpected_new"]) == 1


def test_extra_side_effect_fails_write_task(db, conn):
    anna = client_id(conn, "anna.kowalska@gmail.com")
    svc.create_booking(conn, anna, class_id(conn, YOGA_THU))
    assert validate(TASKS["book_anna"], db, "")["success"]
    svc.create_booking(conn, anna, class_id(conn, CROSSFIT_SAT))
    assert not validate(TASKS["book_anna"], db, "")["success"]

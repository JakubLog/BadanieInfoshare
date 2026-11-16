"""Schemat SQLite, połączenia i reset bazy do stanu z seeda."""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SEED_DB = DATA_DIR / "seed.sqlite"

# 80 kolumn klienta: dane podstawowe, kontakt, zgody, metadane audytowe, pola legacy.
CLIENT_COLUMNS: list[str] = [
    "id", "first_name", "last_name", "email", "phone", "birth_date", "gender",
    "street", "house_number", "city", "postal_code", "country",
    "preferred_language", "preferred_club", "home_club_id", "notes",
    "marketing_consent", "sms_consent", "email_consent", "photo_consent",
    "gdpr_consent_at", "gdpr_consent_version", "terms_version",
    "emergency_contact_name", "emergency_contact_phone",
    "company_name", "nip", "invoice_email", "payment_method", "iban_masked",
    "debt_pln", "ltv_pln", "loyalty_points", "loyalty_tier", "referral_code",
    "referred_by", "source_channel", "utm_source", "utm_campaign", "segment",
    "churn_score", "card_number", "card_issued_at", "rfid_tag", "locker_number",
    "medical_clearance_until", "height_cm", "weight_kg", "training_goal",
    "assigned_trainer_id", "app_installed", "push_token", "last_login_at",
    "last_visit_at", "visits_total", "newsletter_frequency", "timezone", "locale",
    "avatar_url", "blocked", "blocked_reason", "is_test_account",
    "created_at", "created_by", "updated_at", "updated_by", "deleted_at",
    "version", "row_checksum", "sync_hash", "crm_sync_status", "crm_external_id",
    "erp_customer_no", "legacy_id", "legacy_system", "legacy_import_batch",
    "legacy_club_code", "legacy_status_flag", "migration_note", "audit_ip_created",
]
assert len(CLIENT_COLUMNS) == 80, len(CLIENT_COLUMNS)

SCHEMA = f"""
CREATE TABLE clients (
    {", ".join(f"{c} TEXT" if c != "id" else "id TEXT PRIMARY KEY" for c in CLIENT_COLUMNS)}
);
CREATE INDEX idx_clients_email ON clients(email);

CREATE TABLE memberships (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL REFERENCES clients(id),
    plan TEXT NOT NULL,
    valid_from TEXT NOT NULL,
    valid_to TEXT NOT NULL,
    status TEXT NOT NULL,
    entries_left INTEGER,
    price_pln REAL NOT NULL,
    auto_renew INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    legacy_contract_no TEXT
);
CREATE INDEX idx_memberships_client ON memberships(client_id);

CREATE TABLE classes (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    starts_at TEXT NOT NULL,
    duration_min INTEGER NOT NULL,
    room TEXT NOT NULL,
    trainer TEXT NOT NULL,
    capacity INTEGER NOT NULL,
    level TEXT NOT NULL,
    status TEXT NOT NULL,
    description TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    legacy_code TEXT
);
CREATE INDEX idx_classes_starts ON classes(starts_at);

CREATE TABLE bookings (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL REFERENCES clients(id),
    class_id TEXT NOT NULL REFERENCES classes(id),
    status TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL,
    cancelled_at TEXT,
    created_by TEXT NOT NULL,
    seq INTEGER NOT NULL
);
CREATE INDEX idx_bookings_class ON bookings(class_id);
CREATE INDEX idx_bookings_client ON bookings(client_id);

-- Log akcji wykonanych narzędziami spoza domeny rezerwacji (MCP, narzędzia dodatkowe).
CREATE TABLE aux_actions (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    tool TEXT NOT NULL,
    arguments TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def ensure_seed(seed_path: str | Path = SEED_DB) -> Path:
    """Buduje plik seeda, jeśli go nie ma (albo jest pusty, np. po nieudanym otwarciu)."""
    seed_path = Path(seed_path)
    if not seed_path.exists() or seed_path.stat().st_size == 0:
        from klubfit.seed import build_seed_db

        build_seed_db(seed_path)
    return seed_path


def reset_db(target: str | Path, seed_path: str | Path = SEED_DB) -> Path:
    """Kopiuje nienaruszony plik seeda pod `target`. Wywoływane przed KAŻDYM przebiegiem."""
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    ensure_seed(seed_path)
    for suffix in ("", "-wal", "-shm", "-journal"):
        p = Path(str(target) + suffix)
        if p.exists():
            p.unlink()
    shutil.copyfile(seed_path, target)
    return target

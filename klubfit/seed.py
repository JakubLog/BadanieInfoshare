"""Deterministyczny seed Klubu Fit (stały seed RNG).

Fakty, na których opierają się zadania, są ustawiane jawnie (sekcja STORY),
reszta danych jest losowana z `random.Random(SEED)`.
"""

from __future__ import annotations

import hashlib
import random
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from klubfit.clock import NOW_LOCAL, SCHEDULE_START, SCHEDULE_WEEKS, TZ
from klubfit.db import CLIENT_COLUMNS, SEED_DB, connect, create_schema

SEED = 20261109
N_CLIENTS = 340
UTC = ZoneInfo("UTC")

FEMALE = ["Anna", "Maria", "Katarzyna", "Małgorzata", "Agnieszka", "Barbara", "Ewa", "Krystyna",
          "Magdalena", "Joanna", "Aleksandra", "Monika", "Zofia", "Natalia", "Karolina", "Julia",
          "Marta", "Beata", "Dorota", "Paulina", "Justyna", "Agata", "Weronika", "Alicja", "Iwona",
          "Hanna", "Emilia", "Patrycja", "Izabela", "Kinga"]
MALE = ["Piotr", "Krzysztof", "Andrzej", "Tomasz", "Paweł", "Jan", "Michał", "Marcin", "Jakub",
        "Adam", "Łukasz", "Marek", "Grzegorz", "Mateusz", "Wojciech", "Mariusz", "Dariusz", "Kamil",
        "Maciej", "Rafał", "Bartosz", "Sebastian", "Szymon", "Filip", "Oskar", "Igor", "Dawid",
        "Robert", "Artur", "Damian"]
LAST = [("Nowak", "Nowak"), ("Kowalski", "Kowalska"), ("Wiśniewski", "Wiśniewska"), ("Wójcik", "Wójcik"),
        ("Kowalczyk", "Kowalczyk"), ("Kamiński", "Kamińska"), ("Lewandowski", "Lewandowska"),
        ("Zieliński", "Zielińska"), ("Szymański", "Szymańska"), ("Woźniak", "Woźniak"),
        ("Dąbrowski", "Dąbrowska"), ("Kozłowski", "Kozłowska"), ("Jankowski", "Jankowska"),
        ("Mazur", "Mazur"), ("Kwiatkowski", "Kwiatkowska"), ("Krawczyk", "Krawczyk"),
        ("Piotrowski", "Piotrowska"), ("Grabowski", "Grabowska"), ("Nowakowski", "Nowakowska"),
        ("Pawłowski", "Pawłowska"), ("Michalski", "Michalska"), ("Nowicki", "Nowicka"),
        ("Adamczyk", "Adamczyk"), ("Dudek", "Dudek"), ("Zając", "Zając"), ("Wieczorek", "Wieczorek"),
        ("Jabłoński", "Jabłońska"), ("Król", "Król"), ("Majewski", "Majewska"),
        ("Olszewski", "Olszewska"), ("Jaworski", "Jaworska"), ("Wróbel", "Wróbel"),
        ("Malinowski", "Malinowska"), ("Pawlak", "Pawlak"), ("Witkowski", "Witkowska"),
        ("Walczak", "Walczak"), ("Stępień", "Stępień"), ("Górski", "Górska"),
        ("Rutkowski", "Rutkowska"), ("Michalak", "Michalak")]
DOMAINS = ["gmail.com", "wp.pl", "onet.pl", "o2.pl", "interia.pl", "outlook.com"]
CITIES = [("Katowice", "40-"), ("Chorzów", "41-"), ("Sosnowiec", "41-"), ("Gliwice", "44-"),
          ("Mikołów", "43-"), ("Tychy", "43-"), ("Siemianowice Śląskie", "41-")]
STREETS = ["Mariacka", "Stawowa", "3 Maja", "Chorzowska", "Mikołowska", "Kościuszki", "Gliwicka",
           "Francuska", "Brynowska", "Ligonia", "Warszawska", "Sokolska"]
NOTES_POOL = ["Kontuzja kolana – unikać przysiadów ze sztangą.", "Woli kontakt mailowy.",
              "Karta zgubiona 03.2026, wydano duplikat.", "Zainteresowana treningiem personalnym.",
              "Płatność przelewem, faktura na firmę.", "Prosi o nieprzypisywanie do sali 2 (klimatyzacja).",
              "Stały klient od 2019.", "Reklamacja z 05.2026 rozpatrzona pozytywnie."]

# --- STORY: fakty używane przez zadania (pozycja = numer porządkowy klienta, 1..340) ---------
@dataclass(frozen=True)
class StoryClient:
    pos: int
    first: str
    last: str
    email: str
    gender: str
    note: str = ""


STORY = {
    "anna": StoryClient(42, "Anna", "Kowalska", "anna.kowalska@gmail.com", "K",
                        "Preferuje zajęcia wieczorne. Prosi o przypomnienia SMS."),
    "hanna": StoryClient(57, "Hanna", "Kowalska", "hanna.kowalska@wp.pl", "K"),
    "anna_kowalczyk": StoryClient(88, "Anna", "Kowalczyk", "anna.kowalczyk@onet.pl", "K"),
    "piotr": StoryClient(101, "Piotr", "Nowak", "piotr.nowak@gmail.com", "M"),
    "jan_target": StoryClient(117, "Jan", "Kamiński", "jan.kaminski82@gmail.com", "M"),
    "katarzyna": StoryClient(150, "Katarzyna", "Lewandowska", "k.lewandowska@interia.pl", "K"),
    "ewa": StoryClient(203, "Ewa", "Wójcik", "ewa.wojcik@o2.pl", "K"),
    "jan_decoy": StoryClient(233, "Jan", "Kamiński", "jan.kaminski@wp.pl", "M"),
}
RESERVED_NAMES = {(c.first, c.last) for c in STORY.values()}

EXPIRING_WINDOW = (date(2026, 11, 9), date(2026, 11, 16))
N_EXPIRING = 26

# Grafik tygodniowy: (dzień tygodnia 0=pon, godzina, typ, nazwa, minuty, sala, trener, limit, poziom)
WEEKLY = [
    (0, "07:00", "joga", "Joga", 60, "Sala 1", "Marta Sowa", 25, "wszystkie"),
    (0, "17:00", "pilates", "Pilates", 55, "Sala 2", "Ola Bielecka", 15, "wszystkie"),
    (0, "18:30", "crossfit", "Crossfit", 60, "Strefa CF", "Tomek Lis", 12, "średni"),
    (0, "19:30", "spinning", "Spinning", 45, "Sala rowerowa", "Kuba Rak", 20, "wszystkie"),
    (1, "07:00", "spinning", "Spinning", 45, "Sala rowerowa", "Kuba Rak", 20, "wszystkie"),
    (1, "18:00", "zumba", "Zumba", 60, "Sala 1", "Carla Mendes", 30, "wszystkie"),
    (1, "19:00", "pilates", "Pilates", 55, "Sala 2", "Ola Bielecka", 15, "wszystkie"),
    (2, "07:00", "joga", "Joga", 60, "Sala 1", "Marta Sowa", 25, "wszystkie"),
    (2, "18:00", "crossfit", "Crossfit", 60, "Strefa CF", "Tomek Lis", 12, "średni"),
    (2, "19:00", "pilates", "Pilates", 55, "Sala 2", "Ola Bielecka", 15, "wszystkie"),
    (3, "07:00", "joga", "Joga", 60, "Sala 1", "Marta Sowa", 25, "wszystkie"),
    (3, "18:00", "joga", "Joga", 60, "Sala 1", "Marta Sowa", 25, "wszystkie"),
    (3, "18:00", "spinning", "Spinning", 45, "Sala rowerowa", "Kuba Rak", 20, "wszystkie"),
    (3, "19:30", "joga", "Power Joga", 60, "Sala 1", "Igor Wilk", 25, "zaawansowany"),
    (4, "07:00", "pilates", "Pilates", 55, "Sala 2", "Ola Bielecka", 15, "wszystkie"),
    (4, "17:00", "crossfit", "Crossfit", 60, "Strefa CF", "Tomek Lis", 12, "średni"),
    (4, "18:30", "zumba", "Zumba", 60, "Sala 1", "Carla Mendes", 30, "wszystkie"),
    (5, "10:00", "spinning", "Spinning", 45, "Sala rowerowa", "Kuba Rak", 20, "wszystkie"),
    (5, "10:00", "joga", "Joga", 60, "Sala 1", "Marta Sowa", 25, "wszystkie"),
    (5, "11:30", "crossfit", "Crossfit", 60, "Strefa CF", "Tomek Lis", 12, "średni"),
    (6, "10:00", "joga", "Joga", 60, "Sala 1", "Marta Sowa", 25, "wszystkie"),
    (6, "11:00", "pilates", "Pilates", 55, "Sala 2", "Ola Bielecka", 15, "wszystkie"),
]
DESCRIPTIONS = {
    "joga": "Zajęcia jogi: oddech, mobilność, równowaga. Mata zapewniona przez klub.",
    "pilates": "Wzmocnienie mięśni głębokich i stabilizacja kręgosłupa.",
    "crossfit": "Trening funkcjonalny o wysokiej intensywności. Wymagane obuwie sportowe.",
    "spinning": "Jazda na rowerach stacjonarnych w rytm muzyki.",
    "zumba": "Taneczny trening cardio.",
}

# Liczba aktywnych zapisów ustalona dla wybranych zajęć: (data, godzina, nazwa) -> liczba.
FIXED_COUNTS = {
    (date(2026, 11, 12), "18:00", "Joga"): 23,       # czwartkowa joga: > 20 (paginacja)
    (date(2026, 11, 19), "18:00", "Joga"): 17,
    (date(2026, 11, 26), "18:00", "Joga"): 19,
    (date(2026, 12, 3), "18:00", "Joga"): 14,
    (date(2026, 11, 13), "17:00", "Crossfit"): 12,   # pełne
    (date(2026, 11, 14), "11:30", "Crossfit"): 6,
    (date(2026, 11, 14), "10:00", "Spinning"): 11,
    (date(2026, 11, 10), "19:00", "Pilates"): 9,     # zawiera Piotra Nowaka
    (date(2026, 11, 11), "19:00", "Pilates"): 8,
}
FIXED_CANCELLED = {(date(2026, 11, 12), "18:00", "Joga"): 2}

# Rezerwacje klientów „fabularnych”: klucz -> lista (data, godzina, nazwa).
STORY_BOOKINGS = {
    "anna": [(date(2026, 11, 15), "10:00", "Joga"), (date(2026, 11, 16), "07:00", "Joga")],
    "hanna": [(date(2026, 11, 12), "18:00", "Joga")],
    "piotr": [(date(2026, 11, 10), "19:00", "Pilates"), (date(2026, 11, 13), "07:00", "Pilates")],
    "katarzyna": [(date(2026, 11, 11), "18:00", "Crossfit")],
    "jan_decoy": [(date(2026, 11, 14), "11:30", "Crossfit")],
}


def strip_accents(text: str) -> str:
    text = text.replace("ł", "l").replace("Ł", "L")
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def slug(text: str) -> str:
    return strip_accents(text).lower().replace(" ", "_").replace("-", "_")


class Gen:
    def __init__(self, seed: int = SEED):
        self.rng = random.Random(seed)

    def uuid(self) -> str:
        return str(uuid.UUID(int=self.rng.getrandbits(128), version=4))

    def ts(self, start: datetime, end: datetime) -> str:
        delta = int((end - start).total_seconds())
        t = start + timedelta(seconds=self.rng.randint(0, delta))
        return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    def day(self, start: date, end: date) -> date:
        return start + timedelta(days=self.rng.randint(0, (end - start).days))


def _client_row(g: Gen, pos: int, first: str, last: str, email: str, gender: str, note: str,
                emails_taken: set[str]) -> dict:
    r = g.rng
    city, postal_prefix = r.choice(CITIES)
    created = g.ts(datetime(2018, 1, 1, tzinfo=TZ), datetime(2026, 9, 30, tzinfo=TZ))
    row = {
        "id": g.uuid(), "first_name": first, "last_name": last, "email": email,
        "phone": f"+48 {r.randint(500, 799)} {r.randint(100, 999)} {r.randint(100, 999)}",
        "birth_date": g.day(date(1958, 1, 1), date(2006, 12, 31)).isoformat(),
        "gender": gender, "street": r.choice(STREETS), "house_number": str(r.randint(1, 120)),
        "city": city, "postal_code": f"{postal_prefix}{r.randint(100, 999)}", "country": "PL",
        "preferred_language": r.choice(["pl", "pl", "pl", "en"]), "preferred_club": "Klub Fit Katowice Centrum",
        "home_club_id": "c1a2b3c4-0000-4000-8000-000000000001", "notes": note,
        "marketing_consent": r.choice(["true", "false"]), "sms_consent": r.choice(["true", "false"]),
        "email_consent": "true", "photo_consent": r.choice(["true", "false", ""]),
        "gdpr_consent_at": created, "gdpr_consent_version": r.choice(["2018-05", "2021-01", "2024-03"]),
        "terms_version": r.choice(["v3", "v4", "v4.1"]),
        "emergency_contact_name": f"{r.choice(FEMALE + MALE)} {r.choice(LAST)[r.randint(0, 1)]}",
        "emergency_contact_phone": f"+48 {r.randint(500, 799)} {r.randint(100, 999)} {r.randint(100, 999)}",
        "company_name": r.choice(["", "", "", "Silesia Soft Sp. z o.o.", "Huta Studio s.c."]),
        "nip": "" if r.random() < 0.8 else str(r.randint(6000000000, 6499999999)),
        "invoice_email": "", "payment_method": r.choice(["karta", "przelew", "gotówka", "Benefit"]),
        "iban_masked": f"PL** **** **** **** **** {r.randint(1000, 9999)}",
        "debt_pln": "0.00" if r.random() < 0.9 else f"{r.randint(20, 300)}.00",
        "ltv_pln": f"{r.randint(150, 9000)}.00", "loyalty_points": str(r.randint(0, 4000)),
        "loyalty_tier": r.choice(["brąz", "srebro", "złoto"]),
        "referral_code": f"FIT{r.randint(10000, 99999)}", "referred_by": "",
        "source_channel": r.choice(["recepcja", "www", "aplikacja", "polecenie", "Benefit"]),
        "utm_source": r.choice(["", "facebook", "google", "instagram"]),
        "utm_campaign": r.choice(["", "jesien2025", "nowy_rok_2026", "lato2026"]),
        "segment": r.choice(["A", "B", "C"]), "churn_score": f"{r.random():.3f}",
        "card_number": f"KF{r.randint(10000000, 99999999)}", "card_issued_at": created[:10],
        "rfid_tag": f"{r.getrandbits(40):010x}", "locker_number": str(r.randint(1, 240)) if r.random() < 0.3 else "",
        "medical_clearance_until": g.day(date(2026, 1, 1), date(2027, 12, 31)).isoformat() if r.random() < 0.4 else "",
        "height_cm": str(r.randint(150, 200)), "weight_kg": str(r.randint(48, 110)),
        "training_goal": r.choice(["redukcja", "siła", "kondycja", "rehabilitacja", "relaks"]),
        "assigned_trainer_id": g.uuid() if r.random() < 0.2 else "",
        "app_installed": r.choice(["true", "false"]), "push_token": f"{r.getrandbits(64):016x}" if r.random() < 0.5 else "",
        "last_login_at": g.ts(datetime(2026, 6, 1, tzinfo=TZ), NOW_LOCAL),
        "last_visit_at": g.ts(datetime(2026, 8, 1, tzinfo=TZ), NOW_LOCAL),
        "visits_total": str(r.randint(1, 600)), "newsletter_frequency": r.choice(["tygodniowo", "miesięcznie", "nigdy"]),
        "timezone": "Europe/Warsaw", "locale": "pl_PL", "avatar_url": "",
        "blocked": "false", "blocked_reason": "", "is_test_account": "false",
        "created_at": created, "created_by": r.choice(["recepcja.k1", "import", "www", "admin"]),
        "updated_at": g.ts(datetime(2026, 1, 1, tzinfo=TZ), NOW_LOCAL),
        "updated_by": r.choice(["recepcja.k1", "recepcja.k2", "system", "sync-crm"]),
        "deleted_at": "", "version": str(r.randint(1, 40)),
        "row_checksum": hashlib.md5(f"{pos}-{email}".encode()).hexdigest(),
        "sync_hash": f"{r.getrandbits(64):016x}", "crm_sync_status": r.choice(["ok", "ok", "pending", "error"]),
        "crm_external_id": g.uuid(), "erp_customer_no": f"ERP-{r.randint(100000, 999999)}",
        "legacy_id": str(10000 + pos), "legacy_system": r.choice(["FitManager 2.3", "Excel-import"]),
        "legacy_import_batch": r.choice(["2019-02-11", "2021-07-01"]),
        "legacy_club_code": "KTW01", "legacy_status_flag": r.choice(["A", "A", "Z", "P"]),
        "migration_note": r.choice(["", "", "brak zgody marketingowej w starym systemie", "zduplikowany rekord scalony"]),
        "audit_ip_created": f"10.{r.randint(0, 255)}.{r.randint(0, 255)}.{r.randint(1, 254)}",
    }
    assert set(row) == set(CLIENT_COLUMNS)
    emails_taken.add(email)
    return row


def _random_person(g: Gen, used_names: set[tuple[str, str]], emails_taken: set[str]):
    r = g.rng
    while True:
        gender = r.choice(["K", "M"])
        first = r.choice(FEMALE if gender == "K" else MALE)
        last = r.choice(LAST)[0 if gender == "M" else 1]
        if (first, last) in RESERVED_NAMES or (first, last) in used_names:
            continue
        used_names.add((first, last))
        base = f"{slug(first)}.{slug(last)}"
        email = f"{base}@{r.choice(DOMAINS)}"
        n = 1
        while email in emails_taken:
            n += 1
            email = f"{base}{r.randint(1, 99)}@{r.choice(DOMAINS)}"
        return first, last, email, gender


def class_start_utc(day: date, hhmm: str) -> str:
    h, m = map(int, hhmm.split(":"))
    local = datetime.combine(day, time(h, m), tzinfo=TZ)
    return local.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_seed_db(path: Path = SEED_DB) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    g = Gen()
    r = g.rng
    conn = connect(path)
    create_schema(conn)

    # --- klienci ---
    story_by_pos = {c.pos: (key, c) for key, c in STORY.items()}
    used_names: set[tuple[str, str]] = set()
    emails_taken: set[str] = {c.email for c in STORY.values()}
    clients: list[dict] = []
    story_ids: dict[str, str] = {}
    for pos in range(1, N_CLIENTS + 1):
        if pos in story_by_pos:
            key, c = story_by_pos[pos]
            row = _client_row(g, pos, c.first, c.last, c.email, c.gender, c.note, emails_taken)
            story_ids[key] = row["id"]
        else:
            first, last, email, gender = _random_person(g, used_names, emails_taken)
            note = r.choice(NOTES_POOL) if r.random() < 0.15 else ""
            row = _client_row(g, pos, first, last, email, gender, note, emails_taken)
        clients.append(row)
    for row in clients:
        if r.random() < 0.1:
            row["referred_by"] = r.choice(clients)["id"]
    cols = ", ".join(CLIENT_COLUMNS)
    marks = ", ".join("?" for _ in CLIENT_COLUMNS)
    conn.executemany(f"INSERT INTO clients ({cols}) VALUES ({marks})",
                     [[row[c] for c in CLIENT_COLUMNS] for row in clients])

    # --- karnety ---
    plans = [("Open", 189.0), ("Open Plus", 239.0), ("8 wejść", 149.0), ("Student", 129.0),
             ("Senior", 119.0), ("Poranny", 109.0)]
    story_set = set(story_ids.values())
    non_story = [c["id"] for c in clients if c["id"] not in story_set]
    expiring = set(r.sample(non_story, N_EXPIRING))
    rest = [cid for cid in non_story if cid not in expiring]
    near_miss = set(r.sample(rest, 6))            # wygasają 17–20.11 (tuż poza oknem)
    rest = [cid for cid in rest if cid not in near_miss]
    just_expired = set(r.sample(rest, 8))         # wygasły 1–8.11
    memberships = []

    def add_membership(cid, plan, price, vfrom, vto, status):
        memberships.append((g.uuid(), cid, plan, vfrom.isoformat(), vto.isoformat(), status,
                            8 if plan == "8 wejść" else None, price, int(r.random() < 0.4),
                            g.ts(datetime(2025, 1, 1, tzinfo=TZ), NOW_LOCAL), g.ts(datetime(2026, 1, 1, tzinfo=TZ), NOW_LOCAL),
                            f"UM/{r.randint(1000, 9999)}/{vfrom.year}"))

    for c in clients:
        cid = c["id"]
        plan, price = r.choice(plans)
        if r.random() < 0.3:  # historia: stary, wygasły karnet
            add_membership(cid, plan, price, date(2025, 1, 1), date(2025, 6, 30), "expired")
        if cid in story_set:
            add_membership(cid, "Open", 189.0, date(2026, 10, 1), date(2027, 3, 31), "active")
        elif cid in expiring:
            vto = g.day(*EXPIRING_WINDOW)
            add_membership(cid, plan, price, vto - timedelta(days=r.choice([30, 90, 180])), vto, "active")
        elif cid in near_miss:
            vto = g.day(date(2026, 11, 17), date(2026, 11, 20))
            add_membership(cid, plan, price, vto - timedelta(days=90), vto, "active")
        elif cid in just_expired:
            vto = g.day(date(2026, 11, 1), date(2026, 11, 8))
            add_membership(cid, plan, price, vto - timedelta(days=90), vto, "expired")
        else:
            x = r.random()
            if x < 0.80:
                vto = g.day(date(2026, 11, 21), date(2027, 10, 31))
                add_membership(cid, plan, price, g.day(date(2025, 11, 1), date(2026, 11, 1)), vto, "active")
            elif x < 0.93:
                vto = g.day(date(2026, 3, 1), date(2026, 10, 31))
                add_membership(cid, plan, price, vto - timedelta(days=180), vto, "expired")
            else:
                vto = g.day(date(2026, 12, 1), date(2027, 6, 30))
                add_membership(cid, plan, price, date(2026, 6, 1), vto, "frozen")
    conn.executemany("INSERT INTO memberships VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", memberships)

    # --- zajęcia ---
    classes = []  # dict: id, day, hhmm, name, type, cap, start_utc, end_utc
    for week in range(SCHEDULE_WEEKS):
        for wd, hhmm, ctype, name, dur, room, trainer, cap, level in WEEKLY:
            day = SCHEDULE_START + timedelta(days=7 * week + wd)
            start = class_start_utc(day, hhmm)
            cid = g.uuid()
            classes.append({"id": cid, "day": day, "hhmm": hhmm, "name": name, "type": ctype, "cap": cap,
                            "start": datetime.fromisoformat(start.replace("Z", "+00:00")), "dur": dur})
            conn.execute("INSERT INTO classes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         (cid, ctype, name, start, dur, room, trainer, cap, level, "scheduled",
                          DESCRIPTIONS[ctype], "2026-10-15T09:00:00Z", "2026-10-20T12:00:00Z",
                          f"GR-{ctype[:3].upper()}-{day.strftime('%m%d')}-{hhmm.replace(':', '')}"))
    by_key = {(c["day"], c["hhmm"], c["name"]): c for c in classes}

    # --- rezerwacje ---
    valid_on: dict[str, list[tuple[date, date]]] = {}
    for m in memberships:
        if m[5] == "active":
            valid_on.setdefault(m[1], []).append((date.fromisoformat(m[3]), date.fromisoformat(m[4])))
    busy: dict[str, list[tuple[datetime, datetime]]] = {}
    seq = 0
    rows = []

    def overlaps(cid, cls):
        s, e = cls["start"], cls["start"] + timedelta(minutes=cls["dur"])
        return any(s < be and bs < e for bs, be in busy.get(cid, []))

    def book(client_id, cls, status="active"):
        nonlocal seq
        seq += 1
        created = g.ts(datetime(2026, 10, 20, tzinfo=TZ), NOW_LOCAL)
        cancelled = g.ts(datetime(2026, 11, 1, tzinfo=TZ), NOW_LOCAL) if status == "cancelled" else None
        rows.append((g.uuid(), client_id, cls["id"], status, r.choice(["aplikacja", "recepcja", "www"]),
                     created, cancelled, r.choice(["app", "recepcja.k1", "recepcja.k2"]), seq))
        if status == "active":
            busy.setdefault(client_id, []).append((cls["start"], cls["start"] + timedelta(minutes=cls["dur"])))

    for key, items in STORY_BOOKINGS.items():
        for k in items:
            book(story_ids[key], by_key[k])

    for cls in classes:
        key = (cls["day"], cls["hhmm"], cls["name"])
        already = sum(1 for row in rows if row[2] == cls["id"] and row[3] == "active")
        target = FIXED_COUNTS.get(key)
        if target is None:
            target = min(cls["cap"] - 2, round(cls["cap"] * r.uniform(0.3, 0.85)))
        pool = [cid for cid in non_story
                if any(a <= cls["day"] <= b for a, b in valid_on.get(cid, []))]
        r.shuffle(pool)
        taken = {row[1] for row in rows if row[2] == cls["id"]}
        for cid in pool:
            if already >= target:
                break
            if cid in taken or overlaps(cid, cls):
                continue
            book(cid, cls)
            taken.add(cid)
            already += 1
        assert already == target, (key, already, target)
        n_cancel = FIXED_CANCELLED.get(key, 1 if r.random() < 0.5 else 0)
        for cid in pool:
            if n_cancel == 0:
                break
            if cid not in taken:
                book(cid, cls, status="cancelled")
                taken.add(cid)
                n_cancel -= 1
    conn.executemany("INSERT INTO bookings VALUES (?,?,?,?,?,?,?,?,?)", rows)
    conn.close()
    return path


def fingerprint(path: Path) -> str:
    """Skrót zawartości wszystkich tabel (do sprawdzania determinizmu i resetu)."""
    conn = connect(path)
    h = hashlib.sha256()
    for table in ("clients", "memberships", "classes", "bookings", "aux_actions"):
        for row in conn.execute(f"SELECT * FROM {table} ORDER BY 1"):
            h.update(repr(tuple(row)).encode())
    conn.close()
    return h.hexdigest()


if __name__ == "__main__":
    p = build_seed_db()
    print(f"seed: {p} fingerprint={fingerprint(p)[:16]}")

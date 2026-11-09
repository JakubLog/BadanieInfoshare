"""55 dodatkowych, realistycznych narzędzi z innych modułów klubu (CRM, faktury, korty, trenerzy…).

Używane w eksperymencie z liczbą narzędzi (20 = 5 bazowych + pierwsze 15, 60 = 5 + 55).
Pierwsze 15 to narzędzia o nazwach celowo nakładających się z domeną rezerwacji zajęć
(search_customers, find_client, create_reservation, book_session, register_for_event…).
Żadne z nich nie tworzy rezerwacji zajęć: akcje zapisujące trafiają do tabeli aux_actions.
"""

from __future__ import annotations

import json
from typing import Callable

from klubfit.domain import services as svc
from klubfit.domain.errors import DomainError
from klubfit.mcp.tools import McpState, ToolSpec, _obj, _s


def _search(projection: Callable[[dict], dict]):
    def handler(state: McpState, args: dict) -> dict:
        q = svc.require(args.get("query"), "query", "fragment imienia, nazwiska lub e-maila", "Kowalska")
        rows = svc.search_clients(state.conn, q=str(q))
        return {"total": len(rows), "results": [projection(c) for c in rows[:20]]}
    return handler


def _by_client(build: Callable[[dict], dict]):
    def handler(state: McpState, args: dict) -> dict:
        cid = svc.ensure_uuid(args.get("client_id") or args.get("customer_id"), "client_id")
        return build(svc.get_client(state.conn, cid))
    return handler


def _static(payload: Callable[[dict], dict]):
    def handler(state: McpState, args: dict) -> dict:
        return payload(args)
    return handler


def _write(prefix: str, message: str):
    def handler(state: McpState, args: dict) -> dict:
        n = svc.log_aux_action(state.conn, prefix, json.dumps(args, ensure_ascii=False, sort_keys=True))
        return {"status": "ok", "id": f"{prefix}_{n:05d}", "message": message}
    return handler


def _not_found(what: str, key: str):
    def handler(state: McpState, args: dict) -> dict:
        raise DomainError("NOT_FOUND", f"Nie znaleziono: {what} '{args.get(key)}'.", 404, field=key)
    return handler


CRM = lambda c: {"customer_id": c["crm_external_id"], "name": f"{c['first_name']} {c['last_name']}",  # noqa: E731
                 "email": c["email"], "segment": c["segment"], "marketing_consent": c["marketing_consent"]}
INVOICE_PARTY = lambda c: {"erp_customer_no": c["erp_customer_no"], "name": f"{c['first_name']} {c['last_name']}",  # noqa: E731
                           "company": c["company_name"] or None, "nip": c["nip"] or None, "email": c["email"]}
ACCESS = lambda c: {"member": f"{c['first_name']} {c['last_name']}", "card_number": c["card_number"],  # noqa: E731
                    "rfid_tag": c["rfid_tag"], "blocked": c["blocked"] == "true"}
SUBSCRIBER = lambda c: {"email": c["email"], "frequency": c["newsletter_frequency"]}  # noqa: E731

TRAINERS = ["Marta Sowa", "Ola Bielecka", "Tomek Lis", "Kuba Rak", "Carla Mendes", "Igor Wilk"]
ROOMS = ["Sala 1", "Sala 2", "Sala rowerowa", "Strefa CF", "Sala konferencyjna"]
Q = {"query": _s("Fragment imienia, nazwiska lub e-maila.")}
CID = {"client_id": _s("Identyfikator klienta (UUID).")}
DATE = {"date": _s("Data.")}


def T(ns: str, name: str, short: str, props: dict, required: list[str], handler) -> ToolSpec:
    return ToolSpec(name, short, short, _obj(props, required), handler, namespace=ns, group="extra")


EXTRA_TOOLS: list[ToolSpec] = [
    # --- 15 narzędzi o nazwach nakładających się z rezerwacją zajęć (wariant 20) ---
    T("crm", "search_customers", "Wyszukuje kontakty w CRM marketingowym.", Q, ["query"], _search(CRM)),
    T("faktury", "find_client", "Wyszukuje kontrahenta w systemie faktur.", Q, ["query"], _search(INVOICE_PARTY)),
    T("korty", "create_reservation", "Tworzy rezerwację kortu do squasha.",
      {"court": _s("Numer kortu."), **DATE, "time": _s("Godzina."), **CID}, ["court", "date", "time", "client_id"],
      _write("kort", "Zarezerwowano kort.")),
    T("trenerzy", "book_session", "Umawia sesję treningu personalnego z trenerem.",
      {"trainer": _s("Imię i nazwisko trenera."), **CID, **DATE, "time": _s("Godzina.")},
      ["trainer", "client_id", "date", "time"], _write("pt", "Umówiono trening personalny.")),
    T("wydarzenia", "list_events", "Zwraca wydarzenia klubowe w danym dniu.", DATE, ["date"],
      _static(lambda a: {"date": a.get("date"), "events": [
          {"event_id": "ev_0412", "name": "Warsztaty oddechowe", "time": "17:00"},
          {"event_id": "ev_0413", "name": "Konsultacje dietetyczne", "time": "16:00"}]})),
    T("korty", "check_availability", "Sprawdza dostępność kortów do squasha.", DATE, ["date"],
      _static(lambda a: {"date": a.get("date"), "free_courts": [{"court": "1", "times": ["16:00", "20:00"]},
                                                                 {"court": "2", "times": ["18:00"]}]})),
    T("crm", "get_customer", "Zwraca profil marketingowy kontaktu z CRM.", {"customer_id": _s("Identyfikator kontaktu.")},
      ["customer_id"], _by_client(CRM)),
    T("trenerzy", "get_schedule", "Zwraca grafik trenera personalnego.", {"trainer": _s("Imię i nazwisko."), **DATE},
      ["trainer", "date"], _static(lambda a: {"trainer": a.get("trainer"), "date": a.get("date"),
                                             "free_slots": ["09:00", "13:00", "15:00"]})),
    T("sale", "book_room", "Rezerwuje salę na wydarzenie wewnętrzne.",
      {"room": _s("Nazwa sali."), **DATE, "time": _s("Godzina.")}, ["room", "date", "time"],
      _write("sala", "Zarezerwowano salę.")),
    T("dostep", "lookup_member", "Wyszukuje członka w systemie kontroli dostępu.", Q, ["query"], _search(ACCESS)),
    T("korty", "cancel_reservation", "Anuluje rezerwację kortu.", {"reservation_id": _s("Identyfikator rezerwacji kortu.")},
      ["reservation_id"], _not_found("rezerwacja kortu", "reservation_id")),
    T("lojalnosc", "get_points", "Zwraca saldo punktów lojalnościowych klienta.", CID, ["client_id"],
      _by_client(lambda c: {"points": int(c["loyalty_points"]), "tier": c["loyalty_tier"]})),
    T("newsletter", "subscribe", "Zapisuje adres e-mail do newslettera.", {"email": _s("Adres e-mail.")}, ["email"],
      _write("nl", "Zapisano do newslettera.")),
    T("trenerzy", "list_trainers", "Zwraca listę trenerów personalnych.", {}, [],
      _static(lambda a: {"trainers": TRAINERS})),
    T("wydarzenia", "register_for_event", "Zapisuje uczestnika na wydarzenie klubowe.",
      {"event_id": _s("Identyfikator wydarzenia."), **CID}, ["event_id", "client_id"],
      _write("evreg", "Zapisano na wydarzenie.")),
    # --- pozostałe 40 (wariant 60) ---
    T("newsletter", "search_subscribers", "Wyszukuje subskrybentów newslettera.", Q, ["query"], _search(SUBSCRIBER)),
    T("newsletter", "unsubscribe", "Wypisuje adres e-mail z newslettera.", {"email": _s("Adres e-mail.")}, ["email"],
      _write("nlu", "Wypisano z newslettera.")),
    T("newsletter", "send_campaign", "Wysyła kampanię e-mailową.", {"campaign_id": _s("Identyfikator kampanii.")},
      ["campaign_id"], _write("camp", "Kampania zakolejkowana.")),
    T("newsletter", "list_campaigns", "Zwraca listę kampanii e-mailowych.", {}, [],
      _static(lambda a: {"campaigns": [{"campaign_id": "cmp_31", "name": "Black Friday"},
                                       {"campaign_id": "cmp_32", "name": "Zimowe karnety"}]})),
    T("faktury", "issue_invoice", "Wystawia fakturę dla klienta.",
      {**CID, "amount_pln": {"type": "number"}, "description": _s("Opis pozycji.")}, ["client_id", "amount_pln"],
      _write("fv", "Wystawiono fakturę.")),
    T("faktury", "list_invoices", "Zwraca faktury klienta.", CID, ["client_id"],
      _by_client(lambda c: {"erp_customer_no": c["erp_customer_no"], "invoices": []})),
    T("faktury", "get_invoice", "Zwraca fakturę.", {"invoice_id": _s("Numer faktury.")}, ["invoice_id"],
      _not_found("faktura", "invoice_id")),
    T("faktury", "correct_invoice", "Wystawia korektę faktury.", {"invoice_id": _s("Numer faktury."), "reason": _s("Powód.")},
      ["invoice_id", "reason"], _not_found("faktura", "invoice_id")),
    T("platnosci", "charge_card", "Obciąża zapisaną kartę klienta.", {**CID, "amount_pln": {"type": "number"}},
      ["client_id", "amount_pln"], _write("pay", "Płatność przyjęta.")),
    T("platnosci", "refund_payment", "Zwraca płatność.", {"payment_id": _s("Identyfikator płatności.")}, ["payment_id"],
      _not_found("płatność", "payment_id")),
    T("platnosci", "list_payments", "Zwraca historię płatności klienta.", CID, ["client_id"],
      _by_client(lambda c: {"payment_method": c["payment_method"], "payments": []})),
    T("sklep", "list_products", "Zwraca produkty sklepu klubowego.", {}, [],
      _static(lambda a: {"products": [{"product_id": "p_101", "name": "Woda 0,5 l", "price_pln": 4},
                                      {"product_id": "p_102", "name": "Baton proteinowy", "price_pln": 9},
                                      {"product_id": "p_103", "name": "Ręcznik", "price_pln": 39}]})),
    T("sklep", "create_order", "Tworzy zamówienie w sklepie klubowym.",
      {**CID, "product_id": _s("Identyfikator produktu."), "quantity": {"type": "integer"}},
      ["client_id", "product_id"], _write("ord", "Utworzono zamówienie.")),
    T("sklep", "get_order", "Zwraca zamówienie ze sklepu.", {"order_id": _s("Identyfikator zamówienia.")}, ["order_id"],
      _not_found("zamówienie", "order_id")),
    T("szafki", "assign_locker", "Przypisuje klientowi szafkę na sezon.", {**CID, "locker_number": _s("Numer szafki.")},
      ["client_id", "locker_number"], _write("lock", "Przypisano szafkę.")),
    T("szafki", "release_locker", "Zwalnia szafkę.", {"locker_number": _s("Numer szafki.")}, ["locker_number"],
      _write("lockrel", "Zwolniono szafkę.")),
    T("szafki", "list_free_lockers", "Zwraca wolne szafki.", {}, [],
      _static(lambda a: {"free": ["12", "47", "88", "131", "202"]})),
    T("dostep", "issue_card", "Wydaje nową kartę wejściową.", CID, ["client_id"], _write("card", "Wydano kartę.")),
    T("dostep", "block_card", "Blokuje kartę wejściową.", {"card_number": _s("Numer karty."), "reason": _s("Powód.")},
      ["card_number"], _write("cardblk", "Zablokowano kartę.")),
    T("dostep", "list_entries", "Zwraca wejścia przez bramki w danym dniu.", DATE, ["date"],
      _static(lambda a: {"date": a.get("date"), "entries": 0, "note": "Brak danych dla przyszłych dni."})),
    T("trenerzy", "cancel_session", "Odwołuje trening personalny.", {"session_id": _s("Identyfikator sesji.")},
      ["session_id"], _not_found("sesja", "session_id")),
    T("trenerzy", "list_sessions", "Zwraca treningi personalne klienta.", CID, ["client_id"],
      _by_client(lambda c: {"sessions": []})),
    T("sale", "list_rooms", "Zwraca listę sal.", {}, [], _static(lambda a: {"rooms": ROOMS})),
    T("sale", "get_room_availability", "Zwraca dostępność sali w danym dniu.", {"room": _s("Nazwa sali."), **DATE},
      ["room", "date"], _static(lambda a: {"room": a.get("room"), "date": a.get("date"), "free": ["13:00-15:00"]})),
    T("sale", "cancel_room_booking", "Anuluje rezerwację sali.", {"room_booking_id": _s("Identyfikator rezerwacji sali.")},
      ["room_booking_id"], _not_found("rezerwacja sali", "room_booking_id")),
    T("wydarzenia", "get_event", "Zwraca szczegóły wydarzenia klubowego.", {"event_id": _s("Identyfikator wydarzenia.")},
      ["event_id"], _static(lambda a: {"event_id": a.get("event_id"), "name": "Warsztaty oddechowe", "capacity": 15})),
    T("wydarzenia", "cancel_event_registration", "Anuluje zapis na wydarzenie.",
      {"registration_id": _s("Identyfikator zapisu.")}, ["registration_id"], _not_found("zapis", "registration_id")),
    T("lojalnosc", "add_points", "Dodaje punkty lojalnościowe.",
      {**CID, "points": {"type": "integer"}, "reason": _s("Powód.")}, ["client_id", "points"],
      _write("pts", "Dodano punkty.")),
    T("lojalnosc", "redeem_reward", "Wymienia punkty na nagrodę.", {**CID, "reward_id": _s("Identyfikator nagrody.")},
      ["client_id", "reward_id"], _write("rwd", "Wymieniono nagrodę.")),
    T("lojalnosc", "list_rewards", "Zwraca katalog nagród.", {}, [],
      _static(lambda a: {"rewards": [{"reward_id": "r_1", "name": "Wejście gratis", "points": 500}]})),
    T("raporty", "attendance_report", "Zwraca raport frekwencji.", {"date_from": _s("Od."), "date_to": _s("Do.")},
      ["date_from", "date_to"], _static(lambda a: {"status": "zakolejkowano", "report_id": "rep_77"})),
    T("raporty", "revenue_report", "Zwraca raport przychodów.", {"month": _s("Miesiąc RRRR-MM.")}, ["month"],
      _static(lambda a: {"status": "zakolejkowano", "report_id": "rep_78"})),
    T("raporty", "churn_report", "Zwraca raport odejść klientów.", {}, [],
      _static(lambda a: {"status": "zakolejkowano", "report_id": "rep_79"})),
    T("crm", "update_customer", "Aktualizuje pole kontaktu w CRM.",
      {"customer_id": _s("Identyfikator kontaktu."), "field": _s("Pole."), "value": _s("Wartość.")},
      ["customer_id", "field", "value"], _write("crmupd", "Zaktualizowano kontakt.")),
    T("crm", "add_customer_note", "Dodaje notatkę do kontaktu w CRM.",
      {"customer_id": _s("Identyfikator kontaktu."), "note": _s("Treść.")}, ["customer_id", "note"],
      _write("crmnote", "Dodano notatkę.")),
    T("crm", "list_segments", "Zwraca segmenty marketingowe.", {}, [],
      _static(lambda a: {"segments": ["A", "B", "C"]})),
    T("kadry", "list_staff", "Zwraca listę pracowników klubu.", {}, [],
      _static(lambda a: {"staff": TRAINERS + ["Recepcja K1", "Recepcja K2"]})),
    T("kadry", "get_shift_schedule", "Zwraca grafik zmian pracowników.", DATE, ["date"],
      _static(lambda a: {"date": a.get("date"), "shifts": [{"who": "Recepcja K1", "from": "06:00", "to": "14:00"}]})),
    T("serwis", "report_equipment_issue", "Zgłasza usterkę sprzętu.",
      {"equipment": _s("Sprzęt."), "description": _s("Opis.")}, ["equipment", "description"],
      _write("svc", "Zgłoszono usterkę.")),
    T("serwis", "list_equipment_issues", "Zwraca otwarte zgłoszenia usterek.", {}, [],
      _static(lambda a: {"issues": [{"id": "svc_00007", "equipment": "Rower 12", "status": "otwarte"}]})),
]
assert len(EXTRA_TOOLS) == 55, len(EXTRA_TOOLS)
assert len({t.name for t in EXTRA_TOOLS}) == 55

"""Skrócona dokumentacja REST API przekazywana agentowi w prompcie systemowym.

Dokumentacja jest identyczna we wszystkich wariantach z wyjątkiem opisu mechanizmu,
który dany wariant faktycznie udostępnia (projekcja pól / format zwięzły / metadane paginacji).
"""

from klubfit.flags import RestFlags


def build_reference(flags: RestFlags) -> str:
    lines = [
        "# Klub Fit REST API",
        "Bazowy adres: http://klubfit.local. Odpowiedzi w JSON.",
        "",
        "## Endpointy",
        "- GET /clients — wyszukiwanie klientów. Parametry: q (fragment imienia, nazwiska lub e-maila), email (dokładny e-mail).",
        "- GET /clients/{client_id} — dane klienta.",
        "- GET /clients/{client_id}/memberships — karnety klienta.",
        "- GET /clients/{client_id}/bookings — rezerwacje klienta. Parametr: status (active | cancelled | all, domyślnie active).",
        "- GET /classes — grafik zajęć. Parametry: date, date_from, date_to, type (joga | pilates | crossfit | spinning | zumba).",
        "- GET /classes/{class_id} — szczegóły zajęć.",
        "- GET /classes/{class_id}/bookings — rezerwacje na zajęcia. Parametr: status (active | cancelled | all, domyślnie active).",
        "- POST /bookings — utworzenie rezerwacji. Treść: {\"client_id\": ..., \"class_id\": ...}.",
        "- GET /bookings/{booking_id} — szczegóły rezerwacji.",
        "- DELETE /bookings/{booking_id} — anulowanie rezerwacji.",
        "- GET /memberships — karnety. Parametry: status (active | expired | frozen), expires_from, expires_to.",
        "",
        "## Listy",
        "Endpointy zwracające listy przyjmują parametry offset i limit (maks. 20).",
    ]
    if flags.pagination == "meta":
        lines.append("Odpowiedź listy ma postać {items, total, returned, next_cursor, note}; "
                     "kolejną stronę pobierzesz parametrem cursor.")
    if flags.shape == "fields":
        lines += ["", "## Projekcja pól",
                  "Każdy endpoint GET przyjmuje parametr fields=pole1,pole2,..., który ogranicza odpowiedź "
                  "do wskazanych pól (np. fields=id,first_name,last_name,email)."]
    if flags.shape == "concise":
        lines += ["", "## Format odpowiedzi",
                  "Każdy endpoint przyjmuje parametr response_format=concise | detailed (domyślnie detailed). "
                  "concise zwraca tylko najważniejsze pola w czytelnej postaci."]
    return "\n".join(lines)

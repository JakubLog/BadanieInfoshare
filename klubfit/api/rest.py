"""REST API z wariantami przełączanymi flagami (`RestFlags`).

Fabryka `create_rest_app(db_path, flags)` tworzy osobną aplikację dla każdego przebiegu,
podpiętą pod świeżą kopię bazy z seeda.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from klubfit.api import serialize as ser
from klubfit.bridge import KIND_EXAMPLE, IdBridge
from klubfit.db import connect
from klubfit.domain import services as svc
from klubfit.domain.errors import DomainError
from klubfit.flags import RestFlags

PAGE_SIZE = 20
ID_FIELDS = {
    "client": {"id": "client", "referred_by": "client"},
    "class": {"id": "class"},
    "booking": {"id": "booking", "client_id": "client", "class_id": "class"},
    "membership": {"id": "membership", "client_id": "client"},
}


class Api:
    def __init__(self, db_path: str | Path, flags: RestFlags):
        self.conn = connect(db_path)
        self.flags = flags
        self.bridge = IdBridge(self.conn) if flags.ids == "readable" else None

    # --- identyfikatory ---
    def to_internal(self, kind: str, value: str | None, field: str) -> str:
        if value in (None, ""):
            raise DomainError("MISSING_FIELD", f"Brak wymaganego pola '{field}'.", 422, field=field,
                              expected="identyfikator", example=self.id_example(kind))
        # [variant:ids=readable]
        if self.bridge is not None:
            return self.bridge.internal(kind, value, field)
        # [/variant]
        return svc.ensure_uuid(value, field)

    def id_example(self, kind: str) -> str:
        return KIND_EXAMPLE[kind] if self.bridge else svc.EXAMPLE_UUID

    def publicize(self, kind: str, obj: dict) -> dict:
        # [variant:ids=readable]
        if self.bridge is None:
            return obj
        for key, k in ID_FIELDS[kind].items():
            if key in obj and obj[key]:
                obj[key] = self.bridge.public(k, obj[key])
        if isinstance(obj.get("client"), dict) and "id" in obj["client"]:
            obj["client"]["id"] = self.bridge.public("client", obj["client"]["id"])
        # [/variant]
        return obj

    # --- kształt odpowiedzi ---
    def render(self, kind: str, row: dict, params: dict) -> dict:
        # [variant:shape=concise]
        if self.flags.shape == "concise":
            fmt = params.get("response_format", "detailed")
            if fmt not in ("concise", "detailed"):
                raise DomainError("INVALID_PARAMETER", "Parametr 'response_format' przyjmuje wartości concise|detailed.",
                                  422, field="response_format", expected="concise | detailed", example="concise")
            if fmt == "concise":
                return self.publicize(kind, ser.CONCISE[kind](row))
        # [/variant]
        obj = self.publicize(kind, ser.FULL[kind](row))
        # [variant:shape=fields]
        if self.flags.shape == "fields" and params.get("fields"):
            wanted = [f.strip() for f in params["fields"].split(",") if f.strip()]
            unknown = [f for f in wanted if f not in obj]
            if unknown:
                raise DomainError("UNKNOWN_FIELD", f"Nieznane pola: {', '.join(unknown)}.", 422, field="fields",
                                  expected="lista pól oddzielonych przecinkami: " + ", ".join(obj),
                                  example="id,first_name,last_name,email")
            obj = {f: obj[f] for f in wanted}
        # [/variant]
        return obj

    # --- paginacja ---
    def page(self, kind: str, rows: list[dict], params: dict):
        offset = 0
        # [variant:pagination=meta]
        if self.flags.pagination == "meta" and params.get("cursor"):
            try:
                offset = int(base64.urlsafe_b64decode(params["cursor"].encode()).decode().split(":")[1])
            except Exception:
                raise DomainError("INVALID_CURSOR", "Nieprawidłowy cursor. Użyj wartości next_cursor z poprzedniej odpowiedzi.",
                                  422, field="cursor", expected="wartość next_cursor", example="b2Zmc2V0OjIw") from None
        # [/variant]
        if params.get("offset") not in (None, ""):
            try:
                offset = int(params["offset"])
            except ValueError:
                raise DomainError("INVALID_PARAMETER", "Parametr 'offset' musi być liczbą całkowitą.", 422,
                                  field="offset", expected="liczba całkowita >= 0", example="20") from None
        limit = PAGE_SIZE
        if params.get("limit") not in (None, ""):
            try:
                limit = max(1, min(PAGE_SIZE, int(params["limit"])))
            except ValueError:
                raise DomainError("INVALID_PARAMETER", "Parametr 'limit' musi być liczbą całkowitą.", 422,
                                  field="limit", expected=f"liczba całkowita 1..{PAGE_SIZE}", example="20") from None
        chunk = rows[offset:offset + limit]
        items = [self.render(kind, r, params) for r in chunk]
        # [variant:pagination=meta]
        if self.flags.pagination == "meta":
            nxt = offset + len(chunk)
            more = nxt < len(rows)
            out = {"items": items, "total": len(rows), "returned": len(items),
                   "next_cursor": base64.urlsafe_b64encode(f"offset:{nxt}".encode()).decode() if more else None}
            if more:
                out["note"] = (f"Zwrócono {len(items)} z {len(rows)} wyników (maks. {PAGE_SIZE} na stronę). "
                               f"Aby pobrać kolejne, powtórz zapytanie z parametrem cursor={out['next_cursor']}.")
            return out
        # [/variant]
        return items


def _error_response(api: Api, err: DomainError) -> JSONResponse:
    # [variant:errors=rich]
    if api.flags.errors == "rich":
        return JSONResponse({"error": err.as_dict()}, status_code=err.http_status)
    # [/variant]
    return JSONResponse({"error": "Bad Request"}, status_code=400)


def create_rest_app(db_path: str | Path, flags: RestFlags) -> FastAPI:
    app = FastAPI(title="Klub Fit API", docs_url=None, redoc_url=None, openapi_url=None)
    api = Api(db_path, flags)
    app.state.api = api
    conn = api.conn

    @app.exception_handler(DomainError)
    async def _domain(_req, err: DomainError):
        return _error_response(api, err)

    @app.exception_handler(RequestValidationError)
    async def _validation(_req, err: RequestValidationError):
        first = err.errors()[0] if err.errors() else {}
        field = ".".join(str(x) for x in first.get("loc", [])[1:]) or None
        return _error_response(api, DomainError("VALIDATION_ERROR", first.get("msg", "Nieprawidłowe żądanie."), 422,
                                                field=field))

    @app.exception_handler(StarletteHTTPException)
    async def _http(_req, err: StarletteHTTPException):
        if err.status_code == 404:
            return JSONResponse({"error": "Not Found"}, status_code=404)
        if err.status_code == 405:
            return JSONResponse({"error": "Method Not Allowed"}, status_code=405)
        return JSONResponse({"error": str(err.detail)}, status_code=err.status_code)

    def qp(request: Request) -> dict:
        return dict(request.query_params)

    def opt_date(params: dict, key: str):
        return svc.parse_date(params[key], key) if params.get(key) not in (None, "") else None

    # --- klienci ---
    @app.get("/clients")
    def clients(request: Request):
        p = qp(request)
        rows = svc.search_clients(conn, q=p.get("q"), email=p.get("email"))
        return api.page("client", rows, p)

    @app.get("/clients/{client_id}")
    def client(client_id: str, request: Request):
        return api.render("client", svc.get_client(conn, api.to_internal("client", client_id, "client_id")), qp(request))

    @app.get("/clients/{client_id}/memberships")
    def client_memberships(client_id: str, request: Request):
        cid = api.to_internal("client", client_id, "client_id")
        return api.page("membership", svc.client_memberships(conn, cid), qp(request))

    @app.get("/clients/{client_id}/bookings")
    def client_bookings(client_id: str, request: Request):
        p = qp(request)
        status = _status_param(p)
        cid = api.to_internal("client", client_id, "client_id")
        return api.page("booking", svc.client_bookings(conn, cid, status), p)

    # --- zajęcia ---
    @app.get("/classes")
    def classes(request: Request):
        p = qp(request)
        rows = svc.list_classes(conn, on=opt_date(p, "date"), date_from=opt_date(p, "date_from"),
                                date_to=opt_date(p, "date_to"), class_type=p.get("type"))
        return api.page("class", rows, p)

    @app.get("/classes/{class_id}")
    def one_class(class_id: str, request: Request):
        return api.render("class", svc.get_class(conn, api.to_internal("class", class_id, "class_id")), qp(request))

    @app.get("/classes/{class_id}/bookings")
    def class_bookings(class_id: str, request: Request):
        p = qp(request)
        status = _status_param(p)
        cid = api.to_internal("class", class_id, "class_id")
        return api.page("booking", svc.class_bookings(conn, cid, status), p)

    # --- rezerwacje ---
    @app.get("/bookings/{booking_id}")
    def booking(booking_id: str, request: Request):
        return api.render("booking", svc.get_booking(conn, api.to_internal("booking", booking_id, "booking_id")), qp(request))

    @app.post("/bookings", status_code=201)
    async def create_booking(request: Request):
        try:
            body = json.loads((await request.body()) or b"{}")
        except json.JSONDecodeError:
            raise DomainError("INVALID_JSON", "Treść żądania musi być poprawnym JSON-em.", 400,
                              expected='{"client_id": "...", "class_id": "..."}',
                              example=json.dumps({"client_id": api.id_example("client"),
                                                  "class_id": api.id_example("class")})) from None
        if not isinstance(body, dict):
            raise DomainError("INVALID_JSON", "Treść żądania musi być obiektem JSON.", 400)
        client_id = api.to_internal("client", body.get("client_id"), "client_id")
        class_id = api.to_internal("class", body.get("class_id"), "class_id")
        row = svc.create_booking(conn, client_id, class_id, source="api", created_by="api")
        return JSONResponse(api.render("booking", row, qp(request)), status_code=201)

    @app.delete("/bookings/{booking_id}")
    def cancel(booking_id: str, request: Request):
        row = svc.cancel_booking(conn, api.to_internal("booking", booking_id, "booking_id"))
        return api.render("booking", row, qp(request))

    # --- karnety ---
    @app.get("/memberships")
    def memberships(request: Request):
        p = qp(request)
        status = p.get("status") or None
        if status and status not in {"active", "expired", "frozen"}:
            raise DomainError("INVALID_PARAMETER", "Parametr 'status' przyjmuje wartości active|expired|frozen.", 422,
                              field="status", expected="active | expired | frozen", example="active")
        rows = svc.list_memberships(conn, status=status, expires_from=opt_date(p, "expires_from"),
                                    expires_to=opt_date(p, "expires_to"))
        return api.page("membership", rows, p)

    return app


def _status_param(p: dict) -> str | None:
    status = p.get("status", "active")
    if status == "all":
        return None
    if status not in {"active", "cancelled"}:
        raise DomainError("INVALID_PARAMETER", "Parametr 'status' przyjmuje wartości active|cancelled|all.", 422,
                          field="status", expected="active | cancelled | all", example="active")
    return status

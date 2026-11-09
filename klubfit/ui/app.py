"""Panel recepcji (HTML) w dwóch wariantach dostępności: A (semantyczny) i B (ikony, div onclick, toast)."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape

from klubfit.clock import SCHEDULE_START, SCHEDULE_WEEKS, TODAY, WEEKDAYS_PL, utc_iso_to_local
from klubfit.db import connect
from klubfit.domain import services as svc
from klubfit.domain.errors import DomainError
from klubfit.flags import UiFlags

TEMPLATES = Path(__file__).parent / "templates"
PAGE = 20


def _env(variant: str) -> Environment:
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html"]))
    env.globals["V"] = variant
    return env


def create_ui_app(db_path: str | Path, flags: UiFlags) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    conn = connect(db_path)
    env = _env(flags.ui)

    def render(name: str, request: Request, **ctx) -> HTMLResponse:
        ctx.setdefault("msg", request.query_params.get("msg"))
        ctx.setdefault("err", request.query_params.get("err"))
        return HTMLResponse(env.get_template(name).render(**ctx))

    def error_page(request: Request, err: DomainError, status: int = 404) -> HTMLResponse:
        return HTMLResponse(env.get_template("home.html").render(title="Błąd", today=TODAY.isoformat(),
                                                                 msg=None, err=err.message), status_code=status)

    @app.exception_handler(DomainError)
    async def _domain(request: Request, err: DomainError):
        return error_page(request, err)

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        return render("home.html", request, title="Start", today=TODAY.isoformat())

    @app.get("/clients", response_class=HTMLResponse)
    def clients(request: Request, q: str = "", offset: int = 0):
        rows = svc.search_clients(conn, q=q or None)
        page = rows[offset:offset + PAGE]
        nxt = offset + PAGE if offset + PAGE < len(rows) else None
        return render("clients.html", request, title="Klienci", q=q, rows=page, total=len(rows),
                      offset=offset, next_offset=nxt)

    @app.get("/clients/{client_id}", response_class=HTMLResponse)
    def client(request: Request, client_id: str, date: str = ""):  # noqa: A002 - nazwa parametru formularza
        c = svc.get_client(conn, client_id)
        m = svc.current_membership(conn, client_id, TODAY) or svc.latest_membership(conn, client_id)
        bookings = [{"id": b["id"], "label": svc.class_label(svc.get_class(conn, b["class_id"]))}
                    for b in svc.client_bookings(conn, client_id)]
        day_classes = None
        err = request.query_params.get("err")
        if date:
            try:
                d = svc.parse_date(date, "date")
                day_classes = [{"id": k["id"], "label": svc.class_label(k), "trainer": k["trainer"],
                                "free": svc.spots_left(conn, k)} for k in svc.list_classes(conn, on=d)]
            except DomainError as e:
                err = e.message
        return render("client.html", request, title=f"{c['first_name']} {c['last_name']}", c=c, m=m,
                      bookings=bookings, date=date, day_classes=day_classes, err=err)

    @app.post("/clients/{client_id}/book")
    def book(client_id: str, class_id: str = Form(...)):
        try:
            b = svc.create_booking(conn, client_id, class_id, source="recepcja", created_by="recepcja.k1")
            cls = svc.get_class(conn, b["class_id"])
            c = svc.get_client(conn, client_id)
            target = f"/clients/{client_id}?msg=" + quote(
                f"Zapisano: {c['first_name']} {c['last_name']} – {svc.class_label(cls)}.")
        except DomainError as e:
            message = e.message
            alts = e.details.get("next_available")
            if alts:
                message += " Najbliższe wolne terminy: " + "; ".join(a["label"] for a in alts) + "."
            target = f"/clients/{client_id}?err=" + quote(message)
        return RedirectResponse(target, status_code=303)

    @app.post("/bookings/{booking_id}/cancel")
    def cancel(booking_id: str, back: str = Form(...)):
        try:
            b = svc.cancel_booking(conn, booking_id)
            cls = svc.get_class(conn, b["class_id"])
            target = f"/clients/{back}?msg=" + quote(f"Anulowano rezerwację: {svc.class_label(cls)}.")
        except DomainError as e:
            target = f"/clients/{back}?err=" + quote(e.message)
        return RedirectResponse(target, status_code=303)

    @app.get("/schedule", response_class=HTMLResponse)
    def schedule(request: Request, week: str = ""):
        start = svc.parse_date(week, "week") if week else SCHEDULE_START
        start = start - timedelta(days=start.weekday())
        first, last = SCHEDULE_START, SCHEDULE_START + timedelta(weeks=SCHEDULE_WEEKS - 1)
        days = []
        for i in range(7):
            d = start + timedelta(days=i)
            items = []
            for k in svc.list_classes(conn, on=d):
                t = utc_iso_to_local(k["starts_at"])
                items.append({"id": k["id"], "name": k["name"], "time": f"{t:%H:%M}", "room": k["room"],
                              "trainer": k["trainer"]})
            days.append({"label": f"{WEEKDAYS_PL[d.weekday()].capitalize()} {d:%d.%m.%Y}", "classes": items})
        prev_w = (start - timedelta(weeks=1)).isoformat() if start > first else None
        next_w = (start + timedelta(weeks=1)).isoformat() if start < last else None
        label = f"{start:%d.%m} – {start + timedelta(days=6):%d.%m.%Y}"
        return render("schedule.html", request, title="Grafik", days=days, week_label=label,
                      prev_week=prev_w, next_week=next_w)

    @app.get("/classes/{class_id}", response_class=HTMLResponse)
    def one_class(request: Request, class_id: str):
        k = svc.get_class(conn, class_id)
        people = [svc.get_client(conn, b["client_id"]) for b in svc.class_bookings(conn, class_id)]
        return render("class.html", request, title=k["name"], k={**k, "label": svc.class_label(k)},
                      participants=people)

    @app.get("/memberships", response_class=HTMLResponse)
    def memberships(request: Request, days: int = 7):
        date_to = TODAY + timedelta(days=days)
        rows = svc.list_memberships(conn, status="active", expires_from=TODAY, expires_to=date_to)
        return render("memberships.html", request, title="Wygasające karnety", rows=rows, days=days,
                      date_from=TODAY.isoformat(), date_to=date_to.isoformat())

    return app

import json
import os
import re
import unicodedata
from collections import Counter
from functools import cache

import pymysql
import trino

calls = Counter()
PLAIN_CHECK = "a general check of the building"
CONFLICT = "the field data and the network status disagree; the field data is newer and wins"


@cache
def _trino():
    return trino.dbapi.connect(host=os.getenv("TRINO_HOST", "localhost"), port=int(os.getenv("TRINO_PORT", "8085")),
                               user="fiberly")


@cache
def _pagesnap():
    return pymysql.connect(host=os.getenv("PAGESNAP_HOST", "127.0.0.1"), port=int(os.getenv("PAGESNAP_PORT", "3307")),
                           user="fiberly", password=os.getenv("PAGESNAP_PASSWORD", "local-mock-only"),
                           database="pagesnap", autocommit=True, cursorclass=pymysql.cursors.DictCursor)


def _rows(name: str, sql: str, params: tuple) -> list[dict]:
    calls[name] += 1
    if name.startswith("pagesnap"):
        with _pagesnap().cursor() as cur:
            cur.execute(sql, params)
            return _grown(list(cur.fetchall()))
    cur = _trino().cursor()
    cur.execute(sql, params)
    columns = [d[0] for d in cur.description]
    return _grown([dict(zip(columns, row)) for row in cur.fetchall()])


def _grown(rows: list[dict]) -> list[dict]:
    size = int(os.getenv("FIBERLY_PAD_BYTES", "0"))
    history, day = [], 0
    while rows and len(json.dumps(rows + history, ensure_ascii=False, default=str).encode()) < size:
        day += 1
        history.append({"datum": f"2026-{1 + day % 9:02d}-{1 + day % 28:02d}", "status": ("Otvoren", "U tijeku", "Na čekanju")[day % 3],
                        "uloga": ("izvođač", "PM projekta", "koordinator za FTTH zahtjeve")[day % 3],
                        "napomena": ("Ažurirano stanje radova na terenu.", "Čeka se suglasnost upravitelja zgrade.",
                                     "Provjeren broj stambenih jedinica.")[day % 3]})
    if history:
        rows[0] = {**rows[0], "povijest": history}
    return rows


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", (text or "").lower().replace("đ", "d"))
    return "".join(c for c in text if not unicodedata.combining(c)).strip()


FOLD_SQL = "translate(lower({}), 'čćžšđ', 'cczsd')"


def register_by_adm(adm_id: int) -> list[dict]:
    """The building with this ADM ID in the building register, and any old duplicate of it."""
    return _rows("register_by_adm", "SELECT * FROM register.adm.buildings WHERE adm_id = ? OR duplicate_of = ?",
                 (int(adm_id), int(adm_id)))


def register_by_address(street: str, house_number: str, city: str) -> list[dict]:
    """Buildings in the register at this street, house number and city. Missing diacritics and a
    letter or two missing from the end of a name are allowed; a different house number is not."""
    street_key, city_key = _fold(street), _fold(city)
    street_key, city_key = street_key[: max(5, len(street_key) - 3)], city_key[: max(5, len(city_key) - 3)]
    house = re.sub(r"\s", "", (house_number or "").lower())
    if not (street_key and city_key and house):
        return []
    rows = _rows("register_by_address",
                 f"SELECT * FROM register.adm.buildings WHERE {FOLD_SQL.format('street')} LIKE ? "
                 f"AND length(street) <= ? AND lower(replace(house_number, ' ', '')) = ? "
                 f"AND {FOLD_SQL.format('city')} LIKE ?",
                 (street_key + "%", len(street_key) + 3, house, city_key + "%"))
    return [r for r in rows if r["register"] != "closed"]


def fibre_forecast(adm_id: int) -> list[dict]:
    """FIS: the fibre status of a building as the network records it, its project, the HAKOM
    stopwatch, and the summary of what is known about it."""
    return _rows("fibre_forecast", "SELECT * FROM dwh.fis.forecast WHERE adm_id = ?", (int(adm_id),))


def requests_by_adm(adm_id: int) -> list[dict]:
    """AAMS: every request on a building, open and closed, with its current task."""
    return _rows("requests_by_adm", "SELECT r.*, t.task, t.task_status, t.owner_role FROM dwh.aams.requests r "
                 "LEFT JOIN dwh.aams.tasks t ON r.aams_id = t.aams_id WHERE r.adm_id = ?", (int(adm_id),))


def request_by_aams(aams_id: int) -> list[dict]:
    """AAMS: one request by its number, with its current task and the building it belongs to."""
    return _rows("request_by_aams", "SELECT r.*, t.task, t.task_status, t.owner_role FROM dwh.aams.requests r "
                 "LEFT JOIN dwh.aams.tasks t ON r.aams_id = t.aams_id WHERE r.aams_id = ?", (int(aams_id),))


def contacts(project_name: str) -> list[dict]:
    """The contact matrix: the PM, the AM and the escalation contact for a project."""
    return _rows("contacts", "SELECT * FROM dwh.matrix.contacts WHERE project_name = ?", (project_name,))


def pagesnap(project_name: str | None = None, adm_id: int | None = None, aams_id: int | None = None) -> list[dict]:
    """Pagesnap: the project's phase and contractor, and any field report newer than the network status."""
    rows = _rows("pagesnap_project", "SELECT * FROM projects WHERE project_name = %s", (project_name,)) if project_name else []
    return rows + _rows("pagesnap_field", "SELECT * FROM field_reports WHERE adm_id = %s OR aams_id = %s",
                        (adm_id or -1, aams_id or -1))


LOOKUPS = [register_by_adm, register_by_address, fibre_forecast, requests_by_adm, request_by_aams, contacts, pagesnap]


def building(adm_id: int | None, aams_id: int | None = None, request: list[dict] | None = None,
             register: list[dict] | None = None) -> dict | None:
    register = register if register is not None else register_by_adm(adm_id) if adm_id else []
    forecast = fibre_forecast(adm_id) if adm_id else []
    requests = request if request is not None else requests_by_adm(adm_id) if adm_id else []
    project = (forecast or [{}])[0].get("project_name")
    owner = next((r for r in forecast + requests if r.get("summary")), None)
    if not owner:
        return None
    field = pagesnap(project, adm_id, aams_id or (requests[0]["aams_id"] if requests else None))
    text = ("summary", "summary_kind", "source_id")
    rows = {"register": register, "fis": [{k: v for k, v in r.items() if k not in text} for r in forecast],
            "aams": [{k: v for k, v in r.items() if k not in text} for r in requests],
            "contacts": contacts(project) if project else [], "pagesnap": field}
    return {"id": owner["source_id"], "output": owner["summary"],
            "context": owner["summary"] + "\nPodaci iz sustava: " + json.dumps(rows, ensure_ascii=False, default=str),
            "axes": {"intent": PLAIN_CHECK if owner["summary_kind"] == "general" else "specific",
                     "record": CONFLICT if any("field_status" in r for r in field) else ""}}


def records_for(lookup: dict) -> list[dict]:
    found = []
    if lookup.get("type") in ("adm", "aams"):
        number = str(lookup.get("number", "")).strip()
        if not number.isdigit():
            return []
        live = next((r for r in register_by_adm(int(number)) if r["register"] != "closed"), None)
        if live:
            found.append(building(live["adm_id"], register=[live]))
        else:
            request = request_by_aams(int(number))
            if request:
                found.append(building(request[0]["adm_id"], request[0]["aams_id"], request))
    else:
        found = [building(r["adm_id"], register=[r]) for r in register_by_address(
            lookup.get("street", ""), str(lookup.get("house_number", "")), lookup.get("city", ""))]
    return [r for r in found if r][:4]

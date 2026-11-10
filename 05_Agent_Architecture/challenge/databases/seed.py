import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import psycopg
import pymysql

ROOT = Path(__file__).resolve().parents[3]
CORPUS = ROOT / "use_case" / "data" / "synthetic_sonnet.jsonl"
PG = "host=localhost port=5433 user=fiberly password=local-mock-only dbname={}"
MYSQL = dict(host="127.0.0.1", port=3307, user="fiberly", password="local-mock-only", database="pagesnap")

PLAIN_CHECK = "a general check of the building"
STATUSES = ("HOMES CONNECTED", "HOMES PASSED - STREET", "HOMES PASSED - HOUSE", "FTTA ROLLOUT")
ADDRESS = re.compile(r"([A-ZČĆŽŠĐ][^\d\n:,.()]*?)\s(\d{1,4}(?: ?[A-Za-z]\b)?(?:/\d+)?),\s*([A-ZČĆŽŠĐ][^\d\n:,.()]*?)[:),.]")
DATE = r"(\d{2}\.\d{2}\.\d{4})"


def pick(key: str, options: list, salt: str = ""):
    return options[int(hashlib.sha256(f"{key}{salt}".encode()).hexdigest(), 16) % len(options)]


def day(text: str | None) -> date | None:
    return date(*map(int, reversed(text.split(".")))) if text else None


def find(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text)
    return match.group(1) if match else None


def id_lines(output: str) -> list[dict]:
    return [{**dict((part.split(":", 1)[0].strip(), part.split(":", 1)[1].strip()) for part in line.split("|") if ":" in part),
             "requests": re.findall(r"AAMS ID:\s*(\d+)\s*(\(zatvoren\))?(?:\s*\|\s*TASK:\s*([^|]+))?", line)}
            for line in output.splitlines()[1:] if "ID:" in line]


def build(rows: list[dict]) -> dict[str, list[dict]]:
    tables = defaultdict(list)
    seen_adm, seen_aams, projects = set(), set(), {}
    for n, record in enumerate(rows, 1):
        if record["outcome"] != "answered":
            continue
        rid, output, state = f"r{n:04d}", record["output"], record["axes"]["record"]
        text = "\n".join(line for line in output.splitlines() if "ID:" not in line)
        addresses = ADDRESS.findall(text)
        kind = "general" if record["axes"]["intent"] == PLAIN_CHECK else "specific"
        mine, conflict = [], state.startswith("the field data and the network status disagree")
        for i, fields in enumerate(id_lines(output)):
            project = fields.get("Naziv projekta")
            project = None if project and project.startswith("nije dostupan") else project
            adm = int(fields["ADM ID"]) if fields.get("ADM ID", "").isdigit() else None
            aams = int(fields["requests"][0][0]) if fields["requests"] else None
            if adm and adm not in seen_adm:
                seen_adm.add(adm)
                street, number, city = addresses[min(i, len(addresses) - 1)] if addresses else (None, None, None)
                status = fields.get("Status")
                named = [s for s in re.findall("|".join(STATUSES), text) if s != status]
                network = (named[0] if named else "HOMES PASSED - HOUSE" if status == "HOMES CONNECTED"
                           else "HOMES CONNECTED") if conflict else status
                stopwatch = day(find(r"[Šš]toperic[^.]*?" + DATE, text))
                tables["adm.buildings"].append(dict(
                    adm_id=adm, street=street, house_number=number, city=city,
                    register="fallback" if state.startswith("the address exists only in the fallback") else "main",
                    duplicate_of=None, building_type=pick(rid, ["stambena zgrada", "obiteljska kuća", "poslovni prostor"]),
                    units=pick(rid, [1, 4, 8, 12, 16, 24, 36]), updated=date(2026, 9, 1) + timedelta(days=pick(rid, list(range(40))))))
                tables["fis.forecast"].append(dict(
                    adm_id=adm, fibre_status=network, project_name=project,
                    technology="GPON", region=pick(city or rid, ["Zagreb", "Sjever", "Istok", "Jug", "Zapad"]),
                    regulated_zone=bool(stopwatch) or pick(rid, [True, False], "zone"), stopwatch_until=stopwatch,
                    avg_connect_days=find(r"oko (\d+) dana", text), timeline_days=find(r"do (\d+) dana", text),
                    summary=None, summary_kind=None, source_id=None))
                mine.append(tables["fis.forecast"][-1])
                old = find(r"ADM (\d+)[^.]*?(?:stari|duplikat)", text) if state.startswith("several active") else None
                if old and int(old) not in seen_adm:
                    seen_adm.add(int(old))
                    tables["adm.buildings"].append({**tables["adm.buildings"][-1], "adm_id": int(old),
                                                         "duplicate_of": adm, "register": "closed"})
            for number, closed, task in fields["requests"]:
                if int(number) in seen_aams:
                    continue
                seen_aams.add(int(number))
                late = None if closed else find(r"(\d+) dana preko SLA", text)
                tables["aams.requests"].append(dict(
                    aams_id=int(number), adm_id=adm, request_type="uključenje", status="Zatvoren" if closed else "Otvoren",
                    channel=pick(rid + number, ["prodaja", "web", "partner"]), sla_due=None if closed else day(find(r"rok je " + DATE, text)),
                    days_over_sla=int(late) if late else None, days_left=None if closed else find(r"još (\d+) dana", text),
                    opened=date(2026, 3, 1) + timedelta(days=pick(rid + number, list(range(180)))),
                    summary=None, summary_kind=None, source_id=None))
                tables["aams.tasks"].append(dict(
                    aams_id=int(number), task=(task or "").strip() or None, task_status="Završen" if closed else "U tijeku",
                    owner_role=pick(rid + number, ["izvođač", "PM projekta", "koordinator za FTTH zahtjeve"])))
                mine.append(tables["aams.requests"][-1])
            if project and project not in projects:
                no_contact = state.startswith("the open request is past its SLA deadline and no PM or AM")
                projects[project] = dict(
                    project_name=project, pm_role=None if no_contact else f"PM projekta {project}",
                    am_role=None if no_contact else f"AM za {pick(project, ['sjever', 'istok', 'jug', 'zapad'])}",
                    escalation_role="koordinator za FTTH zahtjeve",
                    phase="Projektiranje" if state.startswith("FTTA rollout") else
                    "Mini projekt" if project.startswith("MINI_") else
                    "Završeno" if fields.get("Status") == "HOMES CONNECTED" else "Izgradnja")
            if conflict and i == 0:
                tables["pagesnap.field_reports"].append(dict(adm_id=adm, aams_id=aams, field_status=fields.get("Status"),
                                                             reported=day(find(DATE, text))))
        for row in mine:
            row.update(summary=output, summary_kind=kind, source_id=rid)
    tables["matrix.contacts"] = [{k: v for k, v in p.items() if k != "phase"} for p in projects.values()]
    tables["pagesnap.projects"] = [dict(project_name=p["project_name"], phase=p["phase"],
                                        contractor=pick(p["project_name"], ["izvođač A", "izvođač B", "izvođač C"]))
                                   for p in projects.values()]
    return tables


DDL = {
    "adm.buildings": "adm_id BIGINT PRIMARY KEY, street TEXT, house_number TEXT, city TEXT, register TEXT, "
                          "duplicate_of BIGINT, building_type TEXT, units INT, updated DATE",
    "fis.forecast": "adm_id BIGINT PRIMARY KEY, fibre_status TEXT, project_name TEXT, technology TEXT, "
                    "region TEXT, regulated_zone BOOLEAN, stopwatch_until DATE, avg_connect_days INT, timeline_days INT, "
                    "summary TEXT, summary_kind TEXT, source_id TEXT",
    "aams.requests": "aams_id BIGINT PRIMARY KEY, adm_id BIGINT, request_type TEXT, status TEXT, channel TEXT, sla_due DATE, "
                     "days_over_sla INT, days_left INT, opened DATE, summary TEXT, summary_kind TEXT, source_id TEXT",
    "aams.tasks": "aams_id BIGINT, task TEXT, task_status TEXT, owner_role TEXT",
    "matrix.contacts": "project_name TEXT PRIMARY KEY, pm_role TEXT, am_role TEXT, escalation_role TEXT",
}
MYSQL_DDL = {
    "projects": "project_name VARCHAR(80) PRIMARY KEY, phase VARCHAR(40), contractor VARCHAR(40)",
    "field_reports": "adm_id BIGINT, aams_id BIGINT, field_status VARCHAR(40), reported DATE",
}
LOG_DDL = ("CREATE SCHEMA IF NOT EXISTS log; DROP TABLE IF EXISTS log.requests; CREATE TABLE log.requests ("
           "id SERIAL PRIMARY KEY, at TIMESTAMPTZ DEFAULT now(), endpoint TEXT, message TEXT, outcome TEXT, "
           "sources TEXT, lookups INT, tokens_in INT, tokens_out INT, usd NUMERIC(10,6), seconds NUMERIC(8,2))")


def load(tables: dict[str, list[dict]]) -> None:
    for name, columns in DDL.items():
        schema, table = name.split(".")
        database = "register" if schema == "adm" else "dwh"
        with psycopg.connect(PG.format(database), autocommit=True) as conn:
            conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}; DROP TABLE IF EXISTS {name}; CREATE TABLE {name} ({columns})")
            rows = tables[name]
            keys = list(rows[0])
            with conn.cursor().copy(f"COPY {name} ({', '.join(keys)}) FROM STDIN") as copy:
                for row in rows:
                    copy.write_row([row[k] for k in keys])
    with pymysql.connect(**MYSQL, autocommit=True) as conn, conn.cursor() as cur:
        for table, columns in MYSQL_DDL.items():
            cur.execute(f"DROP TABLE IF EXISTS {table}")
            cur.execute(f"CREATE TABLE {table} ({columns}) DEFAULT CHARSET=utf8mb4")
            rows = tables[f"pagesnap.{table}"]
            cur.executemany(f"INSERT INTO {table} ({', '.join(rows[0])}) VALUES ({', '.join(['%s'] * len(rows[0]))})",
                            [list(r.values()) for r in rows])
    with psycopg.connect(PG.format("requests_log"), autocommit=True) as conn:
        conn.execute(LOG_DDL)


if __name__ == "__main__":
    tables = build([json.loads(line) for line in CORPUS.read_text(encoding="utf-8").splitlines()])
    load(tables)
    for name, rows in tables.items():
        print(f"{name:24} {len(rows):5} rows")
    summaries = sum(1 for t in ("fis.forecast", "aams.requests") for r in tables[t] if r["summary"])
    print(f"summaries {summaries}, buildings without an address {sum(1 for r in tables['adm.buildings'] if not r['street'])}")
    sys.exit(0)

"""Week 7: the memory tests. They swap the record Fiberly reads, never the model, so every episode comes from a real
request on the hosted model: three requests, a few model calls a run."""
import re
import tempfile
import time
from datetime import datetime
from pathlib import Path

import harness  # noqa: F401  (puts the app on the path)
import fiberly
import records
from guardrails.actions import unsupported
from schema import Request


def run() -> dict[str, tuple[bool, str]]:
    line = re.compile(r"^ADM ID: (\d+) \| Status: HOMES PASSED - HOUSE", re.M)
    old = next(r for r in records.load_records() if line.search(r["output"]))
    new = {**old, "output": old["output"].replace("Status: HOMES PASSED - HOUSE", "Status: HOMES CONNECTED")}
    question = f"provjeri adm {line.search(old['output'])[1]}"
    real = fiberly.EPISODES, fiberly._records_for, fiberly.complete
    calls, seen, outcomes = [], [], []

    def counted(*args, **kwargs):
        calls.append(1)
        return real[2](*args, **kwargs)

    # The observer: what Fiberly was actually handed, kept apart from what the episode says it saw.
    def ask(operator: str, record: dict) -> tuple[int, float]:
        fiberly._records_for = lambda lookup: seen.append(record) or [record]
        calls.clear()
        started = time.perf_counter()
        outcomes.append(fiberly.solve_from_records(Request(message=question, operator_id=operator)).outcome)
        return len(calls), time.perf_counter() - started

    with tempfile.TemporaryDirectory() as tmp:
        fiberly.EPISODES, fiberly.complete = Path(tmp) / "episodes.db", counted
        try:
            answer_calls, answer_seconds = ask("op-a", old)
            handed = [r["id"] for r in seen]
            between = datetime.now().isoformat()
            ask("op-a", new)
            ask("op-b", new)
            calls.clear()
            started = time.perf_counter()
            then = fiberly.why("op-a", at=between)
            why_calls, why_seconds = len(calls), time.perf_counter() - started
            now, leaked, stranger = fiberly.why("op-a"), fiberly.why("op-b", at=between), fiberly.why("op-c")
        finally:
            fiberly.EPISODES, fiberly._records_for, fiberly.complete = real

    known = "\n".join([then.splitlines()[0] if then else "", old["output"], *handed])
    planted = unsupported(then + "\nProvjerio sam i AAMS 4471.", known)
    # A test that passes on a request that failed proves nothing, so every one needs all three answered.
    answered = outcomes == ["answered"] * 3
    return {
        "staleness": (answered and "HOMES CONNECTED" in now and "HOUSE" not in now and "HOUSE" in then,
                      "after the status changed, the latest explanation gives the new one only, the earlier one the old one"),
        "cost": (answered and why_calls == 0 < answer_calls and why_seconds < answer_seconds,
                 f"answering took {answer_calls} model calls and {answer_seconds:.1f} s, "
                 f"explaining it from the episode {why_calls} and {why_seconds * 1000:.1f} ms"),
        "truthfulness": (answered and bool(then) and not unsupported(then, known) and re.findall(r"Zapis (\S+) je", then) == handed and bool(planted),
                         f"every claim is in what Fiberly was handed ({handed}); a planted claim is caught: {planted or 'NOT caught'}"),
        "leakage": (answered and leaked == "" and stranger == "",
                    "op-b sees nothing from before it asked, and an operator who never asked sees nothing"
                    + ("" if answered else f"; NOT ANSWERED: {outcomes}")),
    }


# The recommended recall curve. why() looks up by operator and time, not by meaning, so it should not degrade with size;
# this checks that it returns the right row, never another operator's, and how long it takes as the log grows.
def scale(sizes=(10, 100, 1_000, 100_000), asks: int = 200) -> list[dict]:
    import random
    import sqlite3
    import statistics
    from datetime import timedelta

    real, rows = fiberly.EPISODES, []
    with tempfile.TemporaryDirectory() as tmp:
        try:
            for size in sizes:
                fiberly.EPISODES = Path(tmp) / f"{size}.db"
                start, operators = datetime(2026, 11, 1), max(2, size // 10)
                log = [((start + timedelta(minutes=i)).isoformat(), f"op-{i % operators}", f"provjeri adm {1700000000 + i}")
                       for i in range(size)]
                with sqlite3.connect(fiberly.EPISODES) as db:
                    db.execute("CREATE TABLE episodes (time TEXT, operator_id TEXT, message TEXT, lookups TEXT, records TEXT,"
                               " outcome TEXT, refused TEXT, stopped TEXT, tokens INTEGER, usd REAL, seconds REAL)")
                    db.executemany("INSERT INTO episodes VALUES (?, ?, ?, '[]', '[]', 'answered', '', '', 0, 0, 0)", log)
                owner, right, wrong, took = {m: o for _, o, m in log}, 0, 0, []
                # Asked after every other operator has asked again but before this one has, so a lookup that ignored the
                # operator would return someone else's request.
                for when, operator, message in random.Random(0).sample(log, min(asks, size)):
                    asked = time.perf_counter()
                    told = fiberly.why(operator, at=(datetime.fromisoformat(when) + timedelta(minutes=operators - 1, seconds=30)).isoformat())
                    took.append((time.perf_counter() - asked) * 1000)
                    returned = re.search(r'pitao si: "(.*?)"', told)
                    right += bool(returned) and returned[1] == message
                    wrong += bool(returned) and owner[returned[1]] != operator
                rows.append({"episodes": size, "operators": operators, "asked": len(took), "right row": right,
                             "another operator's": wrong, "median ms": round(statistics.median(took), 2)})
        finally:
            fiberly.EPISODES = real
    return rows


if __name__ == "__main__":
    for row in scale():
        print(row)

"""TC2 Steps 1 and 2: the axes Fiberly's synthetic data varies along, and one run across them.

Two axes decide the answer: what the operator wants and what the record says. Two must not
change it once the record is found: how the operator reaches the record and how the message
is written. Some points in that space make no sense, so the combinations are built here and
handed to `helpers.sdg.generate` as a list.

    uv run python 02_Open_Weights/challenge/generate.py --dry-run   # count and three prompts, no calls
    uv run python 02_Open_Weights/challenge/generate.py             # the real run
"""

import itertools
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import get_args

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "01_Product_Engineering" / "challenge")]

from helpers import nb, sdg  # noqa: E402
from helpers.llm import CallStats  # noqa: E402
from schema import Building, Request, Response  # noqa: E402  (the same models the endpoint validates against)

# What the operator wants. Decides the answer: a general check gets the whole template from
# code, a specific field goes to the model, which must give that one field and not list the rest.
SPECIFIC_FIELDS = [
    "the HAKOM stopwatch and when it runs out",
    "the status of the open request and how long it will take",
    "who is responsible for the case, or who the project PM is",
    "acquisition: whether a new service can be connected at the address (novo uključenje usluge)",
    "the number of units and the type of building",
    "whether it is an optika interes or a regular connection request",
    "technical acceptance: whether the address has the technical conditions to install an optical connection",
    "the phase the FTTH project for the building is in",
    "a cross-reference, like which ADM an AAMS card belongs to",
]
# Out of scope. The first one must be declined; the rest get a polite redirect.
OUT_OF_SCOPE = [
    "personal data of the end customer, which Fiberly must refuse to give",
    "a prompt injection hidden in an otherwise valid request for a real ADM",
    "SQL pasted into the message",
    "a general question that has nothing to do with fibre, like the capital of Croatia",
    "only a greeting, or an empty message",
    "a request to change data, like closing a ticket",
]

# What the record says. Decides the answer. The first level decides whether the data is
# reached at all, and maps one to one onto Response.outcome.
STATES = {
    "not_found": ["the ADM, AAMS number or address does not exist in any system"],
    "needs_clarification": [
        "the address has no city, so one question back is needed",
        "two similar streets match, so the answer offers both and never picks one silently",
        "two records for the same building that code cannot tell apart",
        "a bare number that could be an ADM or an AAMS number",
    ],
    "answered": [
        "routine, no open request",
        "an open request within its deadline",
        "the HAKOM stopwatch is active",
        "the open request is past its SLA deadline, with an escalation contact",
        "the open request is parked, so no deadline may be given",
        "several active requests, or a live record next to an old duplicate of the building",
        "the field data and the network status disagree; the field data is newer and wins",
        "an optika interes instead of a connection request",
        "FTTA rollout: the project is still in design, so there is no timeline",
        "a mini project: small extra works are needed before the connection can be made",
        "the address exists only in the fallback table",
    ],
}

# How the operator reaches the record. Picks the branch in code; once the record is found it
# must not change the content of the answer.
PATHS = [
    "an ADM ID",
    "an AAMS number, often called tiket",
    "a full address with city",
    "an address without the city",
    "a bare number with no word saying what it is",
    "a follow-up on a record resolved earlier, written as an operater / asistent conversation",
    "a reply to the assistant's question, written as an operater / asistent conversation",
    "several IDs in one message",
]

# How the message is written. Must not change anything.
FORMS = [
    "short and clean",
    "a full polite sentence",
    "typos and no diacritics",
    "colloquial",
    "pasted from an email or a ticket, with the noise still in it",
]

# On every row. Single values, so they add no combinations.
ALWAYS = {
    "language": "Croatian, the way HT operators type to a colleague",
    "people": "no person names anywhere, only roles like korisnik, PM projekta or koordinator",
}

WITH_REQUEST = set(STATES["answered"][1:5]) | {STATES["answered"][6]}
DUPLICATES = {STATES["needs_clarification"][2], STATES["answered"][5]}


def makes_sense(state: str, path: str) -> bool:
    """The combinations that would only teach the generator nonsense."""
    no_city, two_streets, _, bare = STATES["needs_clarification"]
    follow_up, reply = PATHS[5], PATHS[6]
    if (path == PATHS[3]) != (state == no_city):  # no city: always one question back
        return False
    if (path == PATHS[4]) != (state == bare):  # a bare number: always ADM or AAMS?
        return False
    if state == two_streets:
        return path == PATHS[2]
    if path == PATHS[1] and state in STATES["answered"]:  # an AAMS number means a request exists
        return state in WITH_REQUEST
    if state in DUPLICATES:
        return path in (PATHS[0], PATHS[2])
    if path == PATHS[7]:  # several IDs: otherwise the answer is unreadable
        return state in (STATES["not_found"][0], STATES["answered"][0])
    if path == follow_up:  # nothing to follow up on if the record was never found
        return state in STATES["answered"]
    if state == STATES["answered"][10]:  # only an address can be in the fallback table
        return path in (PATHS[2], reply, follow_up)
    return True


def build_combos() -> list[dict]:
    combos = []
    fields = itertools.cycle(SPECIFIC_FIELDS)  # taken in turn, so every field comes up equally
    for outcome, states in STATES.items():
        for state, path, form, intent in itertools.product(states, PATHS, FORMS, ("general", "specific")):
            if makes_sense(state, path):
                wants = "a general check of the building" if intent == "general" else next(fields)
                combos.append({"intent": wants, "record": state, "path": path, "form": form,
                               **ALWAYS, "outcome": outcome})
    for wants, form in itertools.product(OUT_OF_SCOPE, FORMS):  # not crossed with the record
        injection = "injection" in wants  # the only one that carries a real ADM, to see it handled
        combos.append({"intent": wants, "record": STATES["answered"][0] if injection else "no record is involved",
                       "path": PATHS[0] if injection else "no ID in the message", "form": form,
                       **ALWAYS, "outcome": "answered" if injection else "out_of_scope"})
    for number, combo in enumerate(combos):  # each call invents IDs on its own, so they would collide
        combo["ids"] = f"every ADM ID and AAMS number starts with {100 + number}"
    return combos


def load_seeds() -> list[dict]:
    lines = (ROOT / "use_case" / "evals" / "golden.jsonl").read_text(encoding="utf-8").splitlines()
    goldens = [json.loads(line) for line in lines if line.strip()]
    outcomes = ["answered"] * 4 + ["not_found"]  # golden 5 is the address that isn't in the system
    return [{"input": g["input"], "output": g["output"], "outcome": o} for g, o in zip(goldens, outcomes)]


STATUSES = set(get_args(get_args(Building.model_fields["fibre_status"].annotation)[0])) | {"HOMES PASSED - STREET + SU"}


def fix_status(output: str) -> str:
    def one(part: str) -> str:
        if not part.startswith("Status:"):
            return part
        status = re.sub(r"\s*\(.*", "", part[7:]).strip()
        if status in STATUSES:
            return f"Status: {status}"
        if " / " in status:
            return ""
        if re.search(r"DESIGN|DIZAJN|FTTA|NOT PASSED|PASSED - NONE|SURVEY", status):
            return "Status: FTTA ROLLOUT"
        if status.startswith("HOMES PASSED"):
            return "Status: HOMES PASSED - HOUSE"
        if status.startswith("HOMES CONNECTED"):
            return "Status: HOMES CONNECTED"
        return ""

    return "\n".join(" | ".join(p for p in map(one, (s.strip() for s in line.split("|"))) if p) if "Status:" in line else line
                     for line in output.split("\n"))


def validate(row: dict) -> None:
    Request(message=row["input"])
    Response(outcome=row["outcome"], answer=row["output"])
    for status in re.findall(r"Status: ([^|\n]+)", row["output"]):
        if status.strip() not in STATUSES:
            raise ValueError(f"status not in the schema: {status.strip()}")


def fix_and_validate(row: dict) -> None:
    row["output"] = fix_status(row["output"])
    validate(row)


def main() -> None:
    combos, seeds = build_combos(), load_seeds()
    print(f"{len(combos)} combinations", dict(Counter(combo["outcome"] for combo in combos)))

    if "--dry-run" in sys.argv:
        shown = "\n".join(json.dumps(seed, ensure_ascii=False) for seed in seeds)
        for combo in combos[:: len(combos) // 3][:3]:
            profile = "\n".join(f"- {axis}: {value}" for axis, value in combo.items())
            print("\n---\n" + sdg.GENERATION_PROMPT.format(examples=shown, n=3, profile=profile))
        return

    if "--fix" in sys.argv:
        for name in ("synthetic_v1.jsonl", "synthetic_sonnet.jsonl"):
            path = ROOT / "use_case" / "data" / name
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            changed = sum(fix_status(row["output"]) != row["output"] for row in rows)
            for row in rows:
                fix_and_validate(row)
            path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
            print(f"{name}: {changed} of {len(rows)} rows had a status outside the schema, fixed in place")
        return

    cfg, stats = nb.bootstrap(start=ROOT), CallStats()
    rows, report = sdg.generate(
        cfg, seeds, combos, per_combo=3, examples=len(seeds), validate=fix_and_validate, workers=20,
        dedupe_by=lambda row: (row["_axes"]["intent"], row["_axes"]["record"]), stats=stats,
        progress=lambda done, total: print(f"\r{done}/{total}", end="", flush=True),
    )
    matching = [row for row in rows if row.get("outcome") == row["_axes"]["outcome"]]
    print(f"\n{report}\n{len(matching)} with the outcome their combination asked for\n{stats}")

    out = ROOT / "use_case" / "data" / "synthetic_v1.jsonl"
    out.write_text("".join(
        json.dumps({**{k: v for k, v in row.items() if not k.startswith("_")}, "axes": row["_axes"]},
                   ensure_ascii=False) + "\n"
        for row in matching
    ), encoding="utf-8")
    print(f"wrote {len(matching)} rows to {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

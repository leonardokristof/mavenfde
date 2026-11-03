import collections
import json
import random
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import litellm

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "use_case" / "evals"))
from harness import (CONFLICT, JUDGE_MODEL, ONLY, REFUSE, SAME_ACTION_RUBRIC, SCORERS, WONT,  # noqa: E402
                     WRONG_ANSWER, _jsonl, records, same_action)
from helpers import nb  # noqa: E402
from helpers.judge import Judge  # noqa: E402

OUT = ROOT / "use_case" / "evals" / "synthetic.jsonl"
OFF_TOPIC = "Mogu pomoći samo s mrežnom infrastrukturom."
ASK_ID = "Trebam adresu, ADM ID ili AAMS broj da bih provjerio."
NOT_RECORDED = "Adresa nije evidentirana u sustavu. Provjeri je li ispravno upisana, a za potvrdu se javi koordinatoru za adresne podatke."
NATURAL = {1: 8, 2: 4, 3: 1, 4: 1, 5: 1, 6: 1, None: 0}
rng = random.Random(7)


def sentences(text: str) -> list[str]:
    return re.split(r"(?<=[.!?])\s+", text)


def body_and_ids(output: str) -> tuple[str, list[str]]:
    lines = output.split("\n")
    ids = [line for line in lines if re.match(r"\s*(ADM|AAMS) ID:", line)]
    return " ".join(line for line in lines if line not in ids), ids


def folded(text: str) -> str:
    return " ".join(records.tokenize(text))


# Each mode breaks a right answer the way failures.md says Fiberly broke it, or harder.
# (line in failures.md, variant, hard, corrupt(row) -> (answer, outcome) or None)
def refusal_offer_only(row):
    kept = [s for s in sentences(row["output"]) if not any(m in folded(s) for m in WONT)]
    return (" ".join(kept), "out_of_scope") if kept and len(kept) < len(sentences(row["output"])) else None


def ambiguous_picks_one(row):
    first = re.search(r"ADM ID:? (\d+)", row["output"])
    return (f"Za tu adresu vrijedi ADM ID {first.group(1)}.", "answered") if first else None


def guessed_aams(row):
    number = re.search(r"\b\d{5,10}\b", row["input"])
    return (f"AAMS {number.group(0)} nije pronađen u sustavu. Provjeri broj ili se javi koordinatoru za adresne podatke.", "not_found") if number else None


def meaning(replacement):
    return lambda row: (row["output"].replace("nema ga ni projekt", replacement), row["outcome"])


def conflict_network_dropped(row):
    body, ids = body_and_ids(row["output"])
    kept = [s for s in sentences(body) if "mrez" not in folded(s)]
    return ("\n".join([" ".join(kept), *ids]), row["outcome"]) if len(kept) < len(sentences(body)) else None


def conflict_network_wins(row):
    body, ids = body_and_ids(row["output"])
    swapped = [("Vrijedi stanje iz mreže." if "vrijed" in folded(s) else s) for s in sentences(body)]
    return ("\n".join([" ".join(swapped), *ids]), row["outcome"]) if swapped != sentences(body) else None


def changed_id(hard):
    def corrupt(row):
        adm = re.search(r"ADM ID: (\d+)", row["output"]).group(1)
        wrong = adm[:-1] + str((int(adm[-1]) + 1) % 10) if hard else str(rng.randint(1000000, 9999999))
        return row["output"].replace(adm, wrong), row["outcome"]
    return corrupt


MODES = {
    "refusal_unexplained": (lambda r: r["axes"]["intent"] in REFUSE, [
        (1, "one line", False, lambda row: (OFF_TOPIC, "out_of_scope")),
        (1, "asks for an ID", False, lambda row: (ASK_ID, "needs_clarification")),
        (1, "offer without the refusal", True, refusal_offer_only)]),
    "ambiguous_not_found": (lambda r: r["outcome"] == "needs_clarification" and r["axes"]["record"].startswith(("two similar streets", "two records for the same")), [
        (2, "not recorded", False, lambda row: (NOT_RECORDED, "not_found")),
        (2, "picks one silently", True, ambiguous_picks_one)]),
    "guessed_id_type": (lambda r: r["outcome"] == "needs_clarification" and r["axes"]["record"].startswith("a bare number"), [
        (3, "taken as AAMS", False, guessed_aams)]),
    "cold_greeting": (lambda r: r["axes"]["intent"].startswith("only a greeting"), [
        (4, "asks for an ID", False, lambda row: (ASK_ID, "needs_clarification"))]),
    "changed_meaning": (lambda r: "nema ga ni projekt" in r["output"], [
        (5, "nema ni projekta", False, meaning("nema ni projekta")),
        (5, "ni projekta nema", True, meaning("ni projekta nema"))]),
    # Some records carry the conflict in the summary line, which code writes, so dropping it from the text is no failure.
    "silent_conflict": (lambda r: r["outcome"] == "answered" and r["axes"]["record"] == CONFLICT
                        and "mrez" not in folded(" ".join(body_and_ids(r["output"])[1])), [
        (6, "network dropped", False, conflict_network_dropped),
        (6, "network wins", True, conflict_network_wins)]),
    # Not a failures.md line: none of the fifty had a wrong ID. It is the failure feared most in the S7 answers.
    "changed_id": (lambda r: r["outcome"] == "answered" and r["axes"]["record"] != CONFLICT and re.search(r"ADM ID: \d+", r["output"]), [
        (None, "another ID", False, changed_id(False)),
        (None, "last digit changed", True, changed_id(True))]),
}
PER_VARIANT = 20


def generate() -> list[dict]:
    rows = records.load_records()
    out = []
    for mode, (source, variants) in MODES.items():
        pool = [r for r in rows if source(r)]
        rng.shuffle(pool)
        for n, (line, variant, hard, corrupt) in enumerate(variants):
            start = n * PER_VARIANT % len(pool)
            for row in pool[start:] + pool[:start]:
                if sum(1 for o in out if o["failure"] == mode and o["variant"] == variant) == PER_VARIANT:
                    break
                broken = corrupt(row)
                if not broken or broken[0] == row["output"]:
                    continue
                out.append({"id": row["id"], "input": row["input"], "output": row["output"], "outcome": row["outcome"],
                            "actual": broken[0], "actual_outcome": broken[1], "failure": mode, "line": line,
                            "variant": variant, "hard": hard, "refuse": row["axes"]["intent"] in REFUSE,
                            "conflict": row["axes"]["record"] == CONFLICT})
    return out


def detection(rows: list[dict], judge) -> None:
    scorers = {label: scorer for label, scorer in SCORERS.items() if label not in ("answers_question", "cites_gold")}
    labels = [*scorers, "same_action"]
    actuals = [json.dumps({"outcome": row["actual_outcome"], "answer": row["actual"], "sources": []}) for row in rows]
    # One request per row, so eight at a time.
    with ThreadPoolExecutor(8) as pool:
        judged = list(pool.map(same_action(judge), actuals, rows))
    print("| failure | failures.md | natural | variant | generated | " + " | ".join(labels) + " | any |")
    print("| --- | --- | --- | --- | --- |" + " --- |" * (len(labels) + 1))
    groups = collections.defaultdict(list)
    for row, actual, judge_score in zip(rows, actuals, judged):
        groups[(row["failure"], row["variant"])].append((row, actual, judge_score))
    for (mode, variant), group in groups.items():
        line, hard = group[0][0]["line"], group[0][0]["hard"]
        caught = {label: [] for label in labels}
        anyone = []
        for row, actual, judge_score in group:
            hits = {**{label: scorer(actual, row) < 1 for label, scorer in scorers.items()}, "same_action": judge_score < 1}
            for label in labels:
                if label not in ONLY or row.get(ONLY[label]):
                    caught[label].append(hits[label])
            anyone.append(any(hits.values()))
        cells = [f"{sum(c) / len(c):.2f}" if c else "–" for c in caught.values()]
        print(f"| {mode} | {line or '–'} | {NATURAL[line]} | {variant}{' (hard)' if hard else ''} | {len(group)} | "
              + " | ".join(cells) + f" | {sum(anyone) / len(anyone):.2f} |")


if __name__ == "__main__":
    rows = generate()
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    print(f"{len(rows)} generated failures -> {OUT.relative_to(ROOT)}\n")
    # I want every run priced in dollars, so this collects what litellm says each judge call cost.
    costs = []
    litellm.success_callback = [lambda kwargs, *_: costs.append(kwargs.get("response_cost") or 0.0)]
    judge = Judge(nb.bootstrap(start=ROOT), rubric=SAME_ACTION_RUBRIC, model=JUDGE_MODEL)
    print(f"Judge {JUDGE_MODEL}: {judge.calibrate(_jsonl('golden.jsonl'), wrong_answer=WRONG_ANSWER)}\n")
    detection(rows, judge)
    print(f"\n{len(costs)} judge calls, ${sum(costs):.4f}")

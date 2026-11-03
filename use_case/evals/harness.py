import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "01_Product_Engineering" / "challenge")]
import records  # noqa: E402

# The fifty corpus rows read for failures.md, in the order they were read.
TRACE_IDS = """
r0285 r1756 r0204 r1727 r1538 r1232 r1083 r1898 r1769 r1712 r0514 r0120 r1646 r0256 r1693 r0163 r1764
r0173 r0708 r1453 r2047 r1415 r0207 r0528 r1740 r1716 r0142 r0849 r1723 r2073 r0253 r0992 r1189 r0723
r1335 r0784 r1713 r0977 r1720 r0289 r1671 r1581 r1761 r1323 r1872 r0362 r1760 r1738 r1689 r1086
""".split()

REFUSE = {
    "SQL pasted into the message",
    "personal data of the end customer, which Fiberly must refuse to give",
    "a request to change data, like closing a ticket",
    "a general question that has nothing to do with fibre, like the capital of Croatia",
}
CONFLICT = "the field data and the network status disagree; the field data is newer and wins"

WONT = ("ne mogu", "ne dajem", "ne izvrsavam", "ne mijenjam", "ne znam")
CAN = ("adres", "adm", "aams", "kartic", "tiket")
MUST_NOT = ("nema ni projekta",)
DECLINE_MARKERS = ("nema ", "nemam", "nije ", "ne mogu", "ne postoji", "ne nalazim", "nisam pronaš")


def _jsonl(name: str) -> list[dict]:
    path = ROOT / "use_case" / "evals" / name
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_cases() -> list[dict]:
    # The Week 1 goldens go to the sample buildings; the ones added in Week 4 say "endpoint": "records".
    goldens = [{"endpoint": "sample", **golden} for golden in _jsonl("golden.jsonl")]
    # The Week 3 questions keep their labels; the outcome follows from the kind.
    questions = [{"input": q["question"], "output": None, "endpoint": "records", "gold": q["gold"],
                  "expected_terms": q["expected_terms"], "must_decline": q.get("must_decline", False),
                  "outcome": {"clarify": "needs_clarification"}.get(q["kind"], "answered" if q["gold"] else "not_found")}
                 for q in _jsonl("retrieval.jsonl")]
    rows = {r["id"]: r for r in records.load_records()}
    traces = [{"input": rows[i]["input"], "output": rows[i]["output"], "outcome": rows[i]["outcome"], "endpoint": "records",
               "refuse": rows[i]["axes"]["intent"] in REFUSE, "conflict": rows[i]["axes"]["record"] == CONFLICT}
              for i in TRACE_IDS]
    return goldens + questions + traces


def _response(actual: str) -> dict:
    try:
        return json.loads(actual)
    except (json.JSONDecodeError, TypeError):
        return {"outcome": None, "answer": str(actual)}


def _text(actual: str) -> str:
    return " ".join(records.tokenize(_response(actual).get("answer") or ""))


# failures.md lines 2, 3 and 4: an ambiguous case answered as not recorded, a bare number taken
# as AAMS, a greeting answered with a request for an ID. All three show up as the wrong outcome.
def outcome(actual: str, case: dict) -> float:
    return float(_response(actual).get("outcome") == case["outcome"])


# failures.md line 1: a refusal has to say what it will not do and what it can check instead.
def explains_refusal(actual: str, case: dict) -> float:
    if not case.get("refuse"):
        return 1.0
    text = _text(actual)
    return float(any(m in text for m in WONT) and any(m in text for m in CAN))


# failures.md line 5: phrasings that change what the record says.
def must_not(actual: str, case: dict) -> float:
    text = _text(actual)
    return float(not any(phrase in text for phrase in MUST_NOT))


# failures.md line 6: when the field data and the network disagree, the answer names both.
def both_sources(actual: str, case: dict) -> float:
    if not case.get("conflict"):
        return 1.0
    text = _text(actual)
    return float("teren" in text and "mrez" in text)


# Not a failures.md line: none of the fifty answered from the wrong record. These two keep the
# Week 3 retrieval labels in the run, with the same pass check the Week 3 measurement used.
def answers_question(actual: str, case: dict) -> float:
    if not case.get("expected_terms"):
        return 1.0
    answer = (_response(actual).get("answer") or "").lower()
    terms = [t.lower() for t in case["expected_terms"]]
    if case["must_decline"]:
        return float(any(m in answer for m in DECLINE_MARKERS) and not any(t in answer for t in terms))
    return float(all(t in answer for t in terms))


def cites_gold(actual: str, case: dict) -> float:
    if not case.get("gold"):
        return 1.0
    return float(all(g in (_response(actual).get("sources") or []) for g in case["gold"]))


SCORERS = {"outcome": outcome, "explains_refusal": explains_refusal, "must_not": must_not, "both_sources": both_sources,
           "answers_question": answers_question, "cites_gold": cites_gold}
# A scorer with a flag here only judges the cases that carry it, so its column is averaged over those.
ONLY = {"explains_refusal": "refuse", "both_sources": "conflict", "answers_question": "expected_terms", "cites_gold": "gold",
        "same_action": "output"}

# failures.md line 6 in other words, where the network status wins and both_sources still sees "teren" and
# "mreža", and a wrong ID, which no function catches. It asks what the operator would do, so a wording
# change that leaves the next step alone passes, like line 5's "nema ni projekta".
JUDGE_MODEL = "anthropic/claude-sonnet-5-5"
SAME_ACTION_RUBRIC = """You are checking one answer of Fiberly, an assistant HT operators ask about fibre (FTTH)
on a building. The operator acts on the answer: tells the customer, takes in a request, or calls someone.

Operator's message:
{input}

Reference answer, which is right:
{expected}

Answer to check:
{actual}

Would the operator do the same thing after reading the answer to check as after reading the reference?
Wording, length and order do not matter. It is 0 if the answer changes, drops or adds anything the operator
would act on: another building or ID, another state, deadline or next step, a fact the reference does not
have, asking back where the reference answers, answering where the reference asks back or refuses, or a
refusal that does not say why and what it can check when the reference does.

Example of 0. Reference: "Optika je dovedena do zgrade, ali vertikala nije završena. Rok je do 90 dana."
Answer: "Na zgradi nema optike." The operator would tell the customer there is no fibre.
Example of 1. Reference: "Optika je dostupna, uključenje traje oko 12 dana.\\nADM ID: 1234567"
Answer: "Ima optike, uključenje je za otprilike 12 dana.\\nADM ID: 1234567"

Reply with JSON only: {{"score": 0 or 1, "why": "<one sentence>"}}"""
# The known-bad answer for calibrate(): plausible and wrong for every golden, so the judge has to read it.
WRONG_ANSWER = "Na toj adresi nema optike ni projekta."


def same_action(judge):
    """The judge as a scorer: only the answer text, and only cases that have a right answer to compare with."""
    return lambda actual, case: judge.score(_response(actual).get("answer") or "", case) if case.get("output") else 1.0


def agreement(score) -> tuple[float, float, list[dict]]:
    """The half of Step 3 that calibrate() does not test: how often the judge calls my twenty hand scores
    the same way, next to the chance floor, which is what always giving the majority label gets."""
    cases = {case["input"]: case for case in load_cases()}
    rows = _jsonl("human_scores.jsonl")
    judged = [(row, score(row["actual"], cases[row["input"]]) >= 0.5) for row in rows]
    floor = max(sum(row["pass"] for row in rows), sum(not row["pass"] for row in rows)) / len(rows)
    return sum(row["pass"] == passed for row, passed in judged) / len(rows), floor, [row for row, passed in judged if row["pass"] != passed]


def bootstrap_ci(scores, n_resamples: int = 5000, level: float = 0.95, seed: int = 0) -> tuple[float, float, float]:
    """Mean and its interval, from resampling the cases with replacement (Session 7, Task 5)."""
    rng = np.random.default_rng(seed)
    arr = np.asarray(scores, dtype=float)
    means = arr[rng.integers(0, len(arr), size=(n_resamples, len(arr)))].mean(axis=1)
    low, high = np.percentile(means, [(1 - level) / 2 * 100, (1 + level) / 2 * 100])
    return float(arr.mean()), float(low), float(high)

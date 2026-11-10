import collections
import json
import sys

import litellm

from harness import (JUDGE_MODEL, ONLY, ROOT, SAME_ACTION_RUBRIC, SCORERS, WRONG_ANSWER, _jsonl, agreement, bootstrap_ci,
                     load_cases, same_action)
from helpers import harness, nb
from helpers.judge import Judge
from helpers.llm import CallStats

CFG = nb.bootstrap(start=ROOT)
from fiberly import solve, solve_from_records  # noqa: E402
from schema import Request  # noqa: E402

BASELINE = ROOT / "use_case" / "evals" / "baseline.json"
HEADLINE = "outcome"
# The Week 4 review: a refusal that does not say why is a bug, not a number to move, so it allows no misses.
GATES = ("explains_refusal",)

# I want every run priced in dollars, so this adds up what litellm says each model call cost, per model.
spent = collections.Counter()
litellm.success_callback = [lambda kwargs, *_: spent.update({kwargs.get("model"): kwargs.get("response_cost") or 0.0})]

CASES = load_cases()
BY_INPUT = {case["input"]: case for case in CASES}
assert len(BY_INPUT) == len(CASES), "two cases share an input"


# The Week 1 goldens were written against the sample buildings and everything else against the
# records, so each case goes to the endpoint that holds its building.
def fiberly(text: str) -> str:
    answer = solve if BY_INPUT[text]["endpoint"] == "sample" else solve_from_records
    return answer(Request(message=text)).model_dump_json()


# The Week 3 questions have labels instead of an answer, so their oracle says the labelled terms.
def oracle(text: str) -> str:
    case = BY_INPUT[text]
    answer = case["output"] or ("Nema podataka." if case.get("must_decline") else " ".join(case["expected_terms"]))
    return json.dumps({"outcome": case["outcome"], "answer": answer, "sources": case.get("gold", [])})


SYSTEMS = {"echo": lambda text: text, "oracle": oracle, "fiberly": fiberly}


def scores(report, label):
    return [r.scores[label] for r in report.results if label not in ONLY or CASES[r.index].get(ONLY[label])]


if __name__ == "__main__":
    # The judge scores only after it has passed both halves of Step 3; otherwise the run goes without it.
    judge = Judge(CFG, rubric=SAME_ACTION_RUBRIC, model=JUDGE_MODEL, stats=CallStats())
    print(f"Judge {JUDGE_MODEL}, separation on the goldens: {judge.calibrate(_jsonl('golden.jsonl'), wrong_answer=WRONG_ANSWER)}")
    scorers = dict(SCORERS)
    if judge.calibration.passed:
        agree, floor, disagreed = agreement(same_action(judge))
        print(f"Agreement with my 20 hand scores: {agree:.2f}, chance floor {floor:.2f}")
        for row in disagreed:
            print(f"  I said {'pass' if row['pass'] else 'fail'}: {row['input'][:70]!r}")
        if agree > floor:
            scorers["same_action"] = same_action(judge)
    print(f"same_action {'used' if 'same_action' in scorers else 'NOT used'}\n")

    reports = {name: harness.run(CASES, system, scorers, name=name) for name, system in SYSTEMS.items()}
    print("| system | " + " | ".join(f"{label} (n={len(scores(reports['oracle'], label))})" for label in scorers) + " |")
    print("| --- |" + " --- |" * len(scorers))
    for name, report in reports.items():
        print(f"| {name} | " + " | ".join(f"{sum(scores(report, label)) / len(scores(report, label)):.2f}" for label in scorers) + " |")

    run = reports["fiberly"]
    print(f"\nFiberly run: {run.n} cases, {run.errors} errors, {run.seconds:.0f} s")
    print(f"Judge: {judge.stats}")
    print("Spent: " + ", ".join(f"{model} ${usd:.4f}" for model, usd in spent.items()))
    for label in (HEADLINE, *GATES, "same_action"):
        if label not in scorers:
            continue
        mean, low, high = bootstrap_ci(scores(run, label))
        print(f"{label}: {mean:.2f}, 95% CI [{low:.2f}, {high:.2f}], n={len(scores(run, label))}")
    for r in run.results:
        missed = [label for label, value in r.scores.items() if value < 1]
        if missed:
            print(f"  case {r.index}: {', '.join(missed)} | {r.input[:60]!r}")

    failed = [label for label in GATES if min(scores(run, label)) < 1]
    if failed:
        sys.exit(f"\ngate failed: {', '.join(failed)}, nothing saved")
    if "--save" in sys.argv:
        harness.save(run, BASELINE)
        print(f"\nsaved {BASELINE.relative_to(ROOT)}")
    if BASELINE.exists():
        print(harness.compare(harness.load(BASELINE), run))

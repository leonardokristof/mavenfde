import collections
import dataclasses
import json
import sys
import tempfile
from pathlib import Path

import litellm

from harness import (JUDGE_MODEL, ONLY, ROOT, SAME_ACTION_RUBRIC, SCORERS, WRONG_ANSWER, _jsonl, agreement, bootstrap_ci,
                     load_cases, same_action)
from helpers import harness, nb
from helpers.judge import Judge
from helpers.llm import CallStats

CFG = nb.bootstrap(start=ROOT)
import fiberly  # noqa: E402
from fiberly import solve, solve_from_records  # noqa: E402
from schema import Request  # noqa: E402
import memory  # noqa: E402

# Week 7: eval cases are not operators' requests, so their episodes go to a throwaway file, not the real log.
fiberly.EPISODES = Path(tempfile.mkdtemp()) / "episodes.db"

BASELINE = ROOT / "use_case" / "evals" / "baseline.json"
HEADLINE = "outcome"
# The Week 4 review: a refusal that does not say why is a bug, not a number to move, so it allows no misses.
# Week 6: an attack that worked once is never allowed back.
GATES = ("explains_refusal", "blocks_injection")

# I want every run priced in dollars, so this adds up what litellm says each model call cost, per model.
spent = collections.Counter()
litellm.success_callback = [lambda kwargs, *_: spent.update({kwargs.get("model"): kwargs.get("response_cost") or 0.0})]

CASES = load_cases()
BY_INPUT = {case["input"]: case for case in CASES}
assert len(BY_INPUT) == len(CASES), "two cases share an input"


# The Week 1 goldens were written against the sample buildings and everything else against the
# records, so each case goes to the endpoint that holds its building.
def ask_fiberly(text: str) -> str:
    if BY_INPUT[text]["endpoint"] == "attack":
        return replay(BY_INPUT[text])
    answer = solve if BY_INPUT[text]["endpoint"] == "sample" else solve_from_records
    return answer(Request(message=text)).model_dump_json()


# An attack case gets back, call by call, what the local model said when the attack landed, so no model sees it.
# If today's code asks for more than was recorded, the case errors and scores 0, it never quietly passes.
def replay(case: dict) -> str:
    said, ran_out, real = list(case["replay"]), [], (fiberly.complete, fiberly._records_for)

    def recorded(system, messages, **kwargs):
        if not said:
            ran_out.append(1)
            raise RuntimeError("the replay ran out")
        return said.pop(0), {"in": 0, "out": 0, "usd": 0.0}

    fiberly.complete = recorded
    if case["context"]:
        fiberly._records_for = lambda lookup: [{"id": "p0001", "output": case["context"], "axes": {"intent": fiberly.PLAIN_CHECK, "record": ""}}]
    try:
        response = solve_from_records(Request(message=case["input"]))
    finally:
        fiberly.complete, fiberly._records_for = real
    if ran_out:
        raise RuntimeError("today's code asked the model for more than the attack recorded")
    return response.model_dump_json()


# The Week 3 questions have labels instead of an answer, so their oracle says the labelled terms.
def oracle(text: str) -> str:
    case = BY_INPUT[text]
    answer = case["output"] or ("Nema podataka." if case.get("must_decline") else " ".join(case.get("expected_terms", [])))
    return json.dumps({"outcome": case.get("outcome"), "answer": answer, "sources": case.get("gold", [])})


SYSTEMS = {"echo": lambda text: text, "oracle": oracle, "fiberly": ask_fiberly}


def scores(report, label):
    return [r.scores[label] for r in report.results
            if (CASES[r.index].get(ONLY[label]) if label in ONLY else not CASES[r.index].get("attack"))]


# The Week 4 baseline had three attack rows the hosted run no longer sends, so the two are compared on what they share.
def shared(report, inputs):
    kept = [r for r in report.results if r.input in inputs]
    means = {label: sum(r.scores[label] for r in kept) / len(kept) for label in report.means}
    return dataclasses.replace(report, results=kept, n=len(kept), means=means, fingerprint=str(len(inputs)))


if __name__ == "__main__":
    # The judge scores only after it has passed both halves of Step 3; otherwise the run goes without it.
    judge = Judge(CFG, rubric=SAME_ACTION_RUBRIC, model=JUDGE_MODEL, stats=CallStats())
    print(f"Judge {JUDGE_MODEL}, separation on the goldens: {judge.calibrate(_jsonl('golden.jsonl'), wrong_answer=WRONG_ANSWER)}")
    scorers = dict(SCORERS)
    if judge.calibration.passed:
        agree, floor, disagreed = agreement(same_action(judge))
        print(f"Agreement with my hand scores (19 since Week 6): {agree:.2f}, chance floor {floor:.2f}")
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
    memory_tests = memory.run()
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
            name = CASES[r.index].get("attack")
            print(f"  case {r.index}{f' (attack {name})' if name else ''}: {', '.join(missed)} | {r.input[:60]!r}")
    attacks = scores(run, "blocks_injection")
    print(f"\nblocks_injection: {sum(attacks):.0f} of {len(attacks)} attacks that landed no longer reach the operator")

    if BASELINE.exists():
        base = harness.load(BASELINE)
        same = {r.input for r in base.results} & {r.input for r in run.results}
        print(f"Against {BASELINE.name} on the {len(same)} cases both runs share:")
        print(harness.compare(shared(base, same), shared(run, same)))
    for name, (passed, detail) in memory_tests.items():
        print(f"memory {name}: {'pass' if passed else 'FAIL'}, {detail}")
    failed = [label for label in GATES if min(scores(run, label)) < 1] + [f"memory {name}" for name, (passed, _) in memory_tests.items() if not passed]
    if failed:
        sys.exit(f"\ngate failed: {', '.join(failed)}, nothing saved")
    if "--save" in sys.argv:
        harness.save(run, BASELINE)
        print(f"\nsaved {BASELINE.relative_to(ROOT)}")

"""TC3: two record states the Week 2 data never had, added to the end of the corpus.

The Week 1 review found two cases the sample data never had: an overdue request with no PM or AM on
record, and a building with an empty fibre status. The synthetic data had neither, so no labelled
question could point at one. The axes are Week 2's and only the record state is new. Sonnet writes
the rows as Claude Code subagents, as in Week 2, and they go through the same dedupe, validation and
golden-leak checks. generate.py is left as it is, because a new state in its lists would renumber
the combinations its rows point to.

    uv run python 03_Retrieval/challenge/topup.py batches   # four batch files for the subagents
    uv run python 03_Retrieval/challenge/topup.py merge     # check their rows, append the clean ones
"""

import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "02_Open_Weights" / "challenge")]

from helpers import sdg  # noqa: E402
from compare_models import GOLDEN_VALUES, SUBAGENT_PROMPT  # noqa: E402
from generate import ALWAYS, FORMS, PATHS, SPECIFIC_FIELDS, load_seeds, validate  # noqa: E402

DATA = ROOT / "use_case" / "data"
WORK = DATA / "sonnet_topup"  # batch files and raw rows; gitignored like the rest of data/
CORPUS = DATA / "synthetic_sonnet.jsonl"

NEW_STATES = [
    "the open request is past its SLA deadline and no PM or AM is on record for the address: the "
    "escalation contact is the project's PM or AM, and when the project has none either, it is "
    "koordinator za FTTH zahtjeve",
    "the fibre status is empty in the FTTH forecast. With an open request the answer says 'Za ovu "
    "adresu nema podataka o dostupnosti optike u FTTH planu pokrivanja.' and goes on with the request; "
    "with none it says 'Adresa nije evidentirana u sustavu ili optika nije dostupna. Za potvrdu se "
    "javi koordinatoru za adresne podatke.' The last line leaves the status out",
]
# Both states are reached the way any found record is: an ID, a full address or a conversation.
REACHABLE = [PATHS[0], PATHS[1], PATHS[2], PATHS[5], PATHS[6]]
FIRST_PREFIX = 700  # Week 2 used 100 to 699, so the new IDs cannot collide with rows in the corpus
BATCHES = 4


def build_combos() -> list[dict]:
    combos, fields = [], itertools.cycle(SPECIFIC_FIELDS)
    for state, path, form, intent in itertools.product(NEW_STATES, REACHABLE, FORMS, ("general", "specific")):
        wants = "a general check of the building" if intent == "general" else next(fields)
        combos.append({"intent": wants, "record": state, "path": path, "form": form,
                       **ALWAYS, "outcome": "answered"})
    for number, combo in enumerate(combos):
        combo["ids"] = f"every ADM ID and AAMS number starts with {FIRST_PREFIX + number}"
    return combos


def batches() -> None:
    combos, seeds = build_combos(), load_seeds()
    head, tail = sdg.GENERATION_PROMPT.split("{profile}")
    head = head.format(examples="\n".join(json.dumps(s, ensure_ascii=False) for s in seeds), n=3)
    size = len(combos) // BATCHES
    WORK.mkdir(exist_ok=True)
    for number in range(BATCHES):
        lines = [f"For EACH combination below, answer this prompt once, with its profile in place of {{profile}}:",
                 "", "````text", head + "{profile}" + tail, "````", ""]
        for index in range(number * size, number * size + size):
            lines += [f"## combo {index}", *[f"- {k}: {v}" for k, v in combos[index].items()], ""]
        (WORK / f"batch_{number + 1}.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(combos)} combinations in {BATCHES} batch files under {WORK.relative_to(ROOT)}")
    print("Subagent instruction, as in Week 2:\n" + SUBAGENT_PROMPT)


def merge() -> None:
    corpus = [json.loads(line) for line in CORPUS.read_text(encoding="utf-8").splitlines()]
    if any(row["axes"]["record"] in NEW_STATES for row in corpus):
        sys.exit("already merged: the corpus has rows for the new states")
    combos = build_combos()
    raw, unparseable = [], 0
    for path in sorted(WORK.glob("raw_*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
                raw.append({**{k: v for k, v in row.items() if k != "combo"}, "_axes": combos[int(row["combo"])]})
            except (json.JSONDecodeError, KeyError, ValueError, IndexError):
                unparseable += line.strip().startswith("{")
    groups: dict = {}
    for row in raw:
        groups.setdefault((row["_axes"]["intent"], row["_axes"]["record"]), []).append(row)
    kept = [row for group in groups.values() for row in sdg.dedupe(group)[0]]
    valid = []
    for row in kept:
        try:
            validate({k: v for k, v in row.items() if not k.startswith("_")})
            valid.append(row)
        except Exception:
            pass
    clean = [r for r in valid if r.get("outcome") == "answered"
             and not any(v in r["input"] + r["output"] for v in GOLDEN_VALUES)]
    with CORPUS.open("a", encoding="utf-8") as out:  # appended, so every existing row keeps its line
        for r in clean:
            row = {**{k: v for k, v in r.items() if not k.startswith("_")}, "axes": r["_axes"]}
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"generated {len(raw)} ({unparseable} unparseable) → {len(kept)} after dedupe → {len(valid)} valid → "
          f"{len(clean)} appended; the corpus went from {len(corpus)} to {len(corpus) + len(clean)} rows")


if __name__ == "__main__":
    {"batches": batches, "merge": merge}[sys.argv[1]]()

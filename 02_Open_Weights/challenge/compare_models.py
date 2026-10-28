"""The same 600 combinations written by a second model, Claude Sonnet 5.5, and a comparison with Haiku.

Sonnet did not run through `generate.py` and an API key. It ran as six Claude Code subagents,
each given one batch file with the same prompt, the same five goldens and 100 of the same
combinations, and the instruction in SUBAGENT_PROMPT. Their rows then go through the same
dedupe, validation and leak checks as Haiku's.

    uv run python 02_Open_Weights/challenge/compare_models.py batches   # write the six batch files
    uv run python 02_Open_Weights/challenge/compare_models.py compare   # check Sonnet's rows, compare
"""

import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(Path(__file__).parent)]

from helpers import sdg  # noqa: E402
from generate import build_combos, fix_and_validate, load_seeds  # noqa: E402

DATA = ROOT / "use_case" / "data"
WORK = DATA / "sonnet"  # batch files and the subagents' raw rows; gitignored like the rest of data/

SUBAGENT_PROMPT = """Read batch_N.md. For EVERY combination, do exactly what the prompt asks with that
combination's profile: write 3 NEW examples in the same JSON format as the five examples, in
Croatian, following every line of the profile and every rule in the prompt. Write every row
yourself; do not write or run any script, template or loop that produces rows. No person names.
Invent all IDs with the prefix the profile's `ids` line gives. One JSON object per line:
{"combo": N, "input": ..., "output": ..., "outcome": ...}, written to raw_N_a.jsonl ... raw_N_e.jsonl,
20 combinations per file."""

# The leak check only catches capitalised word pairs and tokens with digits, so it missed the
# goldens' project names written with underscores. These are every distinctive value in them.
GOLDEN_VALUES = ("FTTH_KARLOVAC_3", "FTTH_SINJ_2", "FTTH_ZAGREB_TRNJE", "EUBB_2_Imotski", "4471208",
                 "51873402", "2214637", "Gundulić", "Vukovarska 41", "Trpimirova 8", "Vrbik 23", "Lipovečka")
SCHEMA_STATUSES = {"HOMES CONNECTED", "HOMES PASSED - STREET", "HOMES PASSED - HOUSE", "FTTA ROLLOUT"}


def batches() -> None:
    combos, seeds = build_combos(), load_seeds()
    head, tail = sdg.GENERATION_PROMPT.split("{profile}")
    head = head.format(examples="\n".join(json.dumps(s, ensure_ascii=False) for s in seeds), n=3)
    WORK.mkdir(exist_ok=True)
    for number in range(6):
        lines = [f"For EACH combination below, answer this prompt once, with its profile in place of {{profile}}:",
                 "", "````text", head + "{profile}" + tail, "````", ""]
        for index in range(number * 100, number * 100 + 100):
            lines += [f"## combo {index}", *[f"- {k}: {v}" for k, v in combos[index].items()], ""]
        (WORK / f"batch_{number + 1}.md").write_text("\n".join(lines), encoding="utf-8")


def profile(rows: list[dict]) -> dict:
    addresses: dict = {}
    for row in rows:
        for adm in re.findall(r"ADM ID: (\d+)", row["output"]):
            addresses.setdefault(adm, set()).add(row["output"].split(":")[0])
    statuses = [s.strip() for r in rows for s in re.findall(r"Status: ([^|\n]+)", r["output"])]
    pasted = [r for r in rows if "email" in r["axes"]["form"]]
    starts = Counter(" ".join(r["input"].lower().split()[:2]) for r in rows)
    return {
        "median message / answer length": f'{statistics.median(len(r["input"]) for r in rows):.0f} / '
                                          f'{statistics.median(len(r["output"]) for r in rows):.0f} chars',
        "distinct ADM IDs": len(addresses),
        "an ADM on more than one address": sum(len(v) > 1 for v in addresses.values()),
        "rows that keep the ID prefix": f'{sum(all(i.startswith(r["axes"]["ids"].split()[-1]) for i in re.findall(r"ADM ID: (\d+)", r["output"])) for r in rows) / len(rows):.0%}',
        "pasted emails with a mail header": f'{sum(bool(re.search(r"(Od:|Predmet:|Poslano:|FW:|RE:|Fwd:)", r["input"])) for r in pasted)} of {len(pasted)}',
        "rows with a status the schema lacks": sum(s not in SCHEMA_STATUSES for s in statuses),
        "most common opening": starts.most_common(1)[0],
    }


def compare() -> None:
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
            fix_and_validate(row)
            valid.append(row)
        except Exception:
            pass
    clean = [r for r in valid if r.get("outcome") == r["_axes"]["outcome"]
             and not any(v in r["input"] + r["output"] for v in GOLDEN_VALUES)]
    print(f"sonnet: generated {len(raw)} ({unparseable} unparseable) → {len(kept)} after dedupe → "
          f"{len(valid)} valid → {len(clean)} after removing rows that reuse a golden's values")
    (DATA / "synthetic_sonnet.jsonl").write_text("".join(
        json.dumps({**{k: v for k, v in r.items() if not k.startswith("_")}, "axes": r["_axes"]}, ensure_ascii=False) + "\n"
        for r in clean), encoding="utf-8")

    for name in ("synthetic_v1.jsonl", "synthetic_sonnet.jsonl"):
        rows = [json.loads(line) for line in (DATA / name).read_text(encoding="utf-8").splitlines()]
        print(f"\n{name}: {len(rows)} rows")
        for key, value in profile(rows).items():
            print(f"  {key}: {value}")


if __name__ == "__main__":
    {"batches": batches, "compare": compare}[sys.argv[1]]()

# TC3 submission: Fiberly

Week 3 of the certification for Fiberly: retrieval over the synthetic records from Week 2, measured
against ten real operator questions. Charter: [`use_case/CHARTER.md`](../../use_case/CHARTER.md).

---

## The corpus

Sonnet's synthetic file from Week 2, `use_case/data/synthetic_sonnet.jsonl`, with 298 rows added
for the two record states the Week 1 review found missing: 2075 rows. A record's ID is its line
number, `r0001` to `r2075`, and the file is only ever appended to, so the labels below stay valid.
The data is gitignored; what it is and what it cannot show is in the
[datasheet](../../use_case/data/DATASHEET.md), and the choice is a row in
[`decisions.md`](../../use_case/decisions.md).

```bash
uv run python 03_Retrieval/challenge/topup.py batches   # the batch files the Sonnet subagents wrote from
uv run python 03_Retrieval/challenge/topup.py merge     # their rows, checked and appended
```

## Step 1: ten labelled questions

[`use_case/evals/retrieval.jsonl`](../../use_case/evals/retrieval.jsonl). The questions are real
operator questions from the pilot's regression suite and paraphrase set. The wording is theirs.
The IDs and addresses are swapped for a record in the corpus that is in the same state and is
reached the same way, because the real buildings are not in synthetic data and must not be public.

| | Questions |
| --- | --- |
| By ADM ID | q01 plain check, q02 acquisition, q03 the stopwatch |
| By address | q04 polite sentence, q05 house number with a suffix, q06 typed without diacritics |
| By AAMS number | q07 which ADM a card belongs to, q08 who to escalate to |
| Follow-up | q09 "tko je odgovoran" with the building only in the earlier turn |
| Should decline | q02 the building exists but its acquisition status does not; q10 an address in no record |

Each line also has `expected_terms` and a `favours` prediction, written before any run, in the shape
Session 5's scoring reads. `gold` plays the part of its expected page.

**None of the ten needs more than one record, so the top-k floor is 1.** That is a fact about the
corpus, not the problem: every building was generated in one row, while at work one answer joins two
to six systems, so the real floor is higher.

**What labelling showed about the data:**
- No row in the corpus holds an acquisition status. The Week 2 axis read "whether a new service can be connected", and that is what both models wrote. The pilot's acquisition question became q02, a missing field the answer must admit.
- Only 11 of 2075 rows have a house number with a suffix, and only 2 of them with a slash like 3/2, while the pilot puts 12/1 among its edge cases.
- Many synthetic messages look like the questions themselves ("provjeri adm …"). Whether the index includes the operator's message or only the answer decides how easy the search is, so Step 3 measures both.

**What the ten leave out**, and where it is tested instead: project phase and construction details,
unit counts, clarification questions (no city, a bare number, a similar street), off-topic messages
and injection. These are business rules once the record is found, so they belong to the goldens, the
Week 4 harness and Week 6, not to a retrieval test.

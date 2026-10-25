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

## Step 3: measuring the techniques

Two of the three so far, Session 5's two interfaces over my records. The third comes after Session 6.

```bash
uv run python 03_Retrieval/challenge/corpus.py recall   # retrieval only, no model calls
uv run python 03_Retrieval/challenge/wiki.py build      # the wiki DCI reads
uv run python 03_Retrieval/challenge/measure.py 3        # both approaches, 10 questions, 3 runs, priced in $
```

**Before any model call, retrieval alone** (is the labelled record in BM25's top k, for the 9 questions that have one):

| Tokenizer | Indexed | recall@1 | recall@3 | recall@5 |
| --- | --- | --- | --- | --- |
| Session 5's | the answer | 7 | 8 | 8 |
| Session 5's | message and answer | 6 | 8 | 8 |
| Session 5's | the message | 6 | 7 | 7 |
| diacritics folded | **the answer** | **8** | **9** | **9** |
| diacritics folded | message and answer | 8 | 9 | 9 |
| diacritics folded | the message | 7 | 8 | 8 |

Session 5's tokenizer never finds "Sumska 4 Sibenik" in its top 20. Folding diacritics fixes it. Indexing the operator's message adds nothing, so only the answer is indexed: it is the record, and at work past messages are not part of the source. A plain lookup by the ID in the question finds 6 of the 9; the three addresses need search. For the address that does not exist, BM25 still returns Vinska 14, Ilok at a high score: retrieval never says "nothing".

**The wiki DCI needs** had to be made: one page per record, one page per city, an index of cities. It builds in 0.2 s into 2,388 pages: 2,075 records, 311 cities, the index (12 KB) and a page for records with no building. 52 records with an address written unusually ("Lećevica, Sjenokoša 17") are on no city page and only `grep` reaches them. At work this index would need an owner, and that goes into Step 5.

**Results**, 10 questions × 2 approaches × 3 runs:

| Approach | Pass | Cited the record | Calls | Evidence chars | Latency | $ per question | $ total |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Agentic RAG | 23/30, **28/30** after two label fixes | 27/27 | 2.1 | 2,469 | 4.9 s | $0.00049 | $0.0146 |
| DCI Wiki | 25/30, **27/30** after two label fixes | 27/27 | 3.6 | 12,450 | 6.2 s | $0.00223 | $0.0669 |

| Question | Predicted | Agentic RAG | DCI Wiki |
| --- | --- | --- | --- |
| q01 ADM, empty status | either | 3/3 | 3/3 |
| q02 acquisition, field missing | either | 1/3 | 0/3 |
| q03 stopwatch | either | 3/3 | 3/3 |
| q04 address, polite | RAG | 3/3 | 3/3 |
| q05 house number 3/2 | DCI | 3/3 | 3/3 |
| q06 no diacritics | RAG | 3/3 | 3/3 |
| q07 card to ADM | either | 3/3 | 3/3 |
| q08 contact, no PM | either | 3/3 | 3/3 |
| q09 follow-up | either | 3/3 | 3/3 |
| q10 address not found | DCI | 3/3 | 3/3 |

The per-question columns are after the label fixes. The whole run cost **$0.0816**: 674,054 tokens in and 28,313 out.

**Settings:** `anthropic/claude-haiku-5-5`, temperature 0 as in Session 5, six turns at most. BM25Okapi with its defaults (k1 1.5, b 0.75) over the answer text, diacritics folded and `3/2` kept as one token. `search_chunks` returns 4 records by default, at most 8, each cut at 1,000 characters. `grep_wiki` returns at most 40 lines and `read_page` at most 12,000 characters. Embedding tokens: n/a, because nothing is embedded yet.

**Two labels fixed after reading the traces**, and the same saved answers scored again:
- q08 expected "37 dana" as well as the coordinator. The question asks who is responsible, and all six answers named the coordinator and cited r1793 without repeating the delay. The label now asks only for "koordinator".
- q06 expected "optika interes". RAG found the right record every time but wrote "interes za optiku". The label now asks for "interes".

**What the table says:**
- **Both find the right record.** Every answer that should cite one did, 27 of 27 on each side. On this corpus retrieval is not where Fiberly fails.
- **The one real failure is answering, not finding.** On q02 Haiku reads "zgrada je spojena" and concludes the address is acquired, or hedges, instead of saying the acquisition status is not recorded. Both approaches fetch the right building. The fix belongs in the endpoint's prompt in Step 4: a field the record does not hold is reported as not available.
- **DCI costs 4.5 times as much per question** for one fewer pass: 5 times the evidence and 1.7 times the calls. On q06 its `grep` is exact, "Sumska" does not match "Šumska", and it took five to seven calls to get there by browsing city pages.
- **My predictions for q05 and q06 were wrong.** I expected the suffix to need DCI and the missing diacritics to break it. The folded tokenizer handles both for RAG, and DCI got there at a higher price.
- **Both declined the missing address**, 3 of 3 each, even though BM25 handed RAG a near miss in the same town.

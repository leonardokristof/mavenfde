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

Three techniques over the same records, through Session 5's agent loop: Session 5's two
interfaces, and a hybrid built from Session 6's pieces as the third.

```bash
uv run python 03_Retrieval/challenge/corpus.py recall   # retrieval only, no model calls
uv run python 03_Retrieval/challenge/wiki.py build      # the wiki DCI reads
uv run python 03_Retrieval/challenge/measure.py 3        # three approaches, 10 questions, 3 runs, priced in $
```

**Before any model call, retrieval alone** (is the labelled record in the top k, for the 9 questions that have one):

| Retriever | Tokenizer | Indexed | recall@1 | recall@3 | recall@5 |
| --- | --- | --- | --- | --- | --- |
| BM25 | Session 5's | the answer | 7 | 8 | 8 |
| BM25 | Session 5's | message and answer | 6 | 8 | 8 |
| BM25 | Session 5's | the message | 6 | 7 | 7 |
| BM25 | diacritics folded | **the answer** | **8** | **9** | **9** |
| BM25 | diacritics folded | message and answer | 8 | 9 | 9 |
| BM25 | diacritics folded | the message | 7 | 8 | 8 |
| Dense | multilingual MiniLM | the answer | 0 | 2 | 2 |
| Hybrid, BM25 + dense by RRF | both | the answer | 4 | 4 | 4 |

- **Session 5's tokenizer never finds "Sumska 4 Sibenik"** in its top 20, and folding diacritics fixes it.
- **Indexing the operator's message adds nothing**, so only the answer is indexed. It is the record, and at work past messages are not part of the source.
- **A plain lookup by the ID in the question** finds 6 of the 9.
- **Dense retrieval blurs the identifiers.** An ADM number is one more number in vector space, so it finds the record for none of the ID questions.
- **The hybrid scores below its better parent.** RRF averages ranks, so a record that ranks fifth in both lists beats BM25's exact first place. It ranks the record first only for the polite address, the suffixed address and the contact question.
- **For the address that does not exist**, BM25 still returns Vinska 14, Ilok at a high score. Retrieval never says "nothing".

**The wiki DCI needs** had to be made: one page per record, one page per city and an index of cities. It builds in 0.2 s into 2,388 pages: 2,075 records, 311 cities, the index (12 KB) and a page for records with no building. 52 records with an address written unusually ("Lećevica, Sjenokoša 17") are on no city page, and only `grep` reaches them. At work this index would need an owner, and that goes into Step 5.

**Results**, 10 questions × 3 approaches × 3 runs, 27 October:

| Approach | Pass | Cited the record | Calls | Evidence chars | Latency | $ per question | $ total |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Agentic RAG (BM25) | **29/30** | 27/27 | 2.1 | 2,498 | 3.7 s | **$0.00048** | $0.0145 |
| DCI Wiki | **29/30** | 27/27 | 3.8 | 13,434 | 5.0 s | $0.00244 | $0.0731 |
| Hybrid RAG (BM25 + dense) | 26/30 | 23/27 | 2.3 | 2,620 | 4.0 s | $0.00054 | $0.0161 |

| Question | Predicted | Agentic RAG | DCI Wiki | Hybrid RAG |
| --- | --- | --- | --- | --- |
| q01 ADM, empty status | either | 3/3 | 3/3 | 3/3 |
| q02 acquisition, field missing | either | 2/3 | 2/3 | 2/3 |
| q03 stopwatch | either | 3/3 | 3/3 | **0/3** |
| q04 address, polite | RAG | 3/3 | 3/3 | 3/3 |
| q05 house number 3/2 | DCI | 3/3 | 3/3 | 3/3 |
| q06 no diacritics | RAG | 3/3 | 3/3 | 3/3 |
| q07 card to ADM | either | 3/3 | 3/3 | 3/3 |
| q08 contact, no PM | either | 3/3 | 3/3 | 3/3 |
| q09 follow-up | either | 3/3 | 3/3 | 3/3 |
| q10 address not found | DCI | 3/3 | 3/3 | 3/3 |

The run cost **$0.1037**: 825,421 tokens in and 42,264 out on Haiku. The first run on 25 October, with the two Session 5 techniques, cost $0.0816 and gave 28/30 and 27/30. Between the two runs q02 went from 1/3 and 0/3 to 2/3 and 2/3, so one run of that question is noise, not a result.

**Embedding tokens: 175,930, measured** with the model's own tokenizer for the 2,075 records, plus a few per query. The model runs locally, so it cost $0. 93 records are longer than the model's 128-token limit and were cut. Every change to the chunking means embedding them all again.

**Settings:**
- Model: `anthropic/claude-haiku-5-5`, temperature 0 as in Session 5, six turns at most.
- BM25: BM25Okapi with its defaults (k1 1.5, b 0.75) over the answer text, diacritics folded and `3/2` kept as one token.
- Dense: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` through fastembed, 384 dimensions, cosine. Session 6's default `bge-small-en` is English-only, and the records are Croatian.
- Hybrid: Session 6's reciprocal rank fusion, k = 60, both lists weighted equally. I did not tune it on these ten questions.
- Tools: `search_chunks` returns 4 records by default, at most 8, each cut at 1,000 characters. `grep_wiki` returns at most 40 lines and `read_page` at most 12,000 characters.

**Four labels fixed after reading the traces**, and the same saved answers scored again. Every one was a keyword problem in an answer that was right:
- q08 expected "37 dana" as well as the coordinator. The question asks who, and the answers named the coordinator without repeating the delay. It now asks for "koordinator".
- q06 expected "optika interes", and the answers wrote "interes za optiku". It now asks for "interes".
- q04 expected "Crikvenica", and the answers wrote "u Crikvenici". It now asks for the stem "Crikvenic".
- q01 expected "nema podataka o dostupnosti optike", and an answer wrote "nemam podatke o dostupnosti optike… nema podataka u FTTH planu". It now asks for "nema podataka" and the stem "Vinkovc".

**What the table says:**
- **BM25 RAG and DCI tie on accuracy, and RAG is five times cheaper.** Both pass 29 of 30 and cite the right record every time. DCI reads 5 times the evidence and makes almost twice the calls, so it costs $0.00244 a question against $0.00048.
- **The hybrid is the worst of the three.** On q03 it searched three times, once with the bare number, and never got the record, because the dense half pushes the exact match out of the top four. Haiku said it found nothing and invented nothing. That is the right behaviour, on the wrong retrieval.
- **The one failure all three share is answering, not finding.** On q02 Haiku sometimes reads "zgrada je spojena" and concludes the address is acquired, instead of saying the acquisition status is not recorded. The fix belongs in the endpoint's prompt in Step 4.
- **My predictions for q05 and q06 were wrong.** I expected the suffix to need DCI and the missing diacritics to need DCI's reading. The folded tokenizer handles both for BM25.
- **All three declined the missing address**, 3 of 3 each, even though the search handed them a near miss in the same town.

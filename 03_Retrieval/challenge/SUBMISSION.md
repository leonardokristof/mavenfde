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

**q11 to q15 were added after Step 6.** They are the business owner's own questions, described in Step 6.

**What the ten leave out**, and where it is tested instead: project phase and construction details,
unit counts, clarification questions (no city, a bare number, a similar street), off-topic messages
and injection. These are business rules once the record is found, so they belong to the goldens, the
Week 4 harness and Week 6, not to a retrieval test.

## Step 3: measuring the techniques

Three techniques over the same records, through Session 5's agent loop: Session 5's two
interfaces, and a hybrid built from Session 6's pieces as the third. The fourth row is the pipeline
Step 4 ships, scored with the same labels and the same check.

```bash
uv run python 03_Retrieval/challenge/corpus.py recall   # retrieval only, no model calls
uv run python 03_Retrieval/challenge/wiki.py build      # the wiki DCI reads
uv run python 03_Retrieval/challenge/measure.py 3        # all four, 10 questions, 3 runs, priced in $
uv run python 03_Retrieval/challenge/measure.py 3 Pipeline   # only the endpoint's pipeline
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

**Results**, 10 questions × 4 approaches × 3 runs, 27 October:

| Approach | Pass | Cited the record | Calls | Evidence chars | Latency | $ per question | $ total |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Agentic RAG (BM25) | 29/30 | 27/27 | 2.1 | 2,498 | 3.7 s | $0.00048 | $0.0145 |
| DCI Wiki | 29/30 | 27/27 | 3.8 | 13,434 | 5.0 s | $0.00244 | $0.0731 |
| Hybrid RAG (BM25 + dense) | 26/30 | 23/27 | 2.3 | 2,620 | 4.0 s | $0.00054 | $0.0161 |
| **Pipeline**, the Step 4 endpoint | **30/30** | 27/27 | 1.0 | 254 | 2.3 s | **$0.00021** | $0.0063 |

| Question | Predicted | Agentic RAG | DCI Wiki | Hybrid RAG | Pipeline |
| --- | --- | --- | --- | --- | --- |
| q01 ADM, empty status | either | 3/3 | 3/3 | 3/3 | 3/3 |
| q02 acquisition, field missing | either | 2/3 | 2/3 | 2/3 | 3/3 |
| q03 stopwatch | either | 3/3 | 3/3 | **0/3** | 3/3 |
| q04 address, polite | RAG | 3/3 | 3/3 | 3/3 | 3/3 |
| q05 house number 3/2 | DCI | 3/3 | 3/3 | 3/3 | 3/3 |
| q06 no diacritics | RAG | 3/3 | 3/3 | 3/3 | 3/3 |
| q07 card to ADM | either | 3/3 | 3/3 | 3/3 | 3/3 |
| q08 contact, no PM | either | 3/3 | 3/3 | 3/3 | 3/3 |
| q09 follow-up | either | 3/3 | 3/3 | 3/3 | 3/3 |
| q10 address not found | DCI | 3/3 | 3/3 | 3/3 | 3/3 |

The run cost **$0.1037**: 825,421 tokens in and 42,264 out on Haiku. The first run on 25 October, with the two Session 5 techniques, cost $0.0816 and gave 28/30 and 27/30. Between the two runs q02 went from 1/3 and 0/3 to 2/3 and 2/3, so one run of that question is noise, not a result.

The pipeline ran on its own later the same evening: $0.0063, 37,455 tokens in and 5,121 out. It is not an
agent loop, so its calls are lookups in the store, one per ID or address in the message. It makes two model
calls at most, the parse and the answer to a specific question, and a plain check makes one.

**Embedding tokens: 175,930, measured** with the model's own tokenizer for the 2,075 records, plus a few per query. The model runs locally, so it cost $0. 93 records are longer than the model's 128-token limit and were cut. Every change to the chunking means embedding them all again.

**Settings:**
- Model: `anthropic/claude-haiku-5-5`, temperature 0 as in Session 5, six turns at most.
- BM25: BM25Okapi with its defaults (k1 1.5, b 0.75) over the answer text, diacritics folded and `3/2` kept as one token.
- Dense: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` through fastembed, 384 dimensions, cosine. Session 6's default `bge-small-en` is English-only, and the records are Croatian.
- Hybrid: Session 6's reciprocal rank fusion, k = 60, both lists weighted equally. I did not tune it on these ten questions.
- Tools: `search_chunks` returns 4 records by default, at most 8, each cut at 1,000 characters. `grep_wiki` returns at most 40 lines and `read_page` at most 12,000 characters.
- Pipeline: the Week 1 parse prompt, then a lookup by the exact number or BM25's top 20 for an address with the address check, and at most 4 records for the answer. It calls the model the way the app does, at the provider's default temperature.

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
- **The pipeline passes all 30 at less than half of BM25 RAG's price.** It needs no search for the six ID questions, because every number in the corpus belongs to exactly one record, and the model reads 254 characters on average instead of 2,498. Part of its q02 result is its prompt: it carries the rule for a field no record holds, which the agents' Session 5 prompt does not.

## Step 4: the endpoint

`answer_from_records` in [`app.py`](../../01_Product_Engineering/challenge/app.py), next to the Week 1
endpoint. It is the Week 1 pipeline with the records in place of the nine sample buildings, and it returns
the same `Response`:

1. The model parses the message with the Week 1 parse prompt: an ADM ID, an AAMS or card number, an address, a question back, or off topic.
2. Code finds the records. An ID is looked up exactly, since every number in the corpus belongs to one record. An address goes through BM25, and of its top 20 code keeps only a record whose first line has the same street, house number and city. A near miss never reaches the model.
3. Nothing found: `not_found`, in the Week 1 sentence, with no sources and no second model call.
4. A plain check gets the record's own text word for word, the way Week 1 answers from its template. A specific question gets an answer the model writes from at most four records, and code adds the record's ID line (ADM ID | Status | Naziv projekta) from the record itself.
5. `sources` is set by code. It lists the records the answer was built from, never the ones the model says it used.

[`records.py`](../../01_Product_Engineering/challenge/records.py) holds the records and the two ways into
them, by number and by text. The rest is `solve_from_records` in
[`fiberly.py`](../../01_Product_Engineering/challenge/fiberly.py). Step 3's scripts import the same
`records.py`, so the measurement and the app search the same way. The docstring is written for the agent
that will read it as the whole interface in Week 5.

```bash
cd 01_Product_Engineering/challenge
uv run python app.py

docker build -t challenge .
docker run -p 7860:7860 --env-file ../../.env \
  -v "$PWD/../../use_case/data/synthetic_sonnet.jsonl:/data/corpus.jsonl:ro" challenge
```

**Through the container's API**, 27 October, the ten questions and three more:

| Question | Outcome | Sources | Latency |
| --- | --- | --- | --- |
| q01 ADM, empty status | answered | r1930 | 2.2 s |
| q02 acquisition, field missing | answered | r0305 | 3.1 s |
| q03 stopwatch | answered | r0580 | 2.7 s |
| q04 address, polite | answered | r0316 | 1.0 s |
| q05 house number 3/2 | answered | r0882 | 1.4 s |
| q06 no diacritics | answered | r1263 | 2.1 s |
| q07 card to ADM | answered | r0554 | 4.0 s |
| q08 contact, no PM | answered | r1793 | 3.6 s |
| q09 follow-up | answered | r0670 | 3.9 s |
| q10 address not found | not_found | none | 1.0 s |
| "tko je PM?" with the ADM only in `history` | answered | r0670 | 2.0 s |
| a bare number, 4008845 | needs_clarification | none | 1.2 s |
| a question about restaurants | out_of_scope | none | 1.0 s |

Every source is the labelled record.

**On a decline.** An address in no record, q10, comes back as `not_found` with no sources: "Adresa Kolodvorska
140, Ilok nije evidentirana u sustavu. Provjeri je li ispravno upisana, a za potvrdu se javi koordinatoru za
adresne podatke." No answer model is called. A field no record holds, q02, gets the building with "Taj
podatak nije evidentiran." in front of what the record does say.

**Reading the answers found three things the score did not:**
- The model rewrote the record's ID line. On q08 it labelled AAMS 71004827 as an ADM ID, and on q01 it dropped the AAMS ID. Code now writes that line from the record and removes any the model writes.
- The parser called "je li adresa adm 2063318 akvizirana" a plain check, so the template answer said the building is connected and nothing about acquisition. The Week 1 endpoint had the same flaw. The parse prompt now lists acquisition, the project phase and the number of units as specific questions, and the six goldens still match word for word in 18 of 18 runs.
- In one run of three on q08 the model still turns "nema ga ni projekt" (the project has no PM either) into "nema ni projekta" (there is no project). The score passes it, because it only checks for "koordinator". It goes into the Week 4 harness as a phrase that must not appear.

**Checked without a model:** 1,649 of the 1,653 addresses the wiki can read find their own record through
the address check. The other 4 are not addresses ("AMS 41603851, Ulica"). The same addresses with a house
number 700 higher find nothing, in 1,653 of 1,653. Every ADM ID finds its record, 1,390 of 1,390. The index
over the 1,705 answered records builds in 0.05 s.

**The container** is built from the lock with `rank-bm25` added. It grew by 74 KB, to 807 MB, and runs as
`appuser`. The records are not in the image: they are mounted read-only and the path comes from
`CORPUS_PATH`. Without the mount the app still starts and prints that the records are missing. The new
endpoint then answers `error`, and the Week 1 endpoint keeps working.

Getting here cost about $0.045 in model calls, most of it seven runs of the pipeline while I fixed what
the answers showed.

## Step 5: the decision

The retrieval row and the four answers about non-text content are in
[`decisions.md`](../../use_case/decisions.md).

## Step 6: the demo

I showed the business owner of the tool the first golden example, the question and Fiberly's answer.
Then they wrote five questions of their own, the way they would type them, and said what they expect back.
The questions are in their words, with the ID they made up and the two real addresses they typed swapped
for records in the corpus, as in Step 1:

| | Their question | What they expect back, as they said it |
| --- | --- | --- |
| q11 | Provjeri mi sto je konkretno sa slučajem sa AAMS ID - 27214368 | "da mi sustav konkretno javi što je zadnje rađeno na adresi, odnosno s tim slučajem, koje sve informacije ima, općenito da mi napiše sve što znamo iz sustava o tom slučaju" |
| q12 | Trebam info o adresi Kupska 7, Zagreb | "jednostavna provjera adrese, opet dohvat svega u sustavima i lijep prikaz izlistanja tih informacija, od napomena do općenitih informacija" |
| q13 | Radimo na zgradi u Rijeci, adresa Primorska 28, trebam vise informacija, mozes li vidjet sto sve imamo u sustavu vezano za to. | the same |
| q14 | AAMS ID je 27214368, koji je hakom timer? | the same |
| q15 | ID je 27214368, jel postoji neki timer od hakoma ili nesto drugo sprjecava radove? | the same |

**As they typed them**, the endpoint answered every one correctly. Four came back `not_found`, because the
made-up ID and the two real addresses are not in synthetic data, and none offered a near miss. The bare
"ID" got the question back, "Je li to ADM ID ili AAMS broj?".

**With the swapped records**, 3 runs each:

| Approach | Pass | Cited the record | Calls | Evidence chars | Latency | $ per question |
| --- | --- | --- | --- | --- | --- | --- |
| Agentic RAG (BM25) | 12/15 | 12/12 | 2.1 | 2,679 | 3.9 s | $0.00054 |
| DCI Wiki | 12/15 | 12/12 | 3.3 | 13,562 | 5.4 s | $0.00217 |
| Hybrid RAG (BM25 + dense) | 9/15 | 9/12 | 2.5 | 3,389 | 4.6 s | $0.00067 |
| **Pipeline** | **15/15** | 12/12 | 0.8 | 247 | 2.1 s | **$0.00021** |

- **The decision holds on their questions.** The pipeline passes all 15 at the lowest price, and its plain checks are the records word for word.
- **q15 tests a rule, not retrieval.** The pilot asks back when a number comes without its system, and the pipeline does. The three agents searched the number, found the right record and answered, which in this corpus is right, since no number belongs to two systems. Which of the two the operators want is a question for the next session.
- **The hybrid never found Kupska 7, Zagreb** in three runs and said it had no data. The dense half pushed the exact address out of the top four again.

The run cost $0.0538, and the five questions as typed $0.0008.

**Their answers to the three questions**, after reading the endpoint's answers to their own five: they would
act on them, since they say whom to contact and what the next steps are. The answers and their sources sound
convincing, and they would trust them even without checking, because checking takes too much of their time
today. They had nothing to add.

**What it changed:** their five questions are q11 to q15 in
[`retrieval.jsonl`](../../use_case/evals/retrieval.jsonl), so Week 4 scores them too. All five ask for the
same thing: everything the systems know about the case, listed. The corpus cannot give that, because it
holds no earlier work on a request and no technicians' notes, and a plain check is two or three sentences.
Since they would act on today's answers, that is an improvement for Week 4, not a blocker, with the
request's task history and the notes from Pagesnap as the fields it needs. And because they would not check
the source, the check that a record matches the typed ID or address stays a rule. The rows are in
[`stakeholders.md`](../../use_case/stakeholders.md) and [`decisions.md`](../../use_case/decisions.md).

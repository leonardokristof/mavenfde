# Datasheet

## What this data is

**Generated on:** 2026-10-19
**Generated from:** the response schema in `01_Product_Engineering/challenge/schema.py`, my five hand-written goldens in `use_case/evals/golden.jsonl` and the axes written out in `02_Open_Weights/challenge/generate.py`. No real record went in.
**Rows:** 1794, in `synthetic_v1.jsonl`. Each row has the operator's message (`input`), the answer Fiberly should give (`output`), the expected `outcome`, and the axis values it was generated from (`axes`).
**Kind:** prototyping. Haiku wrote both the messages and the answers, and nobody who judges Fiberly for real has checked an answer, so the dates, deadlines and contacts in them are plausible, not true. The only rows with answers a person accepted are the five goldens in `use_case/evals/golden.jsonl`, and they are not in this file.

## Variation axes

Two axes decide the answer: what the operator wants and what the record says. Two must not change it once the record is found: how the operator reaches the record and how the message is written. The code in `generate.py` holds the same list, with the combinations that make no sense taken out.

| Axis | Values | Why it's here |
| --- | --- | --- |
| Intent (what the operator wants) | a general check of the building · one specific field, taken in turn from nine: HAKOM stopwatch, request status and how long, who is responsible or the PM, acquisition, number of units and building type, optika interes or regular request, technical acceptance, project phase, a cross-reference between ADM and AAMS · out of scope: **personal data of the end customer (must be declined)**, prompt injection inside a valid request, SQL in the message, an unrelated question, a greeting or empty message, a request to change data | Code writes a general check from the template and the model answers a specific field, so this axis decides which half of Fiberly runs and whether the model gives one field instead of the whole overview. |
| Record state | **not found** · **needs clarification:** address without city, two similar streets, two records for one building, a bare number · **answered:** routine without a request, open request within its deadline, active stopwatch, past the SLA deadline with escalation, parked request, several requests or a live record next to an old duplicate, field data and network status disagree, optika interes instead of a request, design or FTTA rollout without a timeline, mini project, address only in the fallback table | Each state needs a different answer. The first level maps one to one onto `Response.outcome`, and "not found" is the case the pilot calls the most important one. |
| Path to the record | ADM ID · AAMS number (tiket) · full address · address without city · bare number · follow-up on a record found earlier · reply to the assistant's question · several IDs in one message | Each one takes a different branch in the parser and the lookup. Once the record is found, it must not change the answer. |
| Form of the message | short and clean · full polite sentence · typos and no diacritics · colloquial · pasted from an email or a ticket with the noise in it | This is how operators actually type. It must change nothing. |

On every row: Croatian the way operators write, no person names (roles only), and its own ID prefix so the IDs of different combinations can't collide.

Combinations taken out, because they would only teach the generator nonsense: an address without a city and a bare number always lead to a question back. An AAMS number only goes with states that have a request. Duplicates only come in through an ADM or an address. Several IDs only go with routine and "not found". A follow-up needs a record found earlier. The fallback table only holds addresses. Out-of-scope messages carry no ID, except the prompt injection, which carries a valid ADM to see whether the real part is still answered.

## How it was generated

| Count | |
| --- | ---: |
| Combinations | 600 (475 answered, 50 not found, 50 needs clarification, 25 out of scope) |
| Generated | 1800, none unparseable |
| After dedupe | 1796 |
| Schema-valid | 1796 |
| Dead combinations | 0 |
| Removed after the leak check | 2, so 1794 kept |

**Settings:**
- Claude Haiku 5.5 through my personal key, 3 rows per combination, all five goldens shown as examples.
- Temperature and top-p at the provider's default, because Haiku 5.5 rejects any other temperature (measured in Session 3). The variety comes from the axes, not the sampler.
- Dedupe on character 4-grams of the input, Jaccard threshold 0.7, compared only within the same intent and record state.
- 20 calls at a time, 120 s timeout, 3 retries.
- 776k tokens in and 1.19M out, about five minutes.

Validation uses the real `Request` and `Response` models, the same ones the endpoint uses. Every row also matched the outcome its combination asked for, but that check is weak, because the outcome is written in the prompt and the model copies it. It only catches broken rows.

An earlier run on the same day was thrown away for two reasons:
- The out-of-scope rows carried an ADM, so "pozdrav, ADM 6630142" was labelled out of scope while Fiberly should answer it.
- Haiku reused the same ADM ID for 97 different buildings.

The ID prefix and the "no ID" path for out-of-scope messages fixed both.

126 rows carry a status the schema doesn't have, most often "IN DESIGN" (41). The axis value "in design or FTTA rollout, with no timeline" names a state the schema has no status for, so the model makes one up. They are kept, and the value needs a status named before the next run.

A second file sits beside this one: `synthetic_sonnet.jsonl`, 1777 rows. Claude Sonnet 5.5 wrote the same 600 combinations as six Claude Code subagents, and the rows went through the same checks. The 14 rows that reused a golden's project names or street were removed. Which file Week 3 uses is still open. The comparison is in `02_Open_Weights/challenge/SUBMISSION.md`, and everything above describes Haiku's file.

## What it can validate

- That Fiberly's parser finds the record however the operator gets to it: ADM, AAMS, a full address, an address without a city, a bare number, a follow-up or a reply inside a conversation, several IDs in one message.
- That typos, missing diacritics, colloquial Croatian and pasted email noise don't break it.
- That every message and answer fits the same `Request` and `Response` the endpoint uses.
- That out-of-scope messages get a refusal or a redirect, and a request for a customer's personal data is always declined.
- The shape of the answer for each state: one question back when the city is missing, both options when two streets match, no deadline for a parked request. The shape, not the facts in it.

## What it cannot validate

- **Whether an answer is right.** Haiku made up every date, deadline, stopwatch expiry and contact. Fiberly's code computes these from the data, and nothing here was computed that way, so a row can look perfect and carry the wrong deadline.
- **Whether Fiberly trusts the field it was given.** When the field data and the network status disagree, code applies "the field data is newer" and hands the model the result. Haiku only wrote what such an answer should look like, so whether the model repeats the computed field or the raw one shows up only when the app answers these messages, in Week 4.
- **How often anything happens.** 79 % of the rows are answered because that is how I built the combinations, not because operators ask that way. How many messages are really "not found", or have typos, only the 107 real questions from the pilot can say.
- **The app end to end.** The ADM and AAMS numbers are invented and are not in `sample_data.json`, so Fiberly would answer "not found" to all of them. These rows test the parser and the answer's form, not the lookup.
- **Anything outside the axes.** Screenshots, messages in English, two questions in one message, voice messages typed out. None was generated, so none can fail.

## What it must never be compared against

The real answers live in the six internal systems Fiberly reads from (the address register, the network status, AAMS and the rest) and in the pilot's test material: 107 real operator questions and 89 regression scenarios, kept outside this repository and never used here. These rows are none of that. A score on them is not Fiberly's accuracy, and it must never sit in the same table as a score from the pilot's questions.

## Leakage check — outward (what left)

- [x] No real record was used as a seed. The seeds are my five goldens, written by hand around invented buildings. Their format and rules follow a real export from the source applications, but no address, ID or project name in them comes from it.
- [x] No real entity names, IDs, or identifiers appear. The IDs are invented. The streets are real street names, very common ones, with house numbers no one checked against the register.
- [ ] No distinctive internal formats that would identify the firm. Not ticked on purpose. Every answer uses the pilot's template: HT's status codes (HOMES PASSED - STREET), task names, the project naming pattern and the summary line. Anyone in Croatian FTTH would recognise HT. The repo names HT openly, and the format is what Fiberly is tested on, so it stays.
- [x] Rare categories were generated, not copied. The mini project, the fallback-table address and the conflicting sources each come from a one-line description, not from a real case.

The automatic check (`sdg.leak_check`) flagged HOMES PASSED, HOMES CONNECTED and 2026. Those are status codes and the year, not leaks.

**What I removed, and why:**
- The row with a sender at `aams.hrt.hr`. That is a real organisation's domain next to the name of an internal system.
- The row with a sender at `ispostava.hr`. It is a real-looking Croatian domain that could belong to someone.

I read fifty rows from every record state, intent, path and form (`read_50.md`, kept local) and removed nothing. I looked for:
- person names (in the first run one slipped through as a sign-off; in this one every name-like hit was a street);
- email addresses, phone numbers and OIBs;
- whether an operator would really write the message, and whether the answer is the one Fiberly should give.

## Leakage check — inward (what the eval shares with the training data)

**Are the goldens disjoint from anything the system was, or will be, tuned on?**
No, they overlap in two places.
- **The code.** All five goldens are plain checks, and their answers use the same pilot template the code in `fiberly.py` writes them from. That is on purpose, because the template is the spec. But it means the goldens check that Fiberly follows the template, not that the template tells the operator the right thing.
- **The data.** The goldens are the seeds of this file, and Week 8 fine-tunes on this file. From then on the model has learned from the goldens' wording, and they no longer measure it independently. Before Week 8 I need goldens that nothing was generated from.

**Overlap between `golden.jsonl` and this file, by the dedupe measure:** 0 rows at 0.7. The closest is 0.65, conversations that copy the shape of golden 4. At 0.5 there are 10 rows, at 0.4 there are 24.

## Week 3: the corpus retrieval runs over

**File:** `synthetic_sonnet.jsonl`, 2075 rows. Sonnet's 1777 rows from Week 2, then 298 rows for two record states the Week 1 review showed were missing: an overdue request with no PM or AM on the address, and a building with an empty fibre status.
**Why this file and not `synthetic_v1`:** Sonnet's messages read more like the ones operators send, its IDs never collide, and the 14 rows that reused the goldens' values were already taken out in Week 2.
**How the 298 were made:** `03_Retrieval/challenge/topup.py` builds 100 combinations, the two new states crossed with the Week 2 paths, forms and intents, and four Sonnet 5.5 subagents in Claude Code wrote three rows each, with the same instruction as in Week 2. The axes are Week 2's, and IDs start at prefix 700 so they cannot meet the old ones. They went through the same checks: 301 written, 0 unparseable, 299 after dedupe, 299 schema-valid, 298 after removing a row that reused a golden's value.
**What I checked by hand on the new rows:**
- all 150 empty-status rows carry the pilot's sentence word for word, 107 with an open request and 43 without, and none prints a status;
- the overdue rows name the project's PM or AM or the coordinator for requests, except a few that answer only the one field they were asked about;
- no 6-digit or longer ID appears in more than one row of the whole file. Two rows use a prefix one digit off, and their IDs are still unique;
- no person names. The one hit was the town Vela Luka.

**Record IDs:** a row's ID is its line number, `r0001` to `r2075`. The labels in `use_case/evals/retrieval.jsonl` and the `sources` in every answer point at these IDs, so the file is only ever appended to, never regenerated or reordered. SHA-256 of the 2075-row file: `e93591ae1313b4f7388e08e256be8f0d33be0758ba0d1be0426d507c538402db`.

**What this corpus cannot show:** every building sits in one row, so a question that needs two records is rare here, while at work one answer joins two to six systems. And each row is an answer, not a source record, so it stands in for the tables Fiberly would read by key.

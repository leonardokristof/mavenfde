# TC2 submission: Fiberly

Week 2 of the certification for Fiberly: synthetic operator questions for the assistant from
Week 1, generated from my five goldens across axes I named, with a datasheet that says what
they can and cannot prove. Charter: [`use_case/CHARTER.md`](../../use_case/CHARTER.md).

Run it:

```bash
uv run python 02_Open_Weights/challenge/generate.py --dry-run   # combinations and three prompts, no calls
uv run python 02_Open_Weights/challenge/generate.py             # the full run, about five minutes
```

The data itself, `use_case/data/synthetic_v1.jsonl`, is gitignored. The datasheet is
[`use_case/data/DATASHEET.md`](../../use_case/data/DATASHEET.md).

---

## Step 1: the axes

Four axes, in [`generate.py`](./generate.py) and in the datasheet's table. Two decide the
answer, two must not change it once the record is found.

| Axis | What real variation it covers |
| --- | --- |
| Intent | A general check, one specific field (nine of them, from the stopwatch to who the PM is), or out of scope. Code writes a general check and the model a specific field, so this decides which half of Fiberly runs. The decline: a request for the end customer's personal data. |
| Record state | Not found, needs clarification (no city, two similar streets, two records for one building, a bare number) or answered, with eleven states from routine to a parked request or sources that disagree. The first level is `Response.outcome`. |
| Path to the record | ADM, AAMS, full address, address without city, bare number, follow-up, reply to the assistant's question, several IDs. Each takes a different branch in the parser. |
| Form | Short, polite, typos without diacritics, colloquial, pasted email noise. How operators actually type. |

Combinations that make no sense are taken out in `makes_sense()`. For example, an AAMS number
only goes with states that have a request, and an address without a city always leads to one
question back. The axes came from going through the pilot's router branches and its tests:
there are three ways to continue a conversation, not one, about fifteen real intents, and "not
found" is the case the pilot calls the most important.

## Step 2: generate, dedupe, validate

| Count | |
| --- | ---: |
| Combinations | 600 |
| Generated | 1800, none unparseable |
| After dedupe | 1796 |
| Schema-valid | 1796 |
| Dead combinations | 0 |

Claude Haiku 5.5, temperature and top-p at the provider default (Haiku 5.5 rejects any other
temperature, measured in Session 3), 3 rows per combination, all five goldens as examples.
Dedupe is on character 4-grams at 0.7, compared only within the same intent and record state.
Validation uses the endpoint's own `Request` and `Response`. It took about five minutes with 20
calls at a time, 776k tokens in and 1.19M out.

To make that possible I changed `helpers/sdg.py`'s `generate()` in four places. It now takes a
list of combinations, shows all the seeds, runs calls in parallel and dedupes by group. Its
defaults behave as before, and the tests pass.

The first run was thrown away. The out-of-scope rows carried an ADM ("pozdrav, ADM 6630142"
labelled out of scope, which Fiberly should answer), and Haiku gave 97 different buildings the
same ADM. A path with no ID for out-of-scope messages and an ID prefix per combination fixed
both. The dedupe threshold is a row in [`use_case/decisions.md`](../../use_case/decisions.md).

## Step 3: leak check and fifty rows

I read fifty rows covering every record state, intent, path and form, and removed none. I looked
for person names, email addresses, phone numbers and OIBs, and for whether an operator would
really write the message. A scan of all 1796 rows found two senders at real-looking Croatian
domains, `aams.hrt.hr` and `ispostava.hr`, and both rows went, which leaves 1794. The automatic
check only flagged the status codes and the year. The box for "no distinctive internal formats"
stays unticked on purpose: the answers use the pilot's template, which anyone in Croatian FTTH
would recognise, and that template is what Fiberly is tested on.

## Step 4: the datasheet

The data is prototyping data. Haiku wrote the answers and nobody has checked one, so the facts
in them are plausible, not true. The datasheet says what that means:
- it cannot show whether an answer is right;
- it cannot show whether Fiberly trusts the computed field when sources disagree;
- it cannot show how often anything really happens;
- it cannot test the app end to end, since the invented IDs aren't in `sample_data.json`;
- it cannot show anything outside the axes.

The goldens are not disjoint from the system: the code writes the same template they use, and
Week 8 fine-tunes on data seeded from them. None of the 1794 rows is within 0.7 of a golden.
The model and endpoint decision is in `use_case/decisions.md`.

## Step 5: the app on a local model

Fiberly from Week 1, run on `qwen3:8b` through Ollama on my laptop (Apple M5, 16 GB) instead of
Claude Haiku 5.5. The whole change:

```diff
- LLM_MODEL=anthropic/claude-haiku-5-5
+ LLM_MODEL=ollama/qwen3:8b
+ LLM_API_BASE=http://localhost:11434
```

No code changed. What happened, measured through the app's own endpoint:

| | Claude Haiku 5.5 | qwen3:8b, local |
| --- | --- | --- |
| Goldens, word for word | 5 of 5 | 5 of 5 |
| Time per question | 0.9 to 2.5 s | 12.6 to 29 s |
| Follow-up without an ID ("tko je PM?") | right | right, 24.7 s |
| Bare number, then "aams" | found the request | said it wasn't in the system |
| Typo in a street name ("vrbnik 23 zagreb") | asked "Jesi li mislio Vrbik 23?" | timed out after 60 s |

The goldens still pass because plain answers are built by code; the model only reads the
question. The swap found two weak spots in my code. The local model returned an AAMS number as
text instead of a number, so the lookup missed it; `fiberly.py` now accepts both. And the 60 s
timeout, which is also my p95 target, is too short for a local model that thinks before it
answers. Whether a local model is a realistic path at HT is in
[`use_case/ecosystem.md`](../../use_case/ecosystem.md).

## Step 6: show it to someone who knows the real data

Not done yet. Nobody who sees real operator questions could look at the rows this week. A
meeting with the business owner of the tool is planned by Friday, 23 October 2026, to show
twenty rows and the datasheet and ask the three questions. Until then the axes and the rows
stay as they are, which is logged in
[`use_case/stakeholders.md`](../../use_case/stakeholders.md) and `use_case/decisions.md`.

## Bring it to work

The project and the three swap lines are under `## Bring it to work` at the end of the
[challenge README](./README.md). In short: the company's internal AI platform sat ready to
deploy while its GDPR review went back and forth. This week's lesson is to agree first, with
Legal, which data may go to an LLM and how, using concrete examples, and only then write the
document.

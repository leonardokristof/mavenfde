# TC7 submission: Fiberly

Charter: [`use_case/CHARTER.md`](../../use_case/CHARTER.md).

- **The kind:** episodic. Fiberly now keeps a log of what it did on every request, written by code from what it saw, and can tell an operator's request back without a model.
- **Rejected:** semantic, because a remembered building status is a copy that goes stale, and an old status stated with confidence is the worst thing this tool can do. Procedural, because the flow is fixed and there are no wrong turns to skip. A vector store and FTS, because the log is read by operator and time, not by meaning. The full row is in [`decisions.md`](../../use_case/decisions.md).
- **Staleness:** validity in time, not supersede. An episode is true about its moment and is never overwritten; the live status is always read fresh from the records, and nothing in the log goes into the answer.
- **Tests:** staleness, cost, truthfulness and leakage, all passing on Haiku, and each one caught the break it is there for when I broke the memory on purpose.
- **Before and after:** `outcome` 0.87 before, 0.88 after (95% CI 0.81 to 0.94, n=85), `compare()` PASS. Memory did not make the answers worse, because it never reaches them.

## What I built

Every request on the records endpoint writes one row to SQLite at the end of `solve_from_records` in
[`fiberly.py`](../../01_Product_Engineering/challenge/fiberly.py): the time, the operator, the message, the
lookups the parser asked for, the records as they read at that moment, the outcome, the refusal, whether the
facts rail stopped text, and the tokens, cost and seconds. Before this, one printed line per request went
away with the terminal.

`why(operator, at)` reads the operator's last row at or before a moment and tells it back with no model call:

```
24.11.2026. u 19:02 pitao si: "provjeri adm 2005184".
Tražio sam ADM 2005184.
Zapis r0298 je tada glasio: ADM ID: 2005184 | Status: HOMES PASSED - HOUSE | Naziv projekta: FTTH_CAKOVEC_1
Ishod: answered.
```

The model writes nothing into the log. In Session 13 an episode the model wrote recorded a check no tool
made, five of five runs, and that is the audit trail the business owner must not get. `Request` has a new
`operator_id`, set by the app from the login, never typed. The log lives in `use_case/data/`, which git ignores.

## The tests

[`use_case/evals/memory.py`](../../use_case/evals/memory.py), run by `run.py` with everything else and gated
like `blocks_injection`: if one fails, nothing is saved. They swap the record Fiberly reads, never the model,
so each episode comes from a real request on Haiku: three requests, $0.0006.

| Test | What it asserts | Result |
| --- | --- | --- |
| Staleness | The record's status changes from HOMES PASSED - HOUSE to HOMES CONNECTED. The latest explanation gives the new status only; asked about the earlier moment, it gives the old one | pass |
| Cost | Answering took 1 model call and 1.1 s; explaining it from the episode took 0 and 1.3 ms | pass |
| Truthfulness | Every claim in the explanation is in what Fiberly was actually handed, recorded by a separate observer. A planted claim ("Provjerio sam i AAMS 4471") is caught | pass |
| Leakage | Two operators ask the same question. The second sees nothing from before it asked, and an operator who never asked sees nothing | pass |

Every test also needs all three requests answered. The first run went to a model that rejected the request,
and two tests passed on the errors; that is fixed.

## Breaking the memory on purpose

| Break | What failed |
| --- | --- |
| The lookup ignores the operator | leakage |
| Only the latest episode kept, the old one overwritten | staleness, leakage |
| The model's account added to the explanation ("vertikala je gotova za 3 dana") | truthfulness |

## Recall at 10 to 100,000 episodes

`python memory.py` from `use_case/evals`, no model. Each question asks for an operator's request after every
other operator has asked again, so a lookup that ignored the operator would return someone else's.

| Episodes | Operators | Asked | Right row | Another operator's | Median |
| --- | --- | --- | --- | --- | --- |
| 10 | 2 | 10 | 10 | 0 | 0.09 ms |
| 100 | 10 | 100 | 100 | 0 | 0.08 ms |
| 1,000 | 100 | 200 | 200 | 0 | 0.11 ms |
| 100,000 | 10,000 | 200 | 200 | 0 | 4.0 ms |

Accuracy does not move with size, because the lookup is exact. Time starts to grow at 100,000 rows because the
table has no index. At the pilot's 11 requests a day that is about 25 years away, so the index on operator and
time waits until the delay is noticeable. With the lookup broken to ignore the operator, the same check gives
the right row 0 of 200 times and another operator's 200 of 200 at 1,000 episodes.

## The business owner

Asked by message after the 23 November meeting, in [`stakeholders.md`](../../use_case/stakeholders.md): he has
no confirmed case of anyone asking why Fiberly answered, but wants it to say which system, which record and why
it could not answer. That is what the log holds. No memory about a person until purpose, scope and retention
are approved, and an operator's region or team, if it matters, comes from the identity system.

## Share: waiting

**Not done yet.** The case is sent to a colleague: the Session 13 episode that recorded a check no tool made,
with three questions, the first one asked before I say where the false part is.

## What it does not do

- The app has no login yet, so the frontend sends no `operator_id`. Its requests are logged with no operator, and `why()` returns them to nobody.
- Only the records endpoint is logged; the sample endpoint with the nine Week 1 buildings is not.
- `why()` has no endpoint yet, on purpose. An endpoint that takes the operator as an argument would let anyone read another operator's requests, and as an MCP tool any agent could. It waits for the login, the Entra ID sign-in the deployment already plans, so the operator comes from the session, and for an audit role, as the business owner asked.

## Verified

Run on 24 November 2026 from `use_case/evals`, Fiberly on Haiku 5.5 and the judge on Sonnet 5.5.

- `memory.run()` alone: four of four pass. $0.0006.
- `run.py`: both gates and the four memory tests passed, `blocks_injection` 20 of 20, `compare()` PASS on the 105 cases both runs share, every score within 0.01 of the baseline. Baseline not overwritten. $0.5712.
- `python memory.py`: the recall table above, and the same check with the lookup broken.
- The three breaks above, each with a stand-in model.

Hosted cost for the week's challenge: $0.57.

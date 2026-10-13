# Decision log

One row per architectural decision, with the option you rejected and why.

> **Week 5 asks you to defend your agent architecture against the alternatives.**
> **Week 10's handoff doc is largely this file.** Both are much easier if you
> wrote the reasoning down while you still remembered it.

A decision without a rejected alternative is not a decision, it is a default.
If you cannot name what you did not do, you did not choose.

| Week | Decision | What you rejected | Why | What would change your mind |
| --- | --- | --- | --- | --- |
| 1 | Agent or pipeline: an agent, but only at the front. The model reads the messy question, resolves it to buildings or requests with lookup tools (retrying only when it has a reason, asking back when it is ambiguous) and writes the answer. Code fetches all six sources and computes the stopwatch, deadlines and contacts. A fixed pipeline (regex for IDs plus an address lookup) stays as the baseline. | A plain function with no model deciding any step. Also the pilot's first design, where the model wrote its own SQL and chose what to fetch. | All four questions came out yes. The number of lookups depends on the input (one ID, an address with typos, several addresses in one message, a follow-up with no ID), resolving it has to call systems, retry with a reason and ask back, and the inputs cannot be listed in advance. Fetching and business rules stay in code so the facts are the same every time and can be tested, and the model-written SQL from the pilot is replaced by read-only, parameterised lookup tools. | If the fixed baseline resolves the right building as often as the agent on the 107 pilot questions and the 89 regression scenarios, I drop the agent and keep the function: cheaper, deterministic and easier to get approved. |
| 3 | <!-- retrieval approach --> | <!-- --> | <!-- --> | <!-- --> |
| 5 | <!-- agent architecture --> | <!-- --> | <!-- --> | <!-- --> |
| 6 | <!-- guardrail level --> | <!-- --> | <!-- --> | <!-- --> |
| 7 | <!-- memory type --> | <!-- --> | <!-- --> | <!-- --> |
| 8 | <!-- model --> | <!-- --> | <!-- --> | <!-- --> |

**Strongest case against the Week 1 verdict.** About 46% of pilot questions
already carry an ADM or WWMS number that a regex catches, and almost all the
rest are addresses that a fuzzy match plus one clarifying question would
resolve. Everything after that is fixed code anyway, so the "agent" is one
lookup step, and a function with a fixed cost per request and outputs you can
diff would be cheaper to run and easier to approve.

---

The last column is the one people skip and the one people ask about. "We chose
dense retrieval; we would switch to hybrid if exact-match queries went above ~20%
of traffic" is an engineering position. "We chose dense retrieval" is a
preference.

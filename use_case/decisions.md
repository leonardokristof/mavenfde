# Decision log

One row per architectural decision, with the option you rejected and why.

> **Week 5 asks you to defend your agent architecture against the alternatives.**
> **Week 10's handoff doc is largely this file.** Both are much easier if you
> wrote the reasoning down while you still remembered it.

A decision without a rejected alternative is not a decision, it is a default.
If you cannot name what you did not do, you did not choose.

| Week | Decision | What you rejected | Why | What would change your mind |
| --- | --- | --- | --- | --- |
| 1 | Agent or pipeline: a pipeline. The flow is fixed and the model does only the two steps that need language. First it turns the operator's free text into an ADM ID, a WWMS number or an address, using read-only lookup tools and asking back when something is unclear. At the end it writes the answer. In between, code fetches the six sources and applies the stopwatch, deadline and contact rules. The pilot already works this way. | A full agent that decides on its own which systems to query and in what order, like the pilot's first version where the model wrote its own SQL. | All four questions came out yes, but every yes comes from understanding the input: typos, follow-ups without an ID, several addresses in one message. Once the building is known, the path is always the same, so code runs it. The facts come out the same every time, the rules can be tested on their own, and Information Security only has to approve a few read-only tools. | If the 107 pilot questions and the 89 regression scenarios show a lot of questions the fixed path can't answer, like comparing two buildings or needing a source only in some cases, I let the model pick the next tool. |
| 3 | <!-- retrieval approach --> | <!-- --> | <!-- --> | <!-- --> |
| 5 | <!-- agent architecture --> | <!-- --> | <!-- --> | <!-- --> |
| 6 | <!-- guardrail level --> | <!-- --> | <!-- --> | <!-- --> |
| 7 | <!-- memory type --> | <!-- --> | <!-- --> | <!-- --> |
| 8 | <!-- model --> | <!-- --> | <!-- --> | <!-- --> |

**Strongest case against the Week 1 verdict.** All four boxes are ticked, and
the questions keep changing shape: a follow-up about the PM, fifteen addresses
on one street, a WWMS number typed as a ticket or a card. With a fixed pipeline
every new kind of question means changing code by hand, while an agent with the
same read-only tools could combine them on its own and cover cases nobody has
written a path for yet.

---

The last column is the one people skip and the one people ask about. "We chose
dense retrieval; we would switch to hybrid if exact-match queries went above ~20%
of traffic" is an engineering position. "We chose dense retrieval" is a
preference.

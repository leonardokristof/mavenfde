# Decision log

One row per architectural decision, with the option you rejected and why.

> **Week 5 asks you to defend your agent architecture against the alternatives.**
> **Week 10's handoff doc is largely this file.** Both are much easier if you
> wrote the reasoning down while you still remembered it.

A decision without a rejected alternative is not a decision, it is a default.
If you cannot name what you did not do, you did not choose.

| Week | Decision | What you rejected | Why | What would change your mind |
| --- | --- | --- | --- | --- |
| 1 | Agent or pipeline: a pipeline. The flow is fixed and the model does only the two steps that need language. First it turns the operator's free text into an ADM ID, an AAMS number or an address, using read-only lookup tools and asking back when something is unclear. At the end it writes the answer. In between, code fetches the six sources and applies the stopwatch, deadline and contact rules. The pilot already works this way. | A full agent that decides on its own which systems to query and in what order, like the pilot's first version where the model wrote its own SQL. | All four questions came out yes, but every yes comes from understanding the input: typos, follow-ups without an ID, several addresses in one message. Once the building is known, the path is always the same, so code runs it. The facts come out the same every time, the rules can be tested on their own, and Information Security only has to approve a few read-only tools. | If the 107 pilot questions and the 89 regression scenarios show a lot of questions the fixed path can't answer, like comparing two buildings or needing a source only in some cases, I let the model pick the next tool. |
| 1 | Who writes the answer: code, for a plain check of an address, ADM ID or AAMS number, using the response template's sentences word for word. The model writes the answer only when the operator asks something specific, like "tko je PM?". | The Step 6 plan, and the pilot's design: the model writes every answer from facts that code worked out. | In the Step 8 tests the model rewrote the stopwatch sentence and broke the format of golden 3 in 3 of 3 runs. With code writing plain checks the five goldens match word for word in 15 of 15 runs, and a plain check needs one model call instead of two (median 1.2 s). | If operators in the Step 12 demo find the template answers too stiff, or if many questions mix a plain check with a specific question in one message. |
| 1 | After the review with the field services, operations and construction representative: keep the scope and the five goldens as they are. | Changing the goldens before more people have seen them. | He asked for this tool, the use case was worked out with him, and he accepted all five golden examples; none was rejected. | If operators who would use it every day reject an answer or a golden in a longer test. |
| 2 | Model and endpoint. Synthetic data is generated with Claude Haiku 5.5 through my personal key, because every input is invented. Real data only ever goes to the company's approved endpoint, Claude Sonnet 5.5 on the company's Azure, or to a model running inside HT. | Small local models for generation. Sending any real record to a hosted model outside the company. | *Constraint:* real HT data may only go to an approved company endpoint (Information Security, DPO). *Constraint:* Haiku 5.5 rejected temperature 0.7, so its sampler can't be pinned (*measured*, S3 Task 9). *Measured:* hosted 1.66 s, 75 in / 109 out tokens; local LFM2.5-350M 18.45 s for 110 tokens on CPU, Apple M5, 16 GB. *Measured:* LFM2.5-350M wrote no usable Croatian at any temperature; Qwen3-1.7B wrote Croatian but repeated itself. *Looked up:* Haiku 5.5 costs $0.10 / $0.50 per 1M tokens. *Preference:* Haiku's Croatian reads naturally. | A local model of 4B or more that writes Croatian operator messages as varied as Haiku's would move generation onto the laptop. Access to the company endpoint would move generation there too. |
| 2 | Temperature ceiling for local generation. Qwen3-1.7B: usable messages drop to 1 in 8 at temperature 1.0, none from 1.6; below 1.0 it repeats one sentence. LFM2.5-350M: no usable range in Croatian. | Generating with the course's 350M default. | *Measured* on an Apple M5, 16 GB, GPU (MPS), float16: 8 samples per temperature (0.3 to 2.0), top-p 1.0, seed 7, up to 40 new tokens, an invented prompt in Croatian; samples read and judged by hand. | A 4B or 8B model that keeps quality above temperature 1.0. |
| 3 | <!-- retrieval approach --> | <!-- --> | <!-- --> | <!-- --> |
| 5 | <!-- agent architecture --> | <!-- --> | <!-- --> | <!-- --> |
| 6 | <!-- guardrail level --> | <!-- --> | <!-- --> | <!-- --> |
| 7 | <!-- memory type --> | <!-- --> | <!-- --> | <!-- --> |
| 8 | <!-- model --> | <!-- --> | <!-- --> | <!-- --> |

**Strongest case against the Week 1 verdict.** All four boxes are ticked, and
the questions keep changing shape: a follow-up about the PM, fifteen addresses
on one street, an AAMS number typed as a ticket or a card. With a fixed pipeline
every new kind of question means changing code by hand, while an agent with the
same read-only tools could combine them on its own and cover cases nobody has
written a path for yet.

---

The last column is the one people skip and the one people ask about. "We chose
dense retrieval; we would switch to hybrid if exact-match queries went above ~20%
of traffic" is an engineering position. "We chose dense retrieval" is a
preference.

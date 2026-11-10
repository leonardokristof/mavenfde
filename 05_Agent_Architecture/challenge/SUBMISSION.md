# TC5 submission: Fiberly

Week 5 of the certification for Fiberly: the endpoint from Week 3, built a second way and measured
against the first on the same systems. Charter: [`use_case/CHARTER.md`](../../use_case/CHARTER.md).

**What changed after critique.** No room questioned me, because I presented Session 9 as a video, so I
answered the rubric's questions in writing and marked two as fair. The first was how much data each call
returns and what that costs. I had only ever measured the corpus records, so this week Fiberly reads the
systems themselves, rebuilt with invented data, and I measured both ways at the pilot's size and above
it. The answer put a size into the switch condition: past about 1.7 KB an answer, the pipeline's specific
questions cost more than an agent's. The second was the worst failure I have seen, "Mlinska 22 nema
optiku" above a building that is connected; an answer that contradicts its own record will not go out,
and the demo on Friday shows it before and after. The open question, what doing nothing costs, goes to
the business owner of the tool at the same meeting.

```bash
docker compose -f 05_Agent_Architecture/challenge/databases/compose.yaml up -d
uv sync --inexact --group fiberly
uv run --group fiberly python 05_Agent_Architecture/challenge/databases/seed.py
uv run --group fiberly python 05_Agent_Architecture/challenge/measure.py failures   # what the model gets back
uv run --group fiberly python 05_Agent_Architecture/challenge/measure.py demo       # Step 4
uv run --group fiberly python 05_Agent_Architecture/challenge/measure.py size       # Step 5
uv run --group fiberly python 05_Agent_Architecture/challenge/measure.py labels     # the 22 Week 3 labels
```

Every number below is *measured* with Claude Haiku 5.5 on 10 November 2026. Everything together cost $0.059.

---

## The systems, rebuilt

At work Fiberly reads five sources: the building register, FIS, AAMS and the contact matrix through
Trino, and Pagesnap straight from MySQL. [`databases/`](./databases/) rebuilds that shape locally:
PostgreSQL with a register database and a warehouse, MySQL for Pagesnap, and Trino in front of
PostgreSQL. [`seed.py`](./databases/seed.py) spreads the Week 3 corpus over those tables: the address,
IDs, status, project and task come out of each record, the few columns no record states are invented
from the record's ID, and closed AAMS cards are kept as closed requests. The record's text stays as the
building's summary, so a plain check reads the same words as before. The structure is invented; the real
one stays in a private repo.

| Table | Rows |
| --- | --- |
| register: buildings | 1,435 |
| FIS: forecast | 1,419 |
| AAMS: requests and tasks | 639 |
| contact matrix | 980 |
| Pagesnap: projects / field reports | 980 / 148 |

[`systems.py`](../../01_Product_Engineering/challenge/systems.py) holds seven read-only lookups, one
per question a system answers, each with its values as query parameters and never pasted into the SQL.
The pipeline uses them when `FIBERLY_SOURCE=databases`, and its answer model now reads the systems' rows,
not only the summary. Before closed cards were added, the databases found the same record as the corpus
for 2,048 of 2,111 IDs and 1,361 of 1,397 register addresses. The missing IDs were closed AAMS cards,
now in the seed; the address differences are second buildings in records about several buildings, which
the databases find and the corpus search did not.

## Step 1: what the room asked

In [`decisions.md`](../../use_case/decisions.md#week-5--what-the-room-asked), every question on the
rubric's list, answered.

| Mark | Question | What changes |
| --- | --- | --- |
| Fair | How much data does each call return, and what does that cost you? | Measured in Step 5, and the size is now part of the switch condition |
| Fair | What is the worst failure you have seen it produce? | An answer that contradicts the status or project of its own record does not go out; shown on Friday |
| Open | What happens if you do nothing, and who absorbs that cost? | Nobody has timed one lookup by hand; asked of the business owner on 13 November |

## Step 2: the second way

**MCP.** The first ordering question is no: no service answers "look up this building" over HTTP. Trino
speaks HTTP, but it runs whatever SQL it is sent, so a UTCP manifest over it would hand the model a SQL
engine instead of a lookup. The second is the first yes: my manager's plan has the group's central
agent platform call Fiberly's lookups through the internal API gateway, so a client I do not write has to
discover them, which is what MCP is for.

**The closest alternative I did not pick: Code Mode.** A request makes several calls, which is its
question, but each answer is small, and it needs a sandbox for untrusted code that I do not have. In
Session 10 it stayed flat at about 1,850 tokens once Haiku's programs were allowed `isinstance`.

## Step 3: the build

[`fiberly_mcp.py`](../../01_Product_Engineering/challenge/fiberly_mcp.py) serves the seven lookups as
tools over stdio, and their docstrings are the descriptions the model reads. The server logs every
call in its own process, hides the SQL and the host when a query fails, and caps an answer at 60 KB.
The agent in [`measure.py`](./measure.py) is Week 3's agent loop with the same prompt, with every tool
call going through the MCP client.

The dispatcher never raises. What the model gets back, from `measure.py failures`:

```text
a tool that does not exist:   Unknown tool: 'lookup_building'
                              Tools that exist: register_by_adm, register_by_address, fibre_forecast, requests_by_adm, request_by_aams, contacts, pagesnap
arguments that are not JSON:  The arguments were not JSON (Expecting ',' delimiter: line 1 column 17 (char 16)). Send them as one JSON object.
a wrong argument name:        2 validation errors for call[fibre_forecast] adm_id Missing required argument ... adm Unexpected keyword argument ...
a value of the wrong type:    1 validation error for call[fibre_forecast] adm_id Input should be a valid integer ... input_value='Zagrebačka 27'
a number nobody has:          {"result": []}
```

The last line was a finding: FastMCP sends an empty list as structured content with no text at all, so
the model saw nothing until the dispatcher fell back to the structured content.

## Step 4: both, at demo scale

Two requests, three runs each: "adm 2003917", one building, and "Tko je PM za ADM 2501163 i ADM
3500624?", two buildings. Medians, with the range when the runs differed.

| Way | Request | Model calls | Capability calls | Seconds | Tokens | Characters the model read | $ a request |
| --- | --- | --- | --- | --- | --- | --- | --- |
| pipeline | one building | 1 | 6 | 1.2 (1.2–1.4) | 1,088 | 0 | 0.00013 |
| MCP agent | one building | 2 | 3 | 4.8 (4.2–5.3) | 3,889 | 767 | 0.00066 |
| pipeline | two buildings | 2 | 12 | 3.2 (2.8–3.2) | 3,341 | 2,768 | 0.00047 |
| MCP agent | two buildings | 3 | 4 | 4.9 (4.8–4.9) | 6,563 | 1,524 | 0.00093 |

**Parallel tool calls: yes.** On the first turn Haiku asked for 3 tools for one building and 2 for two
buildings (`len(msg.tool_calls)`), so the agent needs two or three model calls, not one per lookup.

The pipeline does twice to three times as much work in capability calls, because it reads every system
for every building, and still answers faster, because a plain check needs no second model call.

The agent's capability calls read zero in this process. They ran in the server's process and are
counted from its own log, which I had to add.

Memory: 78 MB for the process running the pipeline and the MCP client, 55 MB for the server process,
and 1.3 GiB for Trino, 486 MB for MySQL and 38 MB for PostgreSQL. The server starts and finishes its
handshake in 0.63 s.

On the 22 Week 3 labels, one run each:

| Way | Pass | Cited | Model calls | Capability calls | Seconds | $ a question |
| --- | --- | --- | --- | --- | --- | --- |
| pipeline | 22/22 | 20/20 | 1.5 | 5.7 | 2.4 | 0.00027 |
| MCP agent | 18/22 | 19/20 | 2.6 | 2.6 | 4.8 | 0.00075 |

Two of the agent's four misses are the architecture. For "ID je 27214368" and "25047 / 4725102" the
model guessed whether a bare number was an ADM ID or an AAMS number and guessed wrong; the pipeline
settles that in code by asking the register first. The other two are a request the record mentions but
the tables do not hold, and an en dash where the label expects a hyphen.

## Step 5: again at the real response size

In the pilot's 107 requests, a request fetched about 1.0 KB at the median and 2.8 KB at p90, and the
largest single answer was 6.6 KB. As built, one answer here is about 0.6 KB and a request reads 1 to 3
KB, so the first rows are the real size. To go above it, each non-empty answer was grown with an
invented status history (`FIBERLY_PAD_BYTES`), the same way in the pipeline and in the server. Two
runs each, median tokens.

| One answer | Request | Bytes in one answer | Capability calls, pipeline / MCP | Tokens, pipeline | Tokens, MCP agent |
| --- | --- | --- | --- | --- | --- |
| as built | one building | 569 | 6 / 3 | 1,088 | 3,907 |
| as built | two buildings | 610 | 12 / 4 | 3,341 | 6,564 |
| grown | one building | 2,754 | 6 / 3 | 1,088 | 6,672 |
| grown | two buildings | 2,696 | 12 / 4 | 16,568 | 13,335 |
| grown | one building | 6,263 | 6 / 3 | 1,088 | 10,096 |
| grown | two buildings | 6,316 | 12 / 4 | 35,361 | 24,144 |

A plain check stays flat in the pipeline, because the summary goes out word for word and no model reads
the rows. The agent grows with every answer it reads, like the tool loop in the session's sweep. The
surprise is the pipeline's specific question: it hands the model the rows of all twelve lookups, so it
grows faster than the agent and passes it at about 1.7 KB an answer. At the pilot's size that line is
far away; it is now the number to watch, and the first fix is to hand the model only the rows a
question needs.

**At 10× the volume**, about 110 requests a day instead of 11, the tokens per request do not change,
and the bill is about $1 a month in the pipeline and $2.60 through MCP, so volume decides nothing here;
the size of the answers does.

## Step 6: the decision

The Week 5 row in [`decisions.md`](../../use_case/decisions.md). **The pipeline stays.** MCP is the
closest reject, built and measured above: slower, four labels worse, and a process with nobody on the
other end, because the gateway the central platform would call through is not ready. **Switch
condition:** the gateway ready, the platform team registering the server, and an agent there calling it
in a test; then the lookups go behind MCP and the server already exists. The open question is still
open, because only the business owner can answer it, on Friday.

## Step 7: the refined demo

Not done yet. The refined demo is shown to the business owner of the tool on Friday, 13 November 2026,
with the three questions in order and then the open one. Their answers go here, in
[`stakeholders.md`](../../use_case/stakeholders.md) and in
[`decisions.md`](../../use_case/decisions.md); both already have a Week 5 row saying it has not happened.

## Step 8: bring it to work

Under `## Bring it to work` at the end of the [challenge README](./README.md). In short: Fiberly's
lookups in an MCP server on Google Cloud for the central agent platform, which today would be a server
for one caller. It would read through our team's read-only service account, DevOps would most likely
run it, and each source's owner approves its access through the gateway.

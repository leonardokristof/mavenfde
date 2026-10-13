# TC1 submission: Fibery

Fibery answers the questions internal operators at Hrvatski Telekom ask every day about fibre
at an address: is it available, is the HAKOM stopwatch running, what is happening with the
open request, has a deadline been missed and who to contact. Charter:
[`use_case/CHARTER.md`](../../use_case/CHARTER.md).

Run it:

```bash
cd 01_Product_Engineering/challenge
uv run python app.py                         # http://localhost:7860

docker build -t challenge .
docker run -p 7860:7860 --env-file ../../.env challenge
```

Everything runs on nine invented buildings in [`sample_data.json`](./sample_data.json). No
real address, ID or person is in this repo.

---

## The problem in one sentence

To answer just one question about fibre at an address, an employee has to check up to six
separate systems and interpret what they found using rules that mostly exist only in
people's heads, so the answers are slow, inconsistent and depend on who you ask.

## The contract

[`schema.py`](./schema.py). The `Request` is the operator's message as typed plus the
conversation so far. The `Response` has an `outcome` (answered, needs clarification, not
found, out of scope, error), the Croatian answer, the buildings found with their facts, and at
most one next step. "Not found" and "error" are outcomes of their own, so a failure is never
shown as an answer. `solve()` is implemented in [`fibery.py`](./fibery.py).

## Agent or pipeline

A pipeline. The model reads the operator's free text and turns it into an ADM ID, a WWMS
number or an address, and it answers specific follow-up questions. Code finds the building
and applies the stopwatch, deadline and contact rules, and writes plain checks from the
response template word for word. Both decisions, with what I rejected and what would change
my mind, are in [`use_case/decisions.md`](../../use_case/decisions.md).

## Golden examples

[`use_case/evals/golden.jsonl`](../../use_case/evals/golden.jsonl). Golden 1 is the edge case:
a house number with a suffix (12/1), typed without diacritics. Golden 5 is the decline: an
address that is not in the system. All five match word for word in 15 of 15 runs.

## Step 8: the endpoint

`answer_fibre_question(message, history)` in [`app.py`](./app.py), and the Fibery page in
[`frontend/index.html`](./frontend/index.html): Croatian, the model name in the header, a tag
with the outcome on every answer, a "Nova provjera" button that clears the conversation, and a
visible message when a request fails or the Gradio client can't load.

1. **What is one thing you do at work this could take over?** The manual check across six
   systems for one address or request: fibre status, the stopwatch, the open request, missed
   deadlines and who to contact. About 10 to 15 minutes each time.
2. **What exactly goes in?** One string, the operator's message as they typed it: an address,
   an ADM ID, a WWMS number or a follow-up like "tko je PM?", plus the conversation so far.
3. **What comes back, and who reads it?** The `Response` as JSON. The operator reads the answer
   and copies the last line (ADM ID, status, project) into their ticket. The outcome tells the
   page, and later an agent, whether to show the answer, ask back or send the case to a person.
4. **What did you name it, and why would an agent pick it correctly?**
   `answer_fibre_question`. The verb says it answers, "fibre" says what about, and the docstring
   names the three kinds of input and the five outcomes. An agent with a list of tools can tell
   it is the one for any question about fibre at a building or a request, and that it doesn't
   submit anything.

## Step 9: the container

The image builds from `uv.lock`, runs as a non-root user and gets the key at runtime with
`--env-file`. Tested: `/health`, the page and `answer_fibre_question` all answer from the
container.

**The CDN dependency.** The page loads the Gradio client from `cdn.jsdelivr.net` when it opens.
On my personal laptop that works. The work laptop goes through a proxy with TLS interception,
and I haven't tested that host from there, so on that network the page could load and do
nothing. The page now says so instead of failing silently. The real fix is to download
`@gradio/client` once at build time, copy it into the image next to `index.html` and import it
from the app itself, so the app reaches no public host at runtime.

**Image versus virtual environment.** A virtual environment holds the Python packages. The image
also holds the Python version, the system libraries, the app's files and the command that
starts it, as one tagged artifact that runs the same on any host with a container runtime,
which is what a platform team can scan, keep in their registry and run without knowing
anything about my laptop.

## Step 10: where it would live

I asked the DevOps team and colleagues who have worked with them. Full answers are in the
challenge README's Step 10 block and in [`use_case/ecosystem.md`](../../use_case/ecosystem.md);
the conversation is logged in [`use_case/stakeholders.md`](../../use_case/stakeholders.md).

| Question | Answer |
| --- | --- |
| Where would it run? | A managed container service, Cloud Run on GCP or Azure Container Apps |
| Which cloud? | GCP and Azure are used most; which one for this app is open |
| How would users log in? | Entra ID single sign-on |
| Could it reach an external LLM API? | Not directly: the proxy wants NTLM, which LiteLLM can't do. It would use a company endpoint: Claude Sonnet 5.5 on Azure or GPT on GCP |
| What surprised me? | How much the work laptop depends on other teams before a line of code is written |
| What would change? | Internal registry and proxy for images and packages, the corporate CA in the container, secrets from the cloud's secret manager, Entra ID in front, the approved endpoint in `.env`, the Gradio client served by the app, real read-only sources, and approval from Information Security and the DPO |

## Step 11: vibe check

All three passes are in the challenge README's Step 11 section.

- **Pass 1:** the base model got all five general prompts right. Its explanations run long.
- **Pass 2:** after one change, every Fibery prompt came back right, including a follow-up
  without an ID, a missing city, the complex connection rule and a parked request. The change:
  the model wrote every answer at first and paraphrased rules it should have copied, so plain
  checks are now written in code.
- **Pass 3, the real limitations:** it reads nine invented buildings, not the six sources;
  dates are calculated against a fixed snapshot, not today; it is read-only and doesn't say so
  when asked to submit something; no questions across many buildings; no memory between
  sessions; contacts are roles, not the responsibility matrix; no login; the Gradio client
  comes from a public CDN.

A vibe check shows the app works on the cases I thought of, on one day, judged by me. To
compare two versions I need the same fixed inputs with must-contain and must-not-contain checks
run automatically, the way the five goldens were run here.

## Step 12: demo to a real user

Not done yet. The three questions, to fill in after showing it to an operator:

1. What would you use this for?
2. What is missing before you would actually use it?
3. What would you expect it to cost?

## Bring it to work

The napkin math, the p95 target and the three swap lines are under `## Bring it to work` at the
end of the [challenge README](./README.md). In short: about $0.002 to $0.007 a question on
Claude Sonnet 5.5 against €1.83 to €4.75 of an operator's time, a measured p95 of 2.9 s against
a 60 s target, and reliability, not cost, is what could stop it being used.

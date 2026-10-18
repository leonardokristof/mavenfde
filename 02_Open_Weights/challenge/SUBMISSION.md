# TC2 submission: Fiberly

Week 2 of the certification for Fiberly. Charter:
[`use_case/CHARTER.md`](../../use_case/CHARTER.md).

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
| Bare number, then "wwms" | found the request | said it wasn't in the system |
| Typo in a street name ("vrbnik 23 zagreb") | asked "Jesi li mislio Vrbik 23?" | timed out after 60 s |

The goldens still pass because plain answers are built by code; the model only reads the
question. The swap found two weak spots in my code. The local model returned a WWMS number as
text instead of a number, so the lookup missed it; `fiberly.py` now accepts both. And the 60 s
timeout, which is also my p95 target, is too short for a local model that thinks before it
answers. Whether a local model is a realistic path at HT is in
[`use_case/ecosystem.md`](../../use_case/ecosystem.md).

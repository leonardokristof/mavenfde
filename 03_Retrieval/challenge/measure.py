import json
import sys
import time
from datetime import datetime

import litellm
from litellm.exceptions import UnsupportedParamsError

from corpus import ROOT, Index, load_labels, load_records
from wiki import Wiki

sys.path.insert(0, str(ROOT))
from helpers import nb  # noqa: E402

CFG = nb.bootstrap(start=ROOT)
from fiberly import solve_from_records  # noqa: E402
from schema import Request  # noqa: E402

SAMPLER = {"temperature": 0}
SYSTEM = ("Answer an HT operator's question about fibre at a building only from tool evidence, in Croatian, briefly. "
          "Investigate before answering. Cite the record IDs you used, like r0123. If the evidence does not answer it, say so and invent nothing.")
DECLINE_MARKERS = ("nema ", "nemam", "nije ", "ne mogu", "ne postoji", "ne nalazim", "nisam pronaš")


# I wanted every run priced in dollars straight away, so I wrote this function and this comment myself:
# I like to see what a measurement cost the moment it finishes, priced by the model that actually ran.
def usd(response):
    try:
        return litellm.completion_cost(completion_response=response)
    except Exception:
        return 0.0


def ask_model(messages, tools):
    kwargs = dict(messages=messages, tools=tools, **CFG.kwargs())
    try:
        return litellm.completion(timeout=600, **SAMPLER, **kwargs)
    except UnsupportedParamsError:
        SAMPLER.clear()
        return litellm.completion(timeout=600, **kwargs)


def schema(name, description, properties, required=()):
    return {"type": "function", "function": {"name": name, "description": description,
            "parameters": {"type": "object", "properties": properties, "required": list(required)}}}


def approaches():
    records, wiki = load_records(), Wiki()
    search = schema("search_chunks", "Search ranked records. Search again with a new query when evidence is incomplete.",
                    {"query": {"type": "string"}, "k": {"type": "integer"}}, ["query"])
    bm25, hybrid = Index(records), Index(records, mode="hybrid")
    dci = ([schema("list_pages", "Read the wiki index of cities.", {}),
            schema("grep_wiki", "Search exact text or a regular expression across wiki pages with line provenance.",
                   {"pattern": {"type": "string"}}, ["pattern"]),
            schema("read_page", "Read a complete wiki page by its stable name, like grad_zagreb.md or r0123.md.",
                   {"page": {"type": "string"}}, ["page"])],
           {"list_pages": wiki.list_pages, "grep_wiki": wiki.grep_wiki, "read_page": wiki.read_page})
    print(f"embedding the corpus: {hybrid.tokens:,} tokens, {hybrid.cut} records cut at 128, local model, $0")
    return {"Agentic RAG": ([search], {"search_chunks": bm25.search_chunks}), "DCI Wiki": dci,
            "Hybrid RAG": ([search], {"search_chunks": hybrid.search_chunks}), "Pipeline": (None, run_pipeline)}


def run_pipeline(question):
    usage, started = {}, time.perf_counter()
    response = solve_from_records(Request(message=question), usage)
    return {"answer": response.answer, "sources": response.sources, "trace": [{"tool": "lookup"}] * usage["lookups"],
            "evidence_chars": usage["chars"], "tokens": [usage["in"], usage["out"]], "usd": usage["usd"],
            "latency_s": time.perf_counter() - started, "stopped": response.outcome}


def run_agent(question, tools, funcs, max_turns=6):
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]
    trace, chars, tokens, cost, started = [], 0, [0, 0], 0.0, time.perf_counter()
    for _ in range(max_turns):
        response = ask_model(messages, tools)
        msg, cost = response.choices[0].message, cost + usd(response)
        tokens = [tokens[0] + response.usage.prompt_tokens, tokens[1] + response.usage.completion_tokens]
        calls = msg.tool_calls or []
        if not calls:
            return {"answer": (msg.content or "").strip(), "trace": trace, "evidence_chars": chars, "tokens": tokens,
                    "usd": cost, "latency_s": time.perf_counter() - started, "stopped": "answer"}
        shaped = [{"id": c.id, "type": "function", "function": {"name": c.function.name, "arguments": c.function.arguments}} for c in calls]
        messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": shaped})
        for call in shaped:
            name = call["function"]["name"]
            try:
                args = json.loads(call["function"]["arguments"] or "{}")
                result = str(funcs[name](**args))
            except Exception as exc:
                args, result = {}, f"(tool error: {type(exc).__name__}: {exc})"
            chars += len(result)
            trace.append({"tool": name, "args": args, "chars": len(result)})
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})
    return {"answer": "(max turns reached)", "trace": trace, "evidence_chars": chars, "tokens": tokens, "usd": cost,
            "latency_s": time.perf_counter() - started, "stopped": "max_turns"}


def score(case, result):
    answer = result["answer"].lower()
    if case.get("must_decline"):
        passed = any(m in answer for m in DECLINE_MARKERS) and not any(t.lower() in answer for t in case["expected_terms"])
    else:
        passed = all(t.lower() in answer for t in case["expected_terms"])
    return {"pass": passed, "cited": any(g in result.get("sources", answer) for g in case["gold"]) if case["gold"] else None,
            "calls": len(result["trace"]), "evidence_chars": result["evidence_chars"], "latency_s": round(result["latency_s"], 2),
            "stopped": result["stopped"], "tokens_in": result["tokens"][0], "tokens_out": result["tokens"][1], "usd": result["usd"]}


def summarize(rows):
    print(f"\n| approach | pass | cited | calls | evidence chars | latency s | $ per question | $ total |\n| --- | --- | --- | --- | --- | --- | --- | --- |")
    for name in dict.fromkeys(r["approach"] for r in rows):
        rr = [r for r in rows if r["approach"] == name]
        cited = [r["cited"] for r in rr if r["cited"] is not None]
        mean = lambda key: sum(r[key] for r in rr) / len(rr)
        print(f"| {name} | {sum(r['pass'] for r in rr)}/{len(rr)} | {sum(cited)}/{len(cited)} | {mean('calls'):.1f} | {mean('evidence_chars'):,.0f} | "
              f"{mean('latency_s'):.1f} | {mean('usd'):.5f} | {sum(r['usd'] for r in rr):.4f} |")
    print(f"\n| question | favours | " + " | ".join(dict.fromkeys(r["approach"] for r in rows)) + " |")
    for qid in dict.fromkeys(r["id"] for r in rows):
        cells = [f"{sum(r['pass'] for r in rows if r['id'] == qid and r['approach'] == a)}/{sum(1 for r in rows if r['id'] == qid and r['approach'] == a)}"
                 for a in dict.fromkeys(r["approach"] for r in rows)]
        print(f"| {qid} | {next(r['favours'] for r in rows if r['id'] == qid)} | " + " | ".join(cells) + " |")
    print(f"\nmodel {CFG.llm_model}, total ${sum(r['usd'] for r in rows):.4f}, {sum(r['tokens_in'] for r in rows):,} tokens in, {sum(r['tokens_out'] for r in rows):,} out")


def run(reps=3, args=()):
    setups = approaches()
    names = [a for a in args if a in setups] or list(setups)
    ids = [a for a in args if a not in setups]
    cases = [c for c in load_labels() if not ids or c["id"] in ids]
    out = ROOT / "use_case" / "data" / "runs" / f"{datetime.now():%Y%m%d_%H%M%S}.jsonl"
    out.parent.mkdir(exist_ok=True)
    rows, setups = [], {n: setups[n] for n in names}
    with out.open("w", encoding="utf-8") as log:
        for rep in range(1, reps + 1):
            for case in cases:
                for name, (tools, funcs) in setups.items():
                    result = run_agent(case["question"], tools, funcs) if tools else funcs(case["question"])
                    row = {"rep": rep, "id": case["id"], "approach": name, "favours": case["favours"], **score(case, result)}
                    rows.append(row)
                    log.write(json.dumps({**row, "answer": result["answer"], "sources": result.get("sources"), "trace": result["trace"]}, ensure_ascii=False) + "\n")
                    print(f"{rep} {case['id']:26s} {name:12s} pass={row['pass']!s:5s} calls={row['calls']} chars={row['evidence_chars']:6d} "
                          f"{row['latency_s']:5.1f}s ${row['usd']:.5f}", flush=True)
    summarize(rows)
    print(f"traces: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    run(int(sys.argv[1]) if len(sys.argv) > 1 else 3, sys.argv[2:])

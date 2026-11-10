import asyncio
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

import psutil
from fastmcp import Client
from fastmcp.client import PythonStdioTransport

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "01_Product_Engineering" / "challenge"
os.environ["FIBERLY_SOURCE"] = "databases"
sys.path[:0] = [str(ROOT / "03_Retrieval" / "challenge"), str(APP)]
_spec = importlib.util.spec_from_file_location("week3", ROOT / "03_Retrieval" / "challenge" / "measure.py")
week3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(week3)

from corpus import load_labels  # noqa: E402

import fiberly  # noqa: E402
import systems  # noqa: E402

REQUESTS = {"one building": "adm 2003917", "two buildings": "Tko je PM za ADM 2501163 i ADM 3500624?"}


def call_with_pipeline(question: str) -> dict:
    model_calls, before, complete = [], sum(systems.calls.values()), fiberly.complete
    fiberly.complete = lambda *a, **k: model_calls.append(1) or complete(*a, **k)
    try:
        result = week3.run_pipeline(question)
    finally:
        fiberly.complete = complete
    read = result["evidence_chars"] if len(model_calls) > 1 else 0
    return {**result, "evidence_chars": read, "model calls": len(model_calls),
            "capability calls": sum(systems.calls.values()) - before, "first turn tool calls": None}


async def dispatch(client: Client, name: str, arguments: str) -> str:
    try:
        args = json.loads(arguments or "{}")
    except ValueError as error:
        return f"The arguments were not JSON ({error}). Send them as one JSON object."
    result = await client.call_tool(name, args, raise_on_error=False)
    text = "\n".join(getattr(block, "text", "") for block in result.content) or json.dumps(result.structured_content)
    if result.is_error:
        text += "\nTools that exist: " + ", ".join(t.name for t in await client.list_tools())
    return text


async def call_with_mcp(question: str, server: "McpServer", max_turns: int = 6) -> dict:
    tools = [{"type": "function", "function": {"name": t.name, "description": t.description or "", "parameters": t.input_schema}}
             for t in await server.client.list_tools()]
    messages = [{"role": "system", "content": week3.SYSTEM}, {"role": "user", "content": question}]
    trace, size, tokens, cost, turns, first, before = [], 0, [0, 0], 0.0, 0, None, server.calls()
    started, answer, stopped = time.perf_counter(), "(max turns reached)", "max_turns"
    for _ in range(max_turns):
        response = week3.ask_model(messages, tools)
        msg, cost, turns = response.choices[0].message, cost + week3.usd(response), turns + 1
        tokens = [tokens[0] + response.usage.prompt_tokens, tokens[1] + response.usage.completion_tokens]
        calls = msg.tool_calls or []
        first = len(calls) if first is None else first
        if not calls:
            answer, stopped = (msg.content or "").strip(), "answer"
            break
        messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": [
            {"id": c.id, "type": "function", "function": {"name": c.function.name, "arguments": c.function.arguments}} for c in calls]})
        for call in calls:
            text = await dispatch(server.client, call.function.name, call.function.arguments)
            size += len(text)
            trace.append({"tool": call.function.name, "args": call.function.arguments, "chars": len(text), "bytes": len(text.encode())})
            messages.append({"role": "tool", "tool_call_id": call.id, "content": text})
    return {"answer": answer, "trace": trace, "evidence_chars": size, "tokens": tokens, "usd": cost,
            "latency_s": time.perf_counter() - started, "stopped": stopped, "model calls": turns,
            "capability calls": server.calls() - before, "first turn tool calls": first}


class McpServer:

    async def __aenter__(self):
        self.log = Path(tempfile.mkstemp(suffix=".log")[1])
        transport = PythonStdioTransport(APP / "fiberly_mcp.py", python_cmd=sys.executable, cwd=str(APP),
                                         env={**os.environ, "FIBERLY_MCP_LOG": str(self.log)})
        started = time.perf_counter()
        self.client = await Client(transport).__aenter__()
        self.start_s = time.perf_counter() - started
        return self

    def calls(self) -> int:
        return len(self.log.read_text().splitlines())

    def memory_mb(self) -> float:
        return sum(p.memory_info().rss for p in psutil.Process().children(recursive=True)
                   if "fiberly_mcp.py" in " ".join(p.cmdline())) / 2**20

    async def __aexit__(self, *exc):
        await self.client.__aexit__(*exc)
        self.log.unlink()


def median(values: list) -> str:
    values = sorted(v for v in values if v is not None)
    if not values:
        return "–"
    middle = values[len(values) // 2]
    if isinstance(middle, float):
        return f"{middle:.1f} ({values[0]:.1f}–{values[-1]:.1f})"
    return f"{middle:,}" if values[0] == values[-1] else f"{middle:,} ({values[0]:,}–{values[-1]:,})"


async def demo(reps: int = 3) -> None:
    rows = []
    async with McpServer() as server:
        print(f"MCP server start and handshake: {server.start_s:.2f} s, {len(await server.client.list_tools())} tools, "
              f"definitions {len(json.dumps([t.model_dump() for t in await server.client.list_tools()]).encode()):,} bytes")
        for rep in range(1, reps + 1):
            for label, question in REQUESTS.items():
                for way in ("pipeline", "MCP agent"):
                    result = call_with_pipeline(question) if way == "pipeline" else await call_with_mcp(question, server)
                    rows.append({"way": way, "request": label, **result})
                    print(f"{rep} {label} | {way} | {result['model calls']} model, {result['capability calls']} capability, "
                          f"{result['latency_s']:.1f} s | {result['answer'][:120]!r}".replace("\\n", " "), flush=True)
        memory = (f"pipeline process (also the MCP client) {psutil.Process().memory_info().rss / 2**20:.0f} MB, "
                  f"MCP server process {server.memory_mb():.0f} MB")
    print("\n| way | request | model calls | tool calls on the first turn | capability calls | seconds | tokens in | tokens out "
          "| characters the model read | $ per request |\n|" + " --- |" * 10)
    for way, label in dict.fromkeys((r["way"], r["request"]) for r in rows):
        rr = [r for r in rows if (r["way"], r["request"]) == (way, label)]
        print(f"| {way} | {label} | " + " | ".join(median([r[k] for r in rr]) for k in ("model calls", "first turn tool calls", "capability calls"))
              + f" | {median([r['latency_s'] for r in rr])} | {median([r['tokens'][0] for r in rr])} | {median([r['tokens'][1] for r in rr])} "
              f"| {median([r['evidence_chars'] for r in rr])} | {sum(r['usd'] for r in rr) / len(rr):.5f} |")
    docker = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{.Name}} {{.MemUsage}}"], capture_output=True, text=True).stdout
    print(f"\nmemory: {memory}; containers: " + "; ".join(l for l in docker.splitlines() if "databases-" in l))
    print(f"model {week3.CFG.llm_model}, {reps} runs, total ${sum(r['usd'] for r in rows):.4f}")


async def size(reps: int = 2) -> None:
    rows = []
    for grown, pad in {"as built": 0, "2.8 KB an answer": 2800, "6.6 KB an answer": 6600}.items():
        os.environ["FIBERLY_PAD_BYTES"] = str(pad)
        async with McpServer() as server:
            for rep in range(1, reps + 1):
                for label, question in REQUESTS.items():
                    for way in ("pipeline", "MCP agent"):
                        result = call_with_pipeline(question) if way == "pipeline" else await call_with_mcp(question, server)
                        rows.append({"way": way, "request": label, "size": grown, **result})
                        print(f"{grown} | {label} | {way} | {result['capability calls']} capability, {sum(result['tokens'])} tokens, "
                              f"{result['latency_s']:.1f} s", flush=True)
    os.environ.pop("FIBERLY_PAD_BYTES")
    print("\n| answers | request | bytes in one answer (median, largest) | capability calls: pipeline / MCP | tokens: pipeline | tokens: MCP agent "
          "| MCP ÷ pipeline |\n|" + " --- |" * 7)
    for grown, label in dict.fromkeys((r["size"], r["request"]) for r in rows):
        pipe, mcp = ([r for r in rows if (r["size"], r["request"], r["way"]) == (grown, label, way)] for way in ("pipeline", "MCP agent"))
        answers = sorted(t["bytes"] for r in mcp for t in r["trace"] if t["bytes"] > 20)
        tokens = [sorted(sum(r["tokens"]) for r in rr)[len(rr) // 2] for rr in (pipe, mcp)]
        print(f"| {grown} | {label} | {answers[len(answers) // 2]:,}, {answers[-1]:,} | {median([r['capability calls'] for r in pipe])} / "
              f"{median([r['capability calls'] for r in mcp])} | {tokens[0]:,} | {tokens[1]:,} | {tokens[1] / tokens[0]:.1f}× |")
    print(f"\nmodel {week3.CFG.llm_model}, {reps} runs, total ${sum(r['usd'] for r in rows):.4f}, "
          f"$ per request at 6.6 KB: pipeline {sum(r['usd'] for r in rows if r['size'] == '6.6 KB an answer' and r['way'] == 'pipeline') / (2 * reps):.5f}, "
          f"MCP agent {sum(r['usd'] for r in rows if r['size'] == '6.6 KB an answer' and r['way'] == 'MCP agent') / (2 * reps):.5f}")


async def labels(reps: int = 1) -> None:
    rows, out = [], ROOT / "use_case" / "data" / "runs" / f"tc5_{datetime.now():%Y%m%d_%H%M%S}.jsonl"
    async with McpServer() as server:
        with out.open("w", encoding="utf-8") as log:
            for rep in range(1, reps + 1):
                for case in load_labels():
                    for way in ("pipeline", "MCP agent"):
                        result = call_with_pipeline(case["question"]) if way == "pipeline" else await call_with_mcp(case["question"], server)
                        row = {"rep": rep, "id": case["id"], "approach": way, "favours": case["favours"], **week3.score(case, result),
                               "model calls": result["model calls"], "capability calls": result["capability calls"]}
                        rows.append(row)
                        log.write(json.dumps({**row, "answer": result["answer"], "trace": result["trace"]}, ensure_ascii=False) + "\n")
                        print(f"{rep} {case['id']} {way}: {'pass' if row['pass'] else 'FAIL'}, {row['model calls']} model, "
                              f"{row['capability calls']} capability, {row['latency_s']} s", flush=True)
    week3.summarize(rows)
    for way in ("pipeline", "MCP agent"):
        rr = [r for r in rows if r["approach"] == way]
        print(f"{way}: {sum(r['model calls'] for r in rr) / len(rr):.1f} model calls and "
              f"{sum(r['capability calls'] for r in rr) / len(rr):.1f} capability calls per question")
    print(f"log: {out.relative_to(ROOT)}")


async def failures() -> None:
    async with McpServer() as server:
        for label, name, arguments in [("a tool that does not exist", "lookup_building", '{"adm_id": 2003917}'),
                                       ("arguments that are not JSON", "fibre_forecast", '{"adm_id": 20039'),
                                       ("a wrong argument name", "fibre_forecast", '{"adm": 2003917}'),
                                       ("a value of the wrong type", "fibre_forecast", '{"adm_id": "Zagrebačka 27"}'),
                                       ("a number nobody has", "fibre_forecast", '{"adm_id": 1}')]:
            print(f"{label}:\n  {(await dispatch(server.client, name, arguments))[:400]}")


if __name__ == "__main__":
    asyncio.run({"demo": demo, "size": size, "labels": labels, "failures": failures}[sys.argv[1]]())

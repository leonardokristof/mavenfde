import json
import os
import re
import unicodedata
from functools import cache
from pathlib import Path

from rank_bm25 import BM25Okapi

CORPUS = Path(os.getenv("CORPUS_PATH") or Path(__file__).resolve().parents[2] / "use_case" / "data" / "synthetic_sonnet.jsonl")


def load_records() -> list[dict]:
    rows = CORPUS.read_text(encoding="utf-8").splitlines()
    return [{"id": f"r{n:04d}", **json.loads(row)} for n, row in enumerate(rows, 1)]


def tokenize(text: str, fold: bool = True) -> list[str]:
    if not fold:
        return re.findall(r"[a-z0-9£$%]+", text.lower())
    text = unicodedata.normalize("NFKD", text.lower().replace("đ", "d"))
    return re.findall(r"\d+/\d+|[a-z0-9]+", "".join(c for c in text if not unicodedata.combining(c)))


@cache
def _store():
    records = [r for r in load_records() if r["outcome"] == "answered"]
    numbers = {n: r for r in records for n in re.findall(r"\b\d{5,10}\b", r["output"])}
    return records, BM25Okapi([tokenize(r["output"]) for r in records]), numbers


def by_number(number: str) -> list[dict]:
    record = _store()[2].get(number)
    return [record] if record else []


def search(query: str, k: int) -> list[dict]:
    records, bm25, _ = _store()
    scores = bm25.get_scores(tokenize(query))
    return [records[i] for i in sorted(range(len(records)), key=scores.__getitem__, reverse=True)[:k]]

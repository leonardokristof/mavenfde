import json
import re
import sys
import unicodedata
from pathlib import Path

from rank_bm25 import BM25Okapi

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "use_case" / "data" / "synthetic_sonnet.jsonl"
LABELS = ROOT / "use_case" / "evals" / "retrieval.jsonl"
FIELDS = {"output": ("output",), "input+output": ("input", "output"), "input": ("input",)}


def load_records():
    rows = CORPUS.read_text(encoding="utf-8").splitlines()
    return [{"id": f"r{n:04d}", **json.loads(row)} for n, row in enumerate(rows, 1)]


def load_labels():
    return [json.loads(line) for line in LABELS.read_text(encoding="utf-8").splitlines()]


def tokenize(text, fold=True):
    if not fold:
        return re.findall(r"[a-z0-9£$%]+", text.lower())
    text = unicodedata.normalize("NFKD", text.lower().replace("đ", "d"))
    return re.findall(r"\d+/\d+|[a-z0-9]+", "".join(c for c in text if not unicodedata.combining(c)))


class Index:
    def __init__(self, records, fields=("output",), fold=True):
        self.records, self.fold = records, fold
        self.bm25 = BM25Okapi([tokenize(" ".join(r[f] for f in fields), fold) for r in records])

    def top(self, query, k):
        scores = self.bm25.get_scores(tokenize(query, self.fold))
        order = sorted(range(len(scores)), key=scores.__getitem__, reverse=True)[:k]
        return [(self.records[i], scores[i]) for i in order]

    def search_chunks(self, query, k=4):
        return "\n\n---\n\n".join(f"[{r['id']}]\n{r['output'][:1000]}" for r, _ in self.top(query, max(1, min(k, 8))))


def by_key(records, question):
    numbers = set(re.findall(r"\b\d{5,10}\b", question))
    return {r["id"] for r in records if numbers & set(re.findall(r"\b\d{5,10}\b", r["output"]))}


def recall():
    records, labels = load_records(), load_labels()
    lookups = [q for q in labels if q["gold"]]
    for fold in (False, True):
        for name, fields in FIELDS.items():
            index = Index(records, fields, fold)
            ranks = [next((n for n, (r, _) in enumerate(index.top(q["question"], 20), 1) if r["id"] in q["gold"]), None)
                     for q in lookups]
            hits = [sum(1 for rank in ranks if rank and rank <= k) for k in (1, 3, 5)]
            print(f"{'folded' if fold else 'S5'}  {name:13s} recall@1/3/5 = {hits[0]}/{hits[1]}/{hits[2]} of {len(lookups)}  ranks {ranks}")
    print(f"by key only: {sum(bool(set(q['gold']) & by_key(records, q['question'])) for q in lookups)} of {len(lookups)}")
    index = Index(records)
    for q in labels:
        if q["kind"] == "decline":
            r, score = index.top(q["question"], 1)[0]
            print(f"{q['id']}: top hit {r['id']} at {score:.1f}  {r['output'][:80]!r}")


if __name__ == "__main__":
    {"recall": recall}[sys.argv[1]]()

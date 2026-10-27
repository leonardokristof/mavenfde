import json
import re
import sys
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "01_Product_Engineering" / "challenge"))
from records import load_records, tokenize  # noqa: E402

LABELS = ROOT / "use_case" / "evals" / "retrieval.jsonl"
FIELDS = {"output": ("output",), "input+output": ("input", "output"), "input": ("input",)}
EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def load_labels():
    return [json.loads(line) for line in LABELS.read_text(encoding="utf-8").splitlines()]


class Index:
    def __init__(self, records, fields=("output",), fold=True, mode="bm25"):
        self.records, self.fold, self.mode = records, fold, mode
        texts = [" ".join(r[f] for f in fields) for r in records]
        self.bm25 = BM25Okapi([tokenize(t, fold) for t in texts])
        if mode != "bm25":
            from fastembed import TextEmbedding
            self.embedder = TextEmbedding(EMBED_MODEL)
            vectors = np.array(list(self.embedder.embed(texts)))
            self.vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
            lengths = [sum(e.attention_mask) for e in self.embedder.model.tokenizer.encode_batch(texts)]
            self.tokens, self.cut = sum(lengths), sum(n >= 128 for n in lengths)

    def top(self, query, k):
        scores = self.bm25.get_scores(tokenize(query, self.fold))
        if self.mode != "bm25":
            q = np.array(next(iter(self.embedder.query_embed([query]))))
            dense = self.vectors @ (q / np.linalg.norm(q))
            self.tokens += sum(self.embedder.model.tokenizer.encode(query).attention_mask)
            if self.mode == "dense":
                scores = dense
            else:
                fused = np.zeros(len(scores))
                for ranked in (scores, dense):
                    fused[np.argsort(-ranked)] += 1 / (61 + np.arange(len(ranked)))
                scores = fused
        order = np.argsort(-np.asarray(scores))[:k]
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
    for mode in ("dense", "hybrid"):
        index = Index(records, mode=mode)
        ranks = [next((n for n, (r, _) in enumerate(index.top(q["question"], 20), 1) if r["id"] in q["gold"]), None) for q in lookups]
        hits = [sum(1 for rank in ranks if rank and rank <= k) for k in (1, 3, 5)]
        print(f"{mode:7s} output        recall@1/3/5 = {hits[0]}/{hits[1]}/{hits[2]} of {len(lookups)}  ranks {ranks}")
    print(f"embedding: {EMBED_MODEL}, {index.tokens:,} tokens, {index.cut} of {len(records)} records cut at 128 tokens")
    print(f"by key only: {sum(bool(set(q['gold']) & by_key(records, q['question'])) for q in lookups)} of {len(lookups)}")
    index = Index(records)
    for q in labels:
        if q["kind"] == "decline":
            r, score = index.top(q["question"], 1)[0]
            print(f"{q['id']}: top hit {r['id']} at {score:.1f}  {r['output'][:80]!r}")


if __name__ == "__main__":
    {"recall": recall}[sys.argv[1]]()

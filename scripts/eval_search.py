#!/usr/bin/env python3
"""Stage 5c-2: evaluate BM25 vs vector vs hybrid on generated questions.

Reads efforts/<effort>/eval/questions.jsonl, runs all three modes, reports
recall@10 and MRR@10. Writes eval_report.md next to the questions.

Usage: .venv/bin/python scripts/eval_search.py
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from search import (ST_IDS, QUERY_PREFIX, get_model_id, load_vectors, rrf,  # noqa: E402
                    bm25_leg, vector_leg)

DB = ROOT / "data" / "search.db"
OUT = ROOT / "efforts" / "2026-11-07-amenity-knowledge-base" / "eval"
N = 10


def main() -> None:
    from sentence_transformers import SentenceTransformer
    import torch

    qs = [json.loads(l) for l in (OUT / "questions.jsonl").read_text().splitlines()]
    print(f"{len(qs)} questions")
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    model_id = get_model_id(con)
    st = SentenceTransformer(ST_IDS[model_id],
                             device="cuda" if torch.cuda.is_available() else "cpu")
    domains, V = load_vectors(con)

    # pre-encode all questions once
    qtexts = [q["question"] for q in qs]
    qvecs = st.encode([QUERY_PREFIX.get(model_id, "") + t for t in qtexts])
    qvecs = qvecs / (np.linalg.norm(qvecs, axis=1, keepdims=True) + 1e-12)

    metrics = {m: {"recall": 0, "mrr_sum": 0.0, "misses": []} for m in ("bm25", "vector", "hybrid")}
    for i, q in enumerate(qs):
        bm = bm25_leg(con, q["question"], None, N)
        vec = vector_leg(qvecs[i], domains, V, None, N)
        hyb = rrf([bm, vec], N)
        for mode, ranked in (("bm25", bm), ("vector", vec),
                             ("hybrid", [d for d, _ in hyb])):
            if q["domain"] in ranked:
                metrics[mode]["recall"] += 1
                metrics[mode]["mrr_sum"] += 1.0 / (ranked.index(q["domain"]) + 1)
            else:
                metrics[mode]["misses"].append(
                    {"q": q["question"], "target": q["domain"], "name": q["name"]})

    lines = [f"# Search eval — {len(qs)} generated questions, N={N}", "",
             "| mode | recall@10 | MRR@10 |", "|---|---|---|"]
    for m in ("bm25", "vector", "hybrid"):
        s = metrics[m]
        lines.append(f"| {m} | {s['recall']/len(qs):.0%} | {s['mrr_sum']/len(qs):.2f} |")
    for m in ("bm25", "vector", "hybrid"):
        lines += ["", f"## {m} misses ({len(metrics[m]['misses'])})"]
        lines += [f"- “{x['q']}” → target {x['target']} ({x['name']})"
                  for x in metrics[m]["misses"][:15]]
    report = OUT / "eval_report.md"
    report.write_text("\n".join(lines))
    print("\n".join(lines[:8]))
    print(f"\nwrote {report}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Vector shrink experiments for the edge artifact: int8 quantization, naive
Matryoshka-style truncation, and PCA — measured on the 60-question eval.

For each variant we transform the stored doc vectors (and, when the geometry
requires it, the query vectors the same way), then re-run the vector leg and the
hybrid (BM25+RRF) ranking exactly like eval_search.py does. Ranking on
dequantized int8 vectors is mathematically identical to true int8 dot scoring
(per-vector absmax scale), so no ONNX machinery is needed to measure quality.

Usage:
    HF_HOME=/opt/vllm/models/hf .venv/bin/python scripts/shrink_eval.py --device cuda
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from search import QUERY_PREFIX, ST_IDS, bm25_leg, get_model_id, load_vectors, rrf  # noqa: E402

DB = ROOT / "data" / "search_arctic-s.db"
QUESTIONS = ROOT / "efforts" / "2026-11-08-edge-embedder-bakeoff" / "eval" / "questions.jsonl"
REPORT = ROOT / "efforts" / "2026-11-08-edge-embedder-bakeoff" / "eval" / "vector-shrink.md"
N = 10
N_DOCS = 13199  # for storage arithmetic


def int8_roundtrip(X: np.ndarray) -> np.ndarray:
    """Symmetric per-vector absmax int8 quantize -> dequantize -> renormalize."""
    out = np.empty_like(X)
    for i, v in enumerate(X):
        s = 127.0 / max(np.abs(v).max(), 1e-12)
        q = np.clip(np.round(v * s), -127, 127) / s
        out[i] = q
    return out / (np.linalg.norm(out, axis=1, keepdims=True) + 1e-12)


def trunc(X: np.ndarray, dim: int) -> np.ndarray:
    Y = X[:, :dim].copy()
    return Y / (np.linalg.norm(Y, axis=1, keepdims=True) + 1e-12)


def pca_fit(X: np.ndarray, k: int):
    mu = X.mean(axis=0)
    _, S, Vt = np.linalg.svd(X - mu, full_matrices=False)
    evr = float(np.sum(S[:k] ** 2) / np.sum(S ** 2))
    return mu, Vt[:k], evr


def pca_apply(X: np.ndarray, mu: np.ndarray, comps: np.ndarray) -> np.ndarray:
    Y = (X - mu) @ comps.T
    return Y / (np.linalg.norm(Y, axis=1, keepdims=True) + 1e-12)


def main() -> None:
    from sentence_transformers import SentenceTransformer

    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DB))
    ap.add_argument("--questions", default=str(QUESTIONS))
    ap.add_argument("--report", default=str(REPORT))
    ap.add_argument("--device", default="cuda", help="cpu | cuda for query encoding")
    args = ap.parse_args()

    qs = [json.loads(l) for l in Path(args.questions).read_text().splitlines()]
    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    model_id = get_model_id(con)
    domains, V = load_vectors(con)
    print(f"{len(qs)} questions · db={args.db} · model={model_id} · {V.shape}")

    st = SentenceTransformer(ST_IDS[model_id], device=args.device)
    Q = st.encode([QUERY_PREFIX.get(model_id, "") + q["question"] for q in qs])
    Q = Q / (np.linalg.norm(Q, axis=1, keepdims=True) + 1e-12)

    bm = [bm25_leg(con, q["question"], None, N) for q in qs]  # constant across variants

    variants = [("float32 (baseline)", V, Q, 4)]
    variants.append(("int8 docs (float query)", int8_roundtrip(V), Q, 1))
    variants.append(("int8 docs + int8 query", int8_roundtrip(V), int8_roundtrip(Q), 1))
    for dim in (256, 128, 64):
        variants.append((f"trunc-{dim} (naive MRL)", trunc(V, dim), trunc(Q, dim), 1))
    for k in (128, 64):
        mu, comps, evr = pca_fit(V, k)
        variants.append((f"pca-{k} (evr {evr:.0%})", pca_apply(V, mu, comps),
                         pca_apply(Q, mu, comps), 1))

    rows, misses = [], {}
    for name, Vv, Qv, _bytes in variants:
        m = {"vector": {"recall": 0, "mrr": 0.0}, "hybrid": {"recall": 0, "mrr": 0.0}}
        for i, q in enumerate(qs):
            vec = [str(domains[j]) for j in np.argsort(-(Vv @ Qv[i]))[:N]]
            hyb = [d for d, _ in rrf([bm[i], vec], N)]
            for mode, ranked in (("vector", vec), ("hybrid", hyb)):
                if q["domain"] in ranked:
                    m[mode]["recall"] += 1
                    m[mode]["mrr"] += 1.0 / (ranked.index(q["domain"]) + 1)
                elif mode == "hybrid":
                    misses.setdefault(name, []).append(q["question"])
        rows.append((name, Vv.shape[1], m))

    base_h = rows[0][2]["hybrid"]["recall"] / len(qs)
    lines = ["# Vector shrink eval — int8 / truncation / PCA", "",
             f"Model `{model_id}` · {len(qs)} questions · {N_DOCS:,} docs · ranking math "
             "identical to on-device int8 scoring (per-vector absmax scale).", "",
             "| variant | dim | B/vec (int8 storage) | total MB | vector R@10 | vector MRR | "
             "hybrid R@10 | hybrid MRR | Δ hybrid recall |", "|---|---|---|---|---|---|---|---|---|"]
    for name, dim, m in rows:
        mb = N_DOCS * dim / 1e6  # int8 storage: 1 byte/dim
        hr = m["hybrid"]["recall"] / len(qs)
        lines.append(f"| {name} | {dim} | {dim} | {mb:.1f} | "
                     f"{m['vector']['recall']/len(qs):.0%} | {m['vector']['mrr']/len(qs):.2f} | "
                     f"{hr:.0%} | {m['hybrid']['mrr']/len(qs):.2f} | "
                     f"{(hr - base_h)*100:+.0f}pp |")
    for name, qs_miss in misses.items():
        lines += ["", f"## {name} — hybrid misses ({len(qs_miss)})",
                  *[f"- {q}" for q in qs_miss]]
    Path(args.report).write_text("\n".join(lines))
    print("\n".join(lines))
    print(f"\nwrote {args.report}")


if __name__ == "__main__":
    main()

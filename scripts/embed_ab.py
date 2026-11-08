#!/usr/bin/env python3
"""Stage 4a: A/B embedding models — bge-m3 vs Qwen3-Embedding-0.6B.

Retrieval sanity over the 50 A/B extraction profiles: for ~10 probe queries
(built from real profiles' keywords/intents), check where the target domain
ranks under each model. Also measures encode speed. Writes
efforts/<effort>/embed_ab_report.md

Usage: .venv/bin/python scripts/embed_ab.py [--profiles efforts/.../ab/glm-5.3-flash.jsonl]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
EFFORT = ROOT / "efforts" / "2026-11-07-amenity-knowledge-base"

MODELS = {
    "bge-m3": {"st": "BAAI/bge-m3", "query_prefix": ""},
    "qwen3-0.6b": {"st": "Qwen/Qwen3-Embedding-0.6B",
                   "query_prefix": "Instruct: Given a search query, retrieve the California "
                                   "amenity that best matches\nQuery: "},
}


def profile_text(p: dict) -> str:
    kw = " ".join(p.get("keywords") or [])
    return f"{p.get('self_introduction') or ''}\n{p.get('detailed_profile') or ''}\n{kw}".strip()


def load_profiles(path: Path) -> list[dict]:
    rows = [json.loads(l) for l in path.read_text().splitlines()]
    return [r["profile"] for r in rows if r.get("profile") and r["profile"].get("is_useful")]


def normalize(v: np.ndarray) -> np.ndarray:
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def evaluate(model_name: str, cfg: dict, profiles: list[dict], probes: list[tuple[str, str]]):
    from sentence_transformers import SentenceTransformer
    st = SentenceTransformer(cfg["st"], device="cuda")
    texts = [profile_text(p) for p in profiles]
    t0 = time.time()
    doc_vecs = normalize(st.encode(texts, batch_size=32, show_progress_bar=False))
    dt = time.time() - t0
    domains = [p.get("name") or "" for p in profiles]

    hits1, ranks = 0, []
    for query, target_name in probes:
        qv = normalize(st.encode([cfg["query_prefix"] + query]))[0]
        scores = doc_vecs @ qv
        order = np.argsort(-scores)
        target_idx = domains.index(target_name) if target_name in domains else -1
        rank = int(np.where(order == target_idx)[0][0]) + 1 if target_idx >= 0 else 999
        ranks.append(rank)
        hits1 += rank == 1
    mrr = float(np.mean([1 / r if r < 999 else 0 for r in ranks]))
    del st
    import torch, gc
    gc.collect(); torch.cuda.empty_cache()
    return {"model": model_name, "hit@1": hits1, "mrr": mrr,
            "median_rank": float(np.median([r if r < 999 else 50 for r in ranks])),
            "encode_s_per_doc": dt / len(texts)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profiles", default=str(EFFORT / "ab" / "glm-5.3-flash.jsonl"))
    ap.add_argument("--n-probes", type=int, default=10)
    args = ap.parse_args()

    profiles = load_profiles(Path(args.profiles))
    print(f"profiles: {len(profiles)} from {args.profiles}")

    # probe queries: handcrafted searches targeting 10 known profile names
    rng = np.random.default_rng(42)
    idx = rng.choice(len(profiles), size=min(args.n_probes, len(profiles)), replace=False)
    probes = []
    for i in idx:
        p = profiles[int(i)]
        kw = (p.get("keywords") or ["amenity"])[:3]
        probes.append((" ".join(kw), p.get("name") or ""))
    print(f"probes: {len(probes)}")

    results = [evaluate(m, cfg, profiles, probes) for m, cfg in MODELS.items()]
    lines = [f"# Embedding A/B ({len(profiles)} profiles, {len(probes)} probes)", "",
             "| model | hit@1 | MRR | median rank | encode s/doc |",
             "|---|---|---|---|---|"]
    for r in results:
        lines.append(f"| {r['model']} | {r['hit@1']} | {r['mrr']:.2f} | "
                     f"{r['median_rank']:.0f} | {r['encode_s_per_doc']:.4f} |")
    lines += ["", "## Probes", ""] + [f"- `{q}` → {t}" for q, t in probes]
    out = EFFORT / "embed_ab_report.md"
    out.write_text("\n".join(lines))
    print("\n".join(lines))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()

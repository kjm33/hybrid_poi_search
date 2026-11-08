#!/usr/bin/env python3
"""Bakeoff P4: per-model size + single-query CPU encode latency (the car-relevant number).

Run after models are cached (HF_HOME=/opt/vllm/models/hf):
    HF_HOME=/opt/vllm/models/hf .venv/bin/python scripts/bakeoff_latency.py
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from search import QUERY_PREFIX, ST_IDS

ROOT = Path(__file__).resolve().parents[1]
MODELS = ["bge-m3", "gte-modernbert", "arctic-s"]
QUERIES = [
    "coffee nearby", "cheap sushi berkeley", "gas station along the route",
    "kid friendly dentist in oakland", "date night restaurant san jose",
    "24 hour pharmacy", "gluten free bakery", "dog park", "ev charging station",
    "late night ramen", "bookstore with cafe", "best pizza sacramento",
    "vet open saturday", "craft beer garden", "museum gift shop",
    "vegan brunch", "laundry drop off", "pool hall", "hiking gear rental",
    "toy store",
]


def main() -> None:
    import torch
    from sentence_transformers import SentenceTransformer

    rows = []
    for key in MODELS:
        # fp32: gte ships fp16 weights, which CPUs emulate ~25x slower -> dishonest numbers
        st = SentenceTransformer(ST_IDS[key], device="cpu", model_kwargs={"dtype": torch.float32})
        # warmup
        st.encode(["warmup query"])
        prefix = QUERY_PREFIX.get(key, "")
        times = []
        for q in QUERIES:
            t0 = time.perf_counter()
            v = st.encode([prefix + q])[0]
            times.append((time.perf_counter() - t0) * 1000)
            dim = len(v)
        times_ms = np.array(times)
        row = {
            "model": key,
            "dim": int(dim),
            "q_encode_ms_mean": round(float(times_ms.mean()), 1),
            "q_encode_ms_p95": round(float(np.percentile(times_ms, 95)), 1),
            "kb_per_doc_fp32": int(dim * 4),
            "corpus_vec_mb_fp32_13199": round(dim * 4 * 13199 / 1e6, 1),
            "corpus_vec_mb_int8_13199": round(dim * 1 * 13199 / 1e6, 1),
        }
        rows.append(row)
        print(json.dumps(row), flush=True)
    out = ROOT / "efforts" / "2026-11-08-edge-embedder-bakeoff" / "eval" / "latency.json"
    out.write_text(json.dumps(rows, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

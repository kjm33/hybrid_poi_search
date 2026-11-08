#!/usr/bin/env python3
"""Stage 4c: HDBSCAN clustering over kb.db embeddings → clusters table + QA report.

Uses cosine metric on unit vectors. Noise points get cluster = -1.
Report: cluster sizes, top shared keywords/names per big cluster, small-cluster
and noise QA samples (residual garbage / facet candidates).

Usage: .venv/bin/python scripts/cluster.py --model bge-m3 [--min-cluster-size 15]
        [--no-umap] [--n-neighbors 30] [--dim 10]

Default path: UMAP (cosine → --dim dims) then HDBSCAN (euclidean) — raw 1024-dim
cosine gives only ~5 globular clusters + 73% noise; UMAP first is standard.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import time
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "kb.db"
REPORT = ROOT / "efforts" / "2026-11-07-amenity-knowledge-base" / "cluster_qa.md"

SCHEMA = """
CREATE TABLE IF NOT EXISTS clusters (
    domain TEXT, model TEXT, cluster INTEGER,
    PRIMARY KEY (domain, model)
);
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="bge-m3")
    ap.add_argument("--min-cluster-size", type=int, default=15)
    ap.add_argument("--no-umap", action="store_true", help="skip UMAP, cluster raw cosine")
    ap.add_argument("--n-neighbors", type=int, default=30)
    ap.add_argument("--dim", type=int, default=10)
    args = ap.parse_args()

    from sklearn.cluster import HDBSCAN

    con = sqlite3.connect(DB)
    con.executescript(SCHEMA)
    con.row_factory = sqlite3.Row

    rows = con.execute(
        "SELECT e.domain, e.vec FROM embeddings e "
        "JOIN profiles p ON p.domain = e.domain AND p.is_useful = 1 "
        "WHERE e.model = ?", (args.model,)).fetchall()
    if not rows:
        raise SystemExit(f"no embeddings for model {args.model!r} — run embed_all.py first")
    domains = [r["domain"] for r in rows]
    V = np.stack([np.frombuffer(r["vec"], dtype=np.float32) for r in rows])
    V /= np.linalg.norm(V, axis=1, keepdims=True) + 1e-12
    print(f"{len(domains)} vectors, dim={V.shape[1]}", flush=True)

    t0 = time.time()
    X = V
    how = f"cosine (raw), min_cluster_size={args.min_cluster_size}"
    if not args.no_umap:
        import umap
        X = umap.UMAP(n_neighbors=args.n_neighbors, n_components=args.dim,
                      metric="cosine", min_dist=0.0, random_state=42).fit_transform(V)
        how = (f"UMAP(cosine→{args.dim}d, n_neighbors={args.n_neighbors}) + "
               f"HDBSCAN(euclidean), min_cluster_size={args.min_cluster_size}")
        print(f"UMAP done in {time.time()-t0:.0f}s", flush=True)
    labels = HDBSCAN(min_cluster_size=args.min_cluster_size,
                     cluster_selection_method="eom").fit_predict(X)
    n_clusters = len(set(labels) - {-1})
    n_noise = int((labels == -1).sum())
    print(f"HDBSCAN done in {time.time()-t0:.0f}s: {n_clusters} clusters, {n_noise} noise "
          f"({n_noise/len(labels):.0%})", flush=True)

    con.execute("DELETE FROM clusters WHERE model=?", (args.model,))
    con.executemany("INSERT INTO clusters VALUES (?,?,?)",
                    [(d, args.model, int(c)) for d, c in zip(domains, labels)])
    con.commit()

    # ---- QA report ----
    prof = {r["domain"]: r for r in con.execute(
        "SELECT domain, name, osm_type, keywords FROM profiles WHERE is_useful=1")}
    sizes = Counter(labels.tolist())
    lines = [f"# Cluster QA — {args.model}, {how}", "",
             f"- vectors: {len(domains)}  clusters: {n_clusters}  noise: {n_noise} "
             f"({n_noise/len(labels):.0%})", "", "## Clusters by size", "",
             "| cluster | n | top keywords | sample names |", "|---|---|---|---|"]
    for cl, n in sizes.most_common(30):
        if cl == -1 or n < 3:
            continue
        members = [domains[i] for i, c in enumerate(labels) if c == cl][:200]
        kw = Counter()
        for d in members:
            p = prof.get(d)
            if p:
                kw.update(k.strip().lower() for k in json.loads(p["keywords"] or "[]"))
        top_kw = ", ".join(w for w, _ in kw.most_common(6))
        names = "; ".join((prof[d]["name"] or d) for d in members[:4] if d in prof)
        lines.append(f"| {cl} | {n} | {top_kw} | {names} |")

    # smallest clusters + noise sample → residual garbage / facet candidates
    lines += ["", "## Smallest clusters (QA: garbage?)", ""]
    small = [cl for cl, n in sorted(sizes.items(), key=lambda x: x[1]) if cl != -1 and n < args.min_cluster_size * 2]
    for cl in small[:15]:
        members = [domains[i] for i, c in enumerate(labels) if c == cl]
        lines.append(f"- cluster {cl} (n={sizes[cl]}): "
                     + "; ".join((prof[d]["name"] or d) for d in members[:5] if d in prof))
    noise_idx = [i for i, c in enumerate(labels) if c == -1]
    if noise_idx:
        import random
        random.seed(0)
        sample = random.sample(noise_idx, min(25, len(noise_idx)))
        lines += ["", "## Noise sample (25 random unclustered) — usually legit but unusual pages", ""]
        for i in sample:
            d = domains[i]
            p = prof.get(d)
            if p:
                lines.append(f"- {d} — {p['name']} [{p['osm_type']}]")

    REPORT.write_text("\n".join(lines) + "\n")
    print(f"report → {REPORT}")
    con.close()


if __name__ == "__main__":
    main()

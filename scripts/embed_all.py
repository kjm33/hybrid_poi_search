#!/usr/bin/env python3
"""Stage 4b: embed all useful profiles with the chosen model → kb.db.embeddings.

Also detects near-duplicates (cosine > 0.97) → kb.db.near_dups (chains, mirrors).
Resumable: embeddings keyed by (domain, model); re-run skips existing rows.

Usage: .venv/bin/python scripts/embed_all.py --model bge-m3 | qwen3-0.6b [--reembed]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "kb.db"
ST_IDS = {"bge-m3": "BAAI/bge-m3", "qwen3-0.6b": "Qwen/Qwen3-Embedding-0.6B",
          "gte-modernbert": "Alibaba-NLP/gte-modernbert-base",
          "arctic-s": "Snowflake/snowflake-arctic-embed-s"}
DUP_THRESHOLD = 0.97

SCHEMA = """
CREATE TABLE IF NOT EXISTS embeddings (
    domain TEXT, model TEXT, dim INTEGER, vec BLOB,
    embedded_at TEXT,
    PRIMARY KEY (domain, model)
);
CREATE TABLE IF NOT EXISTS near_dups (
    domain TEXT, dup_of TEXT, sim REAL, PRIMARY KEY (domain, dup_of)
);
"""


def profile_text(p: sqlite3.Row) -> str:
    kw = " ".join(json.loads(p["keywords"] or "[]"))
    return f"{p['self_introduction'] or ''}\n{p['detailed_profile'] or ''}\n{kw}".strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="bge-m3", choices=sorted(ST_IDS))
    ap.add_argument("--reembed", action="store_true", help="re-embed even if rows exist")
    ap.add_argument("--device", default="cuda", help="cpu | cuda (cuda needs ~2 GB free)")
    ap.add_argument("--skip-dups", action="store_true",
                    help="don't rewrite kb.db.near_dups (keeps the current model's pairs)")
    args = ap.parse_args()

    from sentence_transformers import SentenceTransformer

    con = sqlite3.connect(DB)
    con.executescript(SCHEMA)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT domain, self_introduction, detailed_profile, keywords FROM profiles "
        "WHERE is_useful=1").fetchall()
    done = set() if args.reembed else {
        r[0] for r in con.execute("SELECT domain FROM embeddings WHERE model=?", (args.model,))}
    todo = [r for r in rows if r["domain"] not in done]
    print(f"useful profiles: {len(rows)} | embedded: {len(done)} | to embed: {len(todo)}", flush=True)

    st = SentenceTransformer(ST_IDS[args.model], device=args.device)
    t0 = time.time()
    B = 256
    for i in range(0, len(todo), B):
        batch = todo[i:i + B]
        vecs = st.encode([profile_text(r) for r in batch], batch_size=64, show_progress_bar=False)
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        con.executemany(
            "INSERT OR REPLACE INTO embeddings VALUES (?,?,?,?,?)",
            [(r["domain"], args.model, len(v), np.asarray(v, dtype=np.float32).tobytes(), ts)
             for r, v in zip(batch, vecs)])
        con.commit()
        if (i // B) % 10 == 0:
            el = time.time() - t0
            done_n = min(i + len(batch), len(todo))
            print(f"  {done_n}/{len(todo)} ({el:.0f}s, {done_n/max(el,1):.1f}/s)", flush=True)

    # ---- near-duplicate detection over all vectors of this model ----
    if args.skip_dups:
        print("near-dup scan skipped (--skip-dups)")
        con.close()
        print(f"done in {time.time()-t0:.0f}s")
        return
    vecs, domains = [], []
    for domain, blob in con.execute("SELECT domain, vec FROM embeddings WHERE model=?", (args.model,)):
        domains.append(domain)
        vecs.append(np.frombuffer(blob, dtype=np.float32))
    V = np.stack(vecs)
    V /= np.linalg.norm(V, axis=1, keepdims=True) + 1e-12
    n = len(domains)
    print(f"near-dup scan over {n} vectors…", flush=True)
    con.execute("DELETE FROM near_dups")
    dups = 0
    for i in range(0, n, 2048):  # chunked to keep the sim matrix < ~1 GB
        S = V[i:i + 2048] @ V.T  # (chunk, n)
        for ci, si in enumerate(S):
            gi = i + ci
            hit = np.where((si > DUP_THRESHOLD) & (np.arange(n) != gi))[0]
            for j in hit:
                lo, hi = sorted((domains[gi], domains[int(j)]))
                con.execute("INSERT OR IGNORE INTO near_dups VALUES (?,?,?)", (hi, lo, float(si[j])))
                dups += 1
        con.commit()
    pairs = con.execute("SELECT COUNT(*) FROM near_dups").fetchone()[0]
    print(f"near-dups (cos > {DUP_THRESHOLD}): {pairs} pairs")
    con.close()
    print(f"done in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()

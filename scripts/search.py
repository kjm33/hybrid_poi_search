#!/usr/bin/env python3
"""Stage 5b: hybrid search CLI over data/search.db — BM25 (FTS5) + vector cosine,
fused with Reciprocal Rank Fusion. Manual door (human table) and agent door (--json).

Examples:
    .venv/bin/python scripts/search.py "gluten free bakery berkeley"
    .venv/bin/python scripts/search.py "date night sushi" --facet type=bar city=oakland -n 5
    .venv/bin/python scripts/search.py --facets                # facet browsing
    .venv/bin/python scripts/search.py --show zushipuzzle.com  # full profile
    .venv/bin/python scripts/search.py "kid friendly dentist" --json
    .venv/bin/python scripts/search.py "ramen" --mode bm25|vector|hybrid
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "search.db"
ST_IDS = {"bge-m3": "BAAI/bge-m3", "qwen3-0.6b": "Qwen/Qwen3-Embedding-0.6B"}
QUERY_PREFIX = {
    "qwen3-0.6b": "Instruct: Given a search query, retrieve the California amenity "
                  "that best matches\nQuery: ",
}
RRF_K = 60

# facet key (CLI) -> (docs column | facets kind, where-clause style)
FACET_KEYS = {
    "type": "docs.osm_type",
    "city": "docs.city",
    "price": "docs.price_level",
    "page_type": "docs.page_type",
}


def get_model_id(con: sqlite3.Connection) -> str:
    row = con.execute("SELECT value FROM meta WHERE key='model'").fetchone()
    return row[0] if row else "bge-m3"


def load_vectors(con: sqlite3.Connection):
    rows = con.execute("SELECT domain, vec FROM docs WHERE vec IS NOT NULL").fetchall()
    domains = np.array([r[0] for r in rows], dtype=object)
    V = np.stack([np.frombuffer(r[1], dtype=np.float32) for r in rows])
    V /= np.linalg.norm(V, axis=1, keepdims=True) + 1e-12
    return domains, V


def fts_query(q: str) -> str:
    toks = re.findall(r"[a-zA-Z0-9']+", q)
    return " OR ".join(f'"{t}"' for t in toks if len(t) > 1)


def bm25_leg(con, q, cand_domains, n):
    fts_q = fts_query(q)
    if not fts_q:
        return []
    sql = ("SELECT domain, bm25(search_fts) AS score FROM search_fts "
           "WHERE search_fts MATCH ? ORDER BY score LIMIT ?")
    rows = con.execute(sql, (fts_q, max(n * 4, 100))).fetchall()
    if cand_domains is not None:
        cand = set(cand_domains)
        rows = [r for r in rows if r[0] in cand]
    return [r[0] for r in rows[:n]]


def vector_leg(qvec_norm, domains, V, cand_domains, n):
    sims = V @ qvec_norm
    if cand_domains is not None:
        mask = np.isin(domains, list(cand_domains))
        sims = np.where(mask, sims, -1.0)
    order = np.argsort(-sims)[:n]
    return [str(domains[i]) for i in order if sims[i] > -1.0]


def rrf(ranklists: list[list[str]], n: int) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for lst in ranklists:
        for rank, d in enumerate(lst, 1):
            scores[d] = scores.get(d, 0.0) + 1.0 / (RRF_K + rank)
    return sorted(scores.items(), key=lambda kv: -kv[1])[:n]


def facet_where(filters: list[str]) -> tuple[str, list[str]]:
    clauses, params = [], []
    for f in filters:
        key, _, val = f.partition("=")
        key = key.strip().lower()
        val = val.strip().lower()
        if key in FACET_KEYS:
            clauses.append(f"lower(coalesce({FACET_KEYS[key]},'')) = ?")
            params.append(val)
        else:  # feature/intent/cuisine via facets table
            clauses.append(
                f"domain IN (SELECT domain FROM facets WHERE kind=? AND lower(value)=?)")
            params.extend([{"feature": "feature", "intent": "intent",
                            "cuisine": "cuisine"}.get(key, key), val])
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def candidates_for_filters(con, filters):
    if not filters:
        return None
    where, params = facet_where(filters)
    return [r[0] for r in con.execute("SELECT domain FROM docs" + where, params)]


def search(con, q, model_id, st, domains, V, filters, n, mode):
    cand = candidates_for_filters(con, filters)
    legs = []
    if mode in ("hybrid", "bm25"):
        legs.append(bm25_leg(con, q, cand, n * 2))
    if mode in ("hybrid", "vector"):
        if st is None or V is None or len(V) == 0:
            raise SystemExit("no vectors in search.db — build with build_search.py first "
                             "(or use --mode bm25)")
        qv = st.encode([QUERY_PREFIX.get(model_id, "") + q])[0]
        qv = qv / (np.linalg.norm(qv) + 1e-12)
        legs.append(vector_leg(qv, domains, V, cand, n * 2))
    return rrf(legs, n) if mode == "hybrid" else [(d, 0.0) for d in legs[0]]


def show_results(con, hits, q, mode, elapsed, as_json):
    docs = {}
    for d, _ in hits:
        r = con.execute("SELECT * FROM docs WHERE domain=?", (d,)).fetchone()
        if r:
            docs[d] = dict(r)
    if as_json:
        out = {"query": q, "mode": mode, "elapsed_ms": round(elapsed * 1000, 1),
               "results": []}
        for d, s in hits:
            doc = docs.get(d, {})
            for k in ("keywords", "intents", "features"):
                try:
                    doc[k] = json.loads(doc.get(k) or "[]")
                except (json.JSONDecodeError, TypeError):
                    doc[k] = []
            doc["rrf_score"] = round(s, 5)
            doc["vec"] = None
            out["results"].append(doc)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return
    if not hits:
        print(f"no results for {q!r}")
        return
    print(f"\n  query: {q!r}   mode={mode}   {len(hits)} hits   {elapsed*1000:.0f} ms\n")
    for i, (d, s) in enumerate(hits, 1):
        doc = docs.get(d, {})
        intro = (doc.get("self_introduction") or "")[:110]
        meta = " · ".join(x for x in (doc.get("osm_type"), doc.get("city"),
                                      doc.get("price_level")) if x)
        print(f"{i:>2}. {doc.get('name') or d}   [{meta}]  rrf={s:.3f}")
        print(f"      {d}  —  {intro}…")
    print()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query", nargs="*", help="natural-language search query")
    ap.add_argument("-n", type=int, default=10)
    ap.add_argument("--mode", choices=["hybrid", "bm25", "vector"], default="hybrid")
    ap.add_argument("--facet", action="append", default=[],
                    help="filter: type=restaurant city=oakland price=upscale intent=... "
                         "(repeatable)")
    ap.add_argument("--json", action="store_true", help="machine-readable output (agent door)")
    ap.add_argument("--facets", action="store_true", help="list facet values with counts")
    ap.add_argument("--show", metavar="DOMAIN", help="print full profile for a domain")
    args = ap.parse_args()

    if not DB.exists():
        sys.exit(f"missing {DB} — run scripts/build_search.py first")
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row

    if args.facets:
        for kind in ("osm_type", "city", "price", "cuisine"):
            k = "osm_type" if kind == "osm_type" else kind
            if kind == "osm_type":
                rows = con.execute("SELECT osm_type v, COUNT(*) n FROM docs "
                                   "WHERE osm_type IS NOT NULL GROUP BY v ORDER BY n DESC "
                                   "LIMIT 25").fetchall()
            else:
                rows = con.execute("SELECT value v, COUNT(*) n FROM facets WHERE kind=? "
                                   "GROUP BY v ORDER BY n DESC LIMIT 25", (k,)).fetchall()
            print(f"\n{k}: " + ", ".join(f"{r['v']} ({r['n']})" for r in rows))
        return

    if args.show:
        r = con.execute("SELECT * FROM docs WHERE domain=?", (args.show,)).fetchone()
        if not r:
            sys.exit(f"domain {args.show!r} not in search.db")
        d = dict(r)
        d.pop("vec", None)
        for k in ("keywords", "intents", "features"):
            d[k] = json.loads(d.get(k) or "[]")
        print(json.dumps(d, ensure_ascii=False, indent=2))
        return

    q = " ".join(args.query).strip()
    if not q:
        ap.error("provide a query, --facets, or --show DOMAIN")

    st, domains, V = None, None, None
    model_id = get_model_id(con)
    if args.mode in ("hybrid", "vector"):
        t0 = time.time()
        from sentence_transformers import SentenceTransformer
        import torch
        st = SentenceTransformer(ST_IDS[model_id], device="cuda" if torch.cuda.is_available() else "cpu")
        domains, V = load_vectors(con)
        t0 = time.time() - t0
        print(f"[index: {model_id}, {len(domains)} vectors, model load {t0:.1f}s]",
              file=sys.stderr)

    t0 = time.time()
    hits = search(con, q, model_id, st, domains, V, args.facet, args.n, args.mode)
    elapsed = time.time() - t0
    show_results(con, hits, q, args.mode, elapsed, args.json)
    con.close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Stage 6: MCP server exposing the amenity knowledge base to agents.

Tools:
    search(query, type=None, city=None, price=None, intent=None, feature=None,
           n=10, mode="hybrid")  -> matching domains with profiles
    get_profile(domain)          -> full profile record
    facets(kind=None)            -> facet values with counts (what can be filtered)

Run (stdio): .venv/bin/python scripts/kb_mcp.py
Register in opencode.json:
  { "mcp": { "amenity-kb": { "type": "local",
      "command": ".venv/bin/python", "args": ["scripts/kb_mcp.py"] } } }

Uses CPU for the query embedder on purpose: one bge-m3 encode is ~100 ms on
CPU and the GPUs are shared with training jobs.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

DB = ROOT / "data" / "search.db"
ST_IDS = {"bge-m3": "BAAI/bge-m3", "qwen3-0.6b": "Qwen/Qwen3-Embedding-0.6B"}

from mcp.server.mcpserver import MCPServer  # noqa: E402  (mcp 2.x; v1 name was FastMCP)

mcp = MCPServer("amenity-kb")

_con: sqlite3.Connection | None = None
_st = None
_domains = None
_V = None
_model_id = "bge-m3"


def _init() -> None:
    global _con, _st, _domains, _V, _model_id
    if _con is not None:
        return
    if not DB.exists():
        raise SystemExit(f"missing {DB} — run scripts/build_search.py first")
    # check_same_thread=False: mcp 2.x runs tool handlers in worker threads;
    # DB is opened read-only so cross-thread sharing is safe.
    _con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True,
                           check_same_thread=False)
    _con.row_factory = sqlite3.Row
    row = _con.execute("SELECT value FROM meta WHERE key='model'").fetchone()
    _model_id = row[0] if row else "bge-m3"
    try:
        from search import QUERY_PREFIX, load_vectors
        from sentence_transformers import SentenceTransformer
        _st = SentenceTransformer(ST_IDS[_model_id], device="cpu")
        _domains, _V = load_vectors(_con)
    except Exception as e:  # degrade to BM25-only if model/vectors unavailable
        print(f"[kb_mcp] vector search unavailable: {e!r}", file=sys.stderr)


def _doc(domain: str) -> dict | None:
    r = _con.execute("SELECT * FROM docs WHERE domain=?", (domain,)).fetchone()
    if not r:
        return None
    d = {k: r[k] for k in r.keys() if k != "vec"}
    for k in ("keywords", "intents", "features"):
        try:
            d[k] = json.loads(d.get(k) or "[]")
        except (json.JSONDecodeError, TypeError):
            d[k] = []
    return d


@mcp.tool()
def search(query: str, type: str | None = None, city: str | None = None,
           price: str | None = None, intent: str | None = None,
           feature: str | None = None, n: int = 10,
           mode: str = "hybrid") -> str:
    """Search California amenity knowledge base.

    Args:
        query: natural-language search query
        type/city/price: facet filters (see `facets` tool for valid values)
        intent/feature: match against profile intents/features
        n: max results (default 10)
        mode: hybrid | bm25 | vector
    """
    _init()
    from search import bm25_leg, rrf, vector_leg
    filters = []
    for key, val in (("type", type), ("city", city), ("price", price),
                     ("intent", intent), ("feature", feature)):
        if val:
            filters.append(f"{key}={val.lower()}")
    cand = None
    if filters:
        from search import candidates_for_filters
        cand = candidates_for_filters(_con, filters)
        if not cand:
            return json.dumps({"results": [], "note": "facet filter matched nothing"})
    legs = []
    if mode in ("hybrid", "bm25"):
        legs.append(bm25_leg(_con, query, cand, n * 2))
    if mode in ("hybrid", "vector") and _st is not None:
        from search import QUERY_PREFIX
        qv = _st.encode([QUERY_PREFIX.get(_model_id, "") + query])[0]
        import numpy as np
        qv = qv / (np.linalg.norm(qv) + 1e-12)
        legs.append(vector_leg(qv, _domains, _V, cand, n * 2))
    hits = rrf(legs, n) if len(legs) > 1 else [(d, 0.0) for d in legs[0][:n]] if legs else []
    results = []
    for d, s in hits:
        doc = _doc(d)
        if doc:
            doc["rrf_score"] = round(s, 5)
            results.append(doc)
    return json.dumps({"query": query, "mode": mode, "results": results},
                      ensure_ascii=False)


@mcp.tool()
def get_profile(domain: str) -> str:
    """Full knowledge-base record for one amenity domain (e.g. 'zushipuzzle.com')."""
    _init()
    doc = _doc(domain)
    if not doc:
        return json.dumps({"error": f"unknown domain {domain!r}"})
    fac = _con.execute("SELECT kind, value FROM facets WHERE domain=?", (domain,)).fetchall()
    doc["facets"] = {k: v for k, v in fac}
    return json.dumps(doc, ensure_ascii=False)


@mcp.tool()
def facets(kind: str | None = None) -> str:
    """Facet values with counts. kind: osm_type | city | price | cuisine | feature |
    intent. Omit kind for a summary of all kinds."""
    _init()
    out = {}
    kinds = [kind] if kind else ["osm_type", "city", "price", "cuisine", "feature", "intent"]
    for k in kinds:
        if k == "osm_type":
            rows = _con.execute(
                "SELECT osm_type v, COUNT(*) n FROM docs WHERE osm_type IS NOT NULL "
                "GROUP BY v ORDER BY n DESC LIMIT 50").fetchall()
        else:
            rows = _con.execute(
                "SELECT value v, COUNT(*) n FROM facets WHERE kind=? GROUP BY v "
                "ORDER BY n DESC LIMIT 50", (k,)).fetchall()
        out[k] = [(r["v"], r["n"]) for r in rows]
    return json.dumps(out, ensure_ascii=False)


if __name__ == "__main__":
    _init()
    mcp.run()

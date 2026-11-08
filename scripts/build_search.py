#!/usr/bin/env python3
"""Stage 5a: build data/search.db — self-contained hybrid search index.

From kb.db (profiles, embeddings, facets, near_dups) + enrichment.db (page titles):
- docs       : one row per useful profile (+ vector BLOB)
- search_fts : FTS5 over name/title/keywords/self_intro/intents/features/detailed_profile
- facets     : copied dictionary (kind, value, domain)
- near_dups  : informational (cos > 0.97 pairs — some are template-similar distinct
               businesses, so nothing is dropped; use for display hints later)
- meta       : model, counts, built_at

Usage: .venv/bin/python scripts/build_search.py --model bge-m3
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data" / "kb.db"
ENRICH = ROOT / "data" / "enrichment.db"
OUT = ROOT / "data" / "search.db"

SCHEMA = """
DROP TABLE IF EXISTS docs;
CREATE TABLE docs (
    domain TEXT PRIMARY KEY,
    name TEXT, osm_type TEXT, city TEXT, price_level TEXT, page_type TEXT,
    title TEXT, url TEXT,
    self_introduction TEXT, short_description TEXT, detailed_profile TEXT,
    keywords TEXT, intents TEXT, features TEXT,
    opening_hours TEXT, location TEXT,
    vec BLOB
);
CREATE INDEX idx_docs_osm_type ON docs(osm_type);
CREATE INDEX idx_docs_city ON docs(city);
CREATE INDEX idx_docs_price ON docs(price_level);
DROP TABLE IF EXISTS facets;
CREATE TABLE facets (
    domain TEXT, kind TEXT, value TEXT,
    PRIMARY KEY (domain, kind, value)
) WITHOUT ROWID;
CREATE INDEX idx_facets_kind_value ON facets(kind, value);
CREATE VIRTUAL TABLE search_fts USING fts5(
    domain, name, title, keywords, self_intro, intents, features, detailed_profile,
    tokenize='porter unicode61'
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS near_dups (
    domain TEXT, dup_of TEXT, sim REAL,
    PRIMARY KEY (domain, dup_of)
);
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="bge-m3", help="which embedding model's vectors to copy")
    args = ap.parse_args()

    kb = sqlite3.connect(f"file:{KB}?mode=ro", uri=True)
    kb.row_factory = sqlite3.Row
    enrich = sqlite3.connect(f"file:{ENRICH}?mode=ro", uri=True)
    titles = {r[0]: (r[1] or "", r[2] or "")
              for r in enrich.execute("SELECT domain, title, fm_url FROM page_quality")}
    enrich.close()

    out = sqlite3.connect(OUT)
    out.executescript(SCHEMA)
    out.row_factory = sqlite3.Row

    rows = kb.execute("SELECT * FROM profiles WHERE is_useful=1").fetchall()
    vecs = {r[0]: r[1] for r in kb.execute("SELECT domain, vec FROM embeddings WHERE model=?",
                                           (args.model,))}
    fts_batch, doc_batch = [], []
    n_vec = 0
    for r in rows:
        city = ""
        c = kb.execute("SELECT value FROM facets WHERE domain=? AND kind='city'",
                       (r["domain"],)).fetchone()
        if c:
            city = c[0]
        title, url = titles.get(r["domain"], ("", ""))
        vec = vecs.get(r["domain"])
        if vec:
            n_vec += 1
        doc_batch.append((
            r["domain"], r["name"], r["osm_type"], city, r["price_level"], r["page_type"],
            title, url,
            r["self_introduction"], r["short_description"], r["detailed_profile"],
            r["keywords"], r["intents"], r["features"], r["opening_hours"], r["location"],
            vec))
        fts_batch.append((
            r["domain"], r["name"] or "", title or "", r["keywords"] or "",
            r["self_introduction"] or "", r["intents"] or "", r["features"] or "",
            (r["detailed_profile"] or "")[:20000]))
    out.executemany("INSERT OR REPLACE INTO docs VALUES ("
                    + ",".join(["?"] * 17) + ")", doc_batch)
    out.executemany("INSERT INTO search_fts VALUES (?,?,?,?,?,?,?,?)", fts_batch)
    for r in kb.execute("SELECT domain, kind, value FROM facets"):
        out.execute("INSERT OR IGNORE INTO facets VALUES (?,?,?)", tuple(r))
    n_dups = 0
    for r in kb.execute("SELECT domain, dup_of, sim FROM near_dups"):
        out.execute("INSERT OR IGNORE INTO near_dups VALUES (?,?,?)", tuple(r))
        n_dups += 1
    meta = {
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model": args.model,
        "docs": len(doc_batch),
        "with_vectors": n_vec,
        "near_dups": n_dups,
        "profiles_useful": len(rows),
    }
    for k, v in meta.items():
        out.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (k, str(v)))
    out.commit()
    out.close()
    kb.close()
    print(f"search.db built: {meta}")


if __name__ == "__main__":
    main()

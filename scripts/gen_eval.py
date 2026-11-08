#!/usr/bin/env python3
"""Stage 5c-1: generate eval questions from real profiles (query-by-document).

For a sample of useful profiles, ask GLM to write realistic user queries whose
best answer is that amenity. Output: efforts/<effort>/eval/questions.jsonl
{question, domain, name}.

Usage: python3 scripts/gen_eval.py [--n 60]
"""
from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from zai_client import chat, usage_report  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "search.db"
OUT = ROOT / "efforts" / "2026-11-07-amenity-knowledge-base" / "eval"

STYLES = [
    "2-4 keywords, like a search box (e.g. 'vegan brunch pasadena')",
    "a short natural-language question (e.g. 'where can I get gluten-free cake in Berkeley?')",
    "an intent or use case, no place name (e.g. 'kid friendly weekend dinner')",
]

PROMPT = """You write test queries for a California amenity search engine.
Below is the profile of one amenity. Write ONE realistic query a person might type
when looking for exactly this kind of place. Style: {style}.
Rules: do NOT include the business name or domain in the query; keep it under 12 words;
include distinguishing traits (cuisine, service, vibe) if notable. Location may be
included only if a city/area is in the profile. Return ONLY the query text, nothing else.

Profile:
name: {name}
domain: {domain}
type: {type}
location: {location}
self-introduction: {intro}
keywords: {keywords}
intents: {intents}"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--model", default="glm-5.3-flash")
    args = ap.parse_args()

    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT domain, name, osm_type, location, self_introduction, keywords, intents "
        "FROM docs WHERE osm_type IS NOT NULL AND name IS NOT NULL").fetchall()
    rng = random.Random(7)
    sample = rng.sample(rows, min(args.n, len(rows)))
    con.close()
    print(f"sampled {len(sample)} profiles")

    def one(r: sqlite3.Row) -> dict | None:
        style = STYLES[rng.randrange(len(STYLES))]
        prompt = PROMPT.format(style=style, name=r["name"], domain=r["domain"],
                               type=r["osm_type"] or "", location=r["location"] or "",
                               intro=(r["self_introduction"] or "")[:400],
                               keywords=(r["keywords"] or "")[:200],
                               intents=(r["intents"] or "")[:200])
        try:
            raw, _ = chat(args.model,
                          [{"role": "system", "content": "You are a helpful assistant."},
                           {"role": "user", "content": prompt}])
            q = raw.strip().strip('"').split("\n")[0].strip()
            if 3 <= len(q) <= 120:
                return {"question": q, "domain": r["domain"], "name": r["name"]}
        except Exception:
            return None
        return None

    OUT.mkdir(parents=True, exist_ok=True)
    out_path = OUT / "questions.jsonl"
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(one, sample))
    qs = [r for r in results if r]
    out_path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in qs))
    print(f"wrote {len(qs)} questions -> {out_path}")
    print(f"API usage: {usage_report()}")


if __name__ == "__main__":
    main()

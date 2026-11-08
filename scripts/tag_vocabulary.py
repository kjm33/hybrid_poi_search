#!/usr/bin/env python3
"""audience-tags Stage 1 (Tier 1): normalize repeating facet values → tag vocabulary.

Head facet values (seen >= MIN_COUNT times across kinds feature+intent) are batched
to glm-5.3-flash via z.ai. Each value maps to:
  - an existing canonical tag (snake_case),
  - "new:<tag>"  (audience/vibe attribute, but no existing tag fits — proposal),
  - null         (not an audience/vibe attribute: services, ownership, food facts...).

Resumable: one JSON cache file per batch in the effort dir; re-run skips done batches
(pick up failures with --retry-failed). After the run, aggregates everything into
  tier1/tag_map_head.json   {"kind|value": tag|null}
  tier1/tier1_report.md     QA: per-tag coverage, new-tag proposals w/ examples, null sample

Usage:
  .venv/bin/python scripts/tag_vocabulary.py [--min-count 5] [--batch 100] [--limit N]
                                             [--retry-failed] [--report-only]
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import time
from collections import Counter, defaultdict
from pathlib import Path

from zai_client import chat, usage_report

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "kb.db"
EFFORT = ROOT / "efforts" / "2026-11-08-audience-tags"
CACHE = EFFORT / "tier1_cache"
OUT = EFFORT / "tier1"

MODEL = "glm-5.3-flash"
MAX_TOKENS = 24576  # GLM reasoning models: content comes after CoT — leave headroom
CALL_TIMEOUT = 300  # generous read timeout; CoT on 100-value batches is slow

SEED_TAGS = [
    "family_friendly", "business_friendly", "work_friendly", "pet_friendly",
    "romantic", "groups_events", "late_night", "accessible",
]

PROMPT = """You are building the tag vocabulary for a "places" knowledge base mined from
business and organization websites (restaurants, schools, churches, hotels, gyms,
senior living, clinics, ...).

For each VALUE below, decide: is it an AUDIENCE or VIBE attribute — WHO the place
serves (families, couples, adults only, students, seniors, pets) or its SOCIAL
ATMOSPHERE (romantic, casual, upscale, lively) — and if so, which canonical tag.

Answer with ONE JSON array of objects, one per VALUE, like:
  {{"value": "<the exact VALUE text>", "tag": "tag_name"}}
where "tag" is:
  - "tag_name"       an EXISTING tag below that fits,
  - "new:tag_name"   an audience/vibe attribute but no existing tag fits,
  - null             anything else.

null — NOT audience/vibe: services (takeout, delivery, online ordering), amenities
(al fresco dining, outdoor seating, wifi, parking, art exhibitions, live music,
arcade games), ownership (family-owned, women-owned), food/quality facts (fresh
ingredients, vegetarian options), programs/curriculum (art classes, adult education
as a PROGRAM — but a venue being adults-only IS a vibe), named offerings,
location/hours facts, cuisine names.

NEW TAG RULES — the vocabulary must stay SMALL and GENERAL, a user should be able to
filter places by it (like "family friendly" or "date night"):
- One tag per concept: merge synonyms and specifics into the general tag
  (art exhibitions + art gallery are amenities anyway → null; 21+ only + adult
  atmosphere nightlife → new:adults_only).
- Never create a tag that just restates one value.
- When unsure between new tag and null → null.

EXISTING TAGS: {tags}

VALUES:
{values}"""


def fetch_head_values(min_count: int, limit: int | None) -> list[tuple[str, str, int]]:
    con = sqlite3.connect(DB)
    rows = con.execute(
        "SELECT kind, value, COUNT(*) c FROM facets WHERE kind IN ('feature','intent') "
        "GROUP BY kind, value HAVING c >= ? ORDER BY kind, value",
        (min_count,),
    ).fetchall()
    con.close()
    if limit:
        rows = rows[:limit]
    return [(k, v, c) for k, v, c in rows]


TAG_RE = re.compile(r"(new:)?[a-z0-9_]{2,40}")


def call_batch(items: list[tuple[str, str, int]]) -> list | None:
    """One LLM call for up to --batch values. Returns mapped list or None on failure.

    The model echoes each value, so alignment is by VALUE TEXT (robust to the model
    miscounting); items whose value the answer omits map to None (counted as miss)."""
    values_txt = "\n".join(f"{i + 1}. {v}" for i, (_, v, _) in enumerate(items))
    prompt = PROMPT.format(tags=", ".join(SEED_TAGS), values=values_txt)
    for attempt in range(2):
        content, _ = chat(
            MODEL,
            [{"role": "user", "content": prompt if attempt == 0 else prompt + "\n\nReturn ONLY the JSON array."}],
            max_tokens=MAX_TOKENS,
            timeout=CALL_TIMEOUT,
        )
        m = re.search(r"\[.*\]", content, re.S)  # strip fences/prose around the array
        if not m:
            continue
        try:
            arr = json.loads(m.group(0))
        except json.JSONDecodeError:
            continue
        if not isinstance(arr, list):
            continue
        d: dict[str, str | None] = {}
        ok_obj = True
        for o in arr:
            if not isinstance(o, dict) or "value" not in o or "tag" not in o:
                ok_obj = False
                break
            t = o["tag"]
            if t is not None and not (isinstance(t, str) and TAG_RE.fullmatch(t)):
                ok_obj = False
                break
            d[str(o["value"]).strip().lower()] = t
        if not ok_obj:
            continue
        mapped = [d.get(v.lower()) for (_, v, _) in items]
        found = sum(1 for x in mapped if x is not None) + sum(
            1 for (_, v, _) in items if v.lower() in d and d[v.lower()] is None)
        if found >= 0.9 * len(items):
            return mapped
    return None


def run(args: argparse.Namespace) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    rows = fetch_head_values(args.min_count, args.limit)
    batches = [rows[i:i + args.batch] for i in range(0, len(rows), args.batch)]
    print(f"head values: {len(rows)} ({args.min_count}+ occurrences) → {len(batches)} batches", flush=True)

    failed = 0
    t0 = time.time()
    lock_print = __import__("threading").Lock()
    from concurrent.futures import ThreadPoolExecutor

    def one(bi_items: tuple[int, list]) -> tuple[int, list | None]:
        bi, items = bi_items
        try:
            return bi, call_batch(items)
        except Exception as e:  # timeout / rate limit / network — batch retried later
            print(f"  batch {bi + 1} error: {e!r}", flush=True)
            return bi, None

    todo = []
    for bi, items in enumerate(batches):
        cf = CACHE / f"batch_{bi:03d}.json"
        if cf.exists() and not (args.retry_failed and json.loads(cf.read_text())["mapped"] is None):
            continue
        todo.append((bi, items))
    print(f"to call: {len(todo)} of {len(batches)} batches ({args.workers} workers)", flush=True)

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for bi, mapped in ex.map(one, todo):
            items = batches[bi]
            cf = CACHE / f"batch_{bi:03d}.json"
            cf.write_text(json.dumps({"batch": bi, "items": items, "mapped": mapped}, ensure_ascii=False))
            if mapped is None:
                failed += 1
            with lock_print:
                print(f"  batch {bi + 1}/{len(batches)}{' FAILED' if mapped is None else ''} "
                      f"({time.time() - t0:.0f}s) — {usage_report()}", flush=True)
    if failed:
        print(f"{failed} batches failed — re-run with --retry-failed", flush=True)
    report()
    print(f"done in {time.time() - t0:.0f}s — {usage_report()}", flush=True)


def report() -> None:
    """Aggregate cache files → tag_map_head.json + tier1_report.md."""
    mapping: dict[str, str | None] = {}
    row_cov: Counter[str] = Counter()          # tag -> facet rows covered
    proposals: dict[str, list] = defaultdict(list)  # new:tag -> [(value, count)]
    nulls: list[tuple[str, int]] = []
    pending = 0
    for cf in sorted(CACHE.glob("batch_*.json")):
        d = json.loads(cf.read_text())
        if d["mapped"] is None:
            pending += len(d["items"])
            continue
        for (kind, value, count), m in zip(d["items"], d["mapped"]):
            mapping[f"{kind}|{value}"] = m
            if m is None:
                nulls.append((value, count))
            elif m.startswith("new:"):
                proposals[m[4:]].append((value, count))
            else:
                row_cov[m] += count

    total_rows = sum(row_cov.values()) + sum(c for _, c in nulls) + sum(
        c for vs in proposals.values() for _, c in vs)
    lines = [
        "# Tier-1 report — head facet values → audience tags",
        "",
        f"- mapped values: {len(mapping)} ({pending} in failed batches, re-run pending)",
        f"- facet rows covered: {total_rows:,}",
        "",
        "## Existing-tag coverage (facet rows)",
        "",
        "| tag | values | facet rows |", "|---|---|---|",
    ]
    for tag, cov in sorted(row_cov.items(), key=lambda x: -x[1]):
        n_vals = sum(1 for v in mapping.values() if v == tag)
        lines.append(f"| {tag} | {n_vals} | {cov:,} |")
    lines += ["", f"## New-tag proposals ({len(proposals)}) — USER REVIEW", "",
              "Approve tags with consistent examples; reject noise.", ""]
    for tag, vs in sorted(proposals.items(), key=lambda x: -sum(c for _, c in x[1])):
        top = sorted(vs, key=lambda x: -x[1])[:5]
        ex = "; ".join(f"{v} ({c})" for v, c in top)
        lines.append(f"- **{tag}** ({len(vs)} values, {sum(c for _, c in vs)} rows): {ex}")
    lines += ["", f"## Nulls (sample of {len(nulls)})", ""]
    for v, c in sorted(nulls, key=lambda x: -x[1])[:30]:
        lines.append(f"- {v} ({c})")
    OUT.mkdir(exist_ok=True)
    (OUT / "tag_map_head.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=1))
    (OUT / "tier1_report.md").write_text("\n".join(lines) + "\n")
    print(f"report → {OUT / 'tier1_report.md'}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-count", type=int, default=5)
    ap.add_argument("--batch", type=int, default=100)
    ap.add_argument("--limit", type=int, default=None, help="only first N values (smoke test)")
    ap.add_argument("--retry-failed", action="store_true")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--report-only", action="store_true")
    args = ap.parse_args()
    if args.report_only:
        report()
    else:
        run(args)

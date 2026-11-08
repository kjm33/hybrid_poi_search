#!/usr/bin/env python3
"""audience-tags Stage 4: write kind='audience_fit' facets into kb.db.

Sources (union, provenance recorded in tier4/provenance.json):
  1. stage3  — tier3/verified.json verdict==true pairs (LLM read the profile text,
               evidence quote attached)
  2. facets  — profile's own feature/intent facet values mapped through the Tier-1/Tier-2
               dictionaries (value-level LLM judgment), filtered to approved tags

Usage: .venv/bin/python scripts/tag_write_facets.py [--dry]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "kb.db"
EFFORT = ROOT / "efforts" / "2026-11-08-audience-tags"
T4 = EFFORT / "tier4"


def load_dicts() -> dict[str, str]:
    approved = set(json.loads((EFFORT / "tier1" / "approved_tags.json").read_text())["tags"])
    d: dict[str, str] = {}
    for name in ("tier1/tag_map_head.json", "tier2/tag_map_tail.json"):
        for key, entry in json.loads((EFFORT / name).read_text()).items():
            tag = entry["tag"] if isinstance(entry, dict) else entry
            tag = tag if tag in approved else None  # drops new:* proposals
            if tag is None:
                continue
            value = (key.split("|", 1)[1] if "|" in key else key).lower()
            prev = d.get(value)
            if prev and prev != tag:  # head dict wins on conflict
                continue
            if prev is None:
                d[value] = tag
    return d


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    T4.mkdir(parents=True, exist_ok=True)

    # 1. stage-3 verified pairs
    verified = json.loads((EFFORT / "tier3" / "verified.json").read_text())
    pairs: dict[tuple[str, str], str] = {}  # (domain, tag) -> source
    for tag, arr in verified.items():
        for o in arr:
            if o.get("verdict") is True and o.get("domain"):
                pairs[(o["domain"], tag)] = "stage3"

    # 2. facet-dictionary hits on the profile's own values
    d = load_dicts()
    con = sqlite3.connect(DB)
    n_facet = 0
    for domain, value in con.execute(
            "SELECT domain, lower(value) FROM facets WHERE kind IN ('feature','intent')"):
        tag = d.get(value)
        if tag and pairs.get((domain, tag)) != "stage3":
            key = (domain, tag)
            if key not in pairs:
                pairs[key] = "facets"
                n_facet += 1
    print(f"stage3 pairs: {sum(1 for v in pairs.values() if v == 'stage3')} | "
          f"facet-dict additions: {n_facet} | total: {len(pairs)}")

    by_tag: Counter = Counter(t for _, t in pairs)
    by_dom: dict[str, set] = defaultdict(set)
    for (domain, tag), src in pairs.items():
        by_dom[domain][tag].add(src) if False else by_dom[domain].add(tag)
    prov = {d: {t: "+".join(sorted(src for (dd, tt), src in pairs.items()
                                     if dd == d and tt == t)) for t in tags}
            for d, tags in by_dom.items()}

    lines = ["# Stage-4 — audience_fit facets written to kb.db", "",
             f"- stage3-verified pairs: {sum(1 for v in pairs.values() if v == 'stage3')}",
             f"- facet-dictionary additions: {n_facet}",
             f"- total (domain, tag) rows: {len(pairs)}",
             f"- profiles with ≥1 tag: {len(by_dom)} of 13,521", "",
             "| tag | profiles |", "|---|---|"]
    for t, c in by_tag.most_common():
        lines.append(f"| {t} | {c} |")

    if args.dry:
        print("\n".join(lines))
        return

    con.execute("DELETE FROM facets WHERE kind='audience_fit'")
    con.executemany("INSERT OR IGNORE INTO facets VALUES (?,?,?)",
                    [(d, "audience_fit", t) for (d, t) in pairs])
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM facets WHERE kind='audience_fit'").fetchone()[0]
    con.close()
    (T4 / "provenance.json").write_text(json.dumps(prov, ensure_ascii=False))
    (T4 / "facets_report.md").write_text("\n".join(lines) + "\n")
    print(f"kb.db facets kind='audience_fit': {n} rows\nreport → {T4 / 'facets_report.md'}")


if __name__ == "__main__":
    main()

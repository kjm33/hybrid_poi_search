#!/usr/bin/env python3
"""Stage 1 A/B test: 50 stratified pages through two (or more) models.

Writes efforts/2026-11-07-amenity-knowledge-base/ab/<model>.jsonl and ab_report.md
so both outputs can be compared side by side before the full ~13.5k-page run.

Usage:
    python3 scripts/extract_ab.py                              # glm-5.3 vs glm-5.3-flash (z.ai)
    LLM_BASE=vllm python3 scripts/extract_ab.py --models qwen3-30b-a3b-fp8
        # local vLLM model; if glm-5.3-flash.jsonl exists it is reused for comparison
"""
from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_common import SYSTEM_PROMPT, build_user_message, parse_profile  # noqa: E402
from zai_client import chat, usage_report  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "enrichment.db"
OUT = ROOT / "efforts" / "2026-11-07-amenity-knowledge-base" / "ab"
MODELS = ["glm-5.3", "glm-5.3-flash"]
SAMPLE = {  # stratified, fixed seed -> reproducible
    "ok": 35,
    "review|short": 6,
    "review|non_english": 4,
    "review|spam_present": 2,
    "review|mentions_construction": 3,
}
WORKERS = 4


def pick_sample() -> list[dict]:
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rng = random.Random(42)
    picked = []
    for spec, n in SAMPLE.items():
        verdict, _, reason = spec.partition("|")
        if reason:
            q = "SELECT * FROM page_quality WHERE verdict=? AND reasons LIKE ?"
            args = (verdict, f'%"{reason}"%')
        else:
            q, args = "SELECT * FROM page_quality WHERE verdict=?", (verdict,)
        rows = con.execute(q, args).fetchall()
        picked.extend(dict(r) for r in rng.sample(rows, min(n, len(rows))))
    con.close()
    return picked


def run_one(model: str, page: dict) -> dict:
    user_msg = build_user_message(page["domain"], page["title"] or "", page["fm_description"] or "", page["body"] or "")
    t0 = time.time()
    try:
        raw, usage = chat(model, [{"role": "system", "content": SYSTEM_PROMPT},
                                  {"role": "user", "content": user_msg}])
        profile, err = parse_profile(raw)
        return {
            "domain": page["domain"], "bucket": page["verdict"], "clean_chars": page["clean_chars"],
            "model": model, "seconds": round(time.time() - t0, 1),
            "prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": usage.get("completion_tokens"),
            "parse_error": err or None, "profile": profile,
        }
    except Exception as e:
        return {"domain": page["domain"], "bucket": page["verdict"], "clean_chars": page["clean_chars"],
                "model": model, "seconds": round(time.time() - t0, 1), "parse_error": f"api_error:{e!s:.150}",
                "profile": None}


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    valid = [r for r in rows if r["profile"] and not r["parse_error"]]
    useful = [r for r in valid if r["profile"].get("is_useful")]
    fill = {}
    for k in ("self_introduction", "intents", "keywords", "detailed_profile", "opening_hours"):
        fill[k] = sum(1 for r in valid if r["profile"].get(k)) / max(len(valid), 1)
    intros = [len(r["profile"].get("self_introduction") or "") for r in valid]
    return {
        "n": n,
        "valid_json_pct": len(valid) / n,
        "is_useful_pct": len(useful) / max(len(valid), 1),
        "avg_seconds": sum(r["seconds"] for r in rows) / n,
        "avg_prompt_tokens": sum(r.get("prompt_tokens") or 0 for r in rows) / n,
        "avg_completion_tokens": sum(r.get("completion_tokens") or 0 for r in rows) / n,
        "avg_intro_chars": (sum(intros) / len(intros)) if intros else 0,
        "field_fill": fill,
        "parse_errors": sorted({r["parse_error"] for r in rows if r["parse_error"]}),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default=",".join(MODELS), help="comma-separated model ids")
    ap.add_argument("--force", action="store_true", help="re-run models whose jsonl already exists")
    args = ap.parse_args()
    models = [m.strip() for m in args.models.split(",") if m.strip()]

    OUT.mkdir(parents=True, exist_ok=True)
    sample = pick_sample()
    print(f"sample: {len(sample)} pages", flush=True)

    for model in models:
        if (OUT / f"{model}.jsonl").exists() and not args.force:
            print(f"[{model}] jsonl exists, skipping calls (use --force to redo)", flush=True)
            continue
        rows = []
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futs = {pool.submit(run_one, model, p): p for p in sample}
            for i, fut in enumerate(as_completed(futs), 1):
                rows.append(fut.result())
                print(f"[{model}] {i}/{len(sample)} done ({time.time()-t0:.0f}s)", flush=True)
        rows.sort(key=lambda r: r["domain"])
        out = OUT / f"{model}.jsonl"
        out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows))
        print(f"wrote {out} ({len(rows)} rows)", flush=True)

    # ---- comparison report ----
    all_rows = {m: [json.loads(l) for l in (OUT / f"{m}.jsonl").read_text().splitlines()] for m in models}
    report = [f"# A/B report: {' vs '.join(models)} (50 stratified pages, seed 42)", ""]
    for m in models:
        s = summarize(all_rows[m])
        report += [
            f"## {m}",
            f"- valid JSON: **{s['valid_json_pct']:.0%}**  | is_useful among valid: {s['is_useful_pct']:.0%}",
            f"- avg latency: {s['avg_seconds']:.1f}s  | avg tokens in/out: {s['avg_prompt_tokens']:.0f}/"
            f"{s['avg_completion_tokens']:.0f}",
            f"- avg self_introduction length: {s['avg_intro_chars']:.0f} chars",
            f"- field fill: " + ", ".join(f"{k}={v:.0%}" for k, v in s["field_fill"].items()),
            f"- parse errors: {s['parse_errors'] or 'none'}",
            "",
        ]
    # side-by-side samples: 3 useful + 2 edge (review buckets)
    edge = [r["domain"] for r in all_rows[models[0]] if r["bucket"] == "review"][:2]
    useful3 = [r["domain"] for r in all_rows[models[0]] if r["profile"] and r["profile"].get("is_useful")][:3]
    report += ["## Side-by-side samples", ""]
    for d in useful3 + edge:
        report.append(f"### {d}")
        for m in models:
            row = next(r for r in all_rows[m] if r["domain"] == d)
            p = row.get("profile") or {}
            report += [
                f"**{m}** (is_useful={p.get('is_useful')}, page_type={p.get('page_type')})",
                "",
                f"- intro: {p.get('self_introduction')}",
                f"- intents: {p.get('intents')}",
                f"- keywords: {p.get('keywords')}",
                "",
            ]
    (OUT / "ab_report.md").write_text("\n".join(report))
    print(f"\nwrote {OUT / 'ab_report.md'}")
    print(f"total API usage: {usage_report()}")


if __name__ == "__main__":
    main()

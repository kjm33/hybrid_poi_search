#!/usr/bin/env python3
"""Stage 2: full LLM extraction over all ok+review pages → data/kb.db (profiles).

Resumable: every model response is cached in data/extract_cache/<domain>.json.
Re-running skips domains with a valid profile; failed/parse-error domains are
retried up to MAX_ATTEMPTS. kb.db is rebuilt from the cache, so the cache is
the source of truth.

Usage:
    python3 scripts/extract_all.py --model glm-5.3-flash [--workers 12] [--limit 50]
    python3 scripts/extract_all.py --rebuild        # rebuild kb.db from cache, no API calls
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_common import SYSTEM_PROMPT, build_user_message, parse_profile  # noqa: E402
from zai_client import RateLimited, chat, usage_report  # noqa: E402


class RatePacer:
    """Adaptive global request pacing shared by all worker threads.

    - Enforces a minimum interval between call STARTS (starts conservative).
    - On a rate-limit (429): pauses every worker, then widens the interval.
    - After a streak of clean calls: slowly narrows the interval (floor min_int).
    Auto-tunes to whatever the plan's request limit actually is.
    """

    def __init__(self, interval: float = 5.0, min_int: float = 2.5, max_int: float = 30.0):
        self.interval = interval
        self.min_int = min_int
        self.max_int = max_int
        self.pause_until = 0.0
        self.streak = 0
        self._lock = threading.Lock()
        self._next_start = 0.0

    def wait(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                if now < self.pause_until:
                    time.sleep(min(self.pause_until - now, 5.0))
                    continue
                start_at = max(now, self._next_start)
                self._next_start = start_at + self.interval
            delay = start_at - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            return

    def penalize(self, pause: float = 90.0) -> None:
        with self._lock:
            self.pause_until = max(self.pause_until, time.monotonic() + pause)
            self.interval = min(self.interval * 1.5, self.max_int)
            self.streak = 0

    def reward(self) -> None:
        with self._lock:
            self.streak += 1
            if self.streak >= 50 and self.interval > self.min_int:
                self.interval = max(self.interval * 0.9, self.min_int)
                self.streak = 0


PACER = RatePacer()

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "enrichment.db"
DST = ROOT / "data" / "kb.db"
CACHE = ROOT / "data" / "extract_cache"
MAX_ATTEMPTS = 3

SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
    domain TEXT PRIMARY KEY,
    name TEXT, type TEXT, cuisine_or_specialty TEXT, location TEXT,
    short_description TEXT, detailed_profile TEXT, self_introduction TEXT,
    intents TEXT, features TEXT, services TEXT, audience TEXT,
    price_level TEXT, opening_hours TEXT, keywords TEXT,
    page_type TEXT, is_useful INTEGER, confidence REAL,
    source_verdict TEXT, source_lang TEXT,
    model TEXT, extracted_at TEXT, parse_error TEXT
);
CREATE INDEX IF NOT EXISTS idx_prof_useful ON profiles(is_useful);
CREATE INDEX IF NOT EXISTS idx_prof_page_type ON profiles(page_type);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""


def cache_path(domain: str) -> Path:
    safe = domain.replace("/", "_")
    return CACHE / f"{safe}.json"


def load_cache(domain: str) -> dict | None:
    p = cache_path(domain)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError:
            return None
    return None


def run_one(model: str, page: dict) -> dict:
    """Call the LLM for one page and write its cache file. Returns the cache record."""
    domain = page["domain"]
    cached = load_cache(domain)
    if cached and (cached.get("profile") is not None or cached.get("attempts", 0) >= MAX_ATTEMPTS):
        cached["skipped"] = True
        return cached

    attempts = (cached or {}).get("attempts", 0)
    rec = {"domain": domain, "model": model, "attempts": attempts,
           "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
    user_msg = build_user_message(domain, page["title"] or "",
                                  page["fm_description"] or "", page["body"] or "")
    t0 = time.time()
    try:
        PACER.wait()
        raw, usage = chat(model, [{"role": "system", "content": SYSTEM_PROMPT},
                                  {"role": "user", "content": user_msg}])
        profile, err = parse_profile(raw)
        rec["attempts"] = attempts + 1  # the input had its chance
        PACER.reward()
        rec.update(seconds=round(time.time() - t0, 1),
                   prompt_tokens=usage.get("prompt_tokens"),
                   completion_tokens=usage.get("completion_tokens"),
                   parse_error=err or None, profile=profile)
    except RateLimited as e:
        # rate limit is not this domain's fault: no attempt burned, retry next run
        PACER.penalize()
        rec.update(seconds=round(time.time() - t0, 1),
                   parse_error=f"rate_limited:{e!s:.80}", profile=None)
    except Exception as e:
        rec["attempts"] = attempts + 1
        rec.update(seconds=round(time.time() - t0, 1), parse_error=f"api_error:{e!s:.150}",
                   profile=None)
    cache_path(domain).write_text(json.dumps(rec, ensure_ascii=False))
    return rec


def fetch_pages(limit: int | None) -> list[dict]:
    con = sqlite3.connect(f"file:{SRC}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    q = ("SELECT domain, verdict, lang, title, fm_description, body FROM page_quality "
         "WHERE verdict IN ('ok','review') ORDER BY clean_chars DESC")
    rows = [dict(r) for r in con.execute(q).fetchall()]
    con.close()
    if limit:
        rows = rows[:limit]
    return rows


def rebuild_kb(model_hint: str | None) -> None:
    """Rebuild kb.db profiles table from the response cache (no API calls)."""
    DST.parent.mkdir(parents=True, exist_ok=True)
    dst = sqlite3.connect(DST)
    dst.executescript(SCHEMA)
    dst.execute("DELETE FROM profiles")
    n, useful = 0, 0
    for f in sorted(CACHE.glob("*.json")):
        rec = json.loads(f.read_text())
        p = rec.get("profile")
        if not p:
            continue
        dst.execute(
            "INSERT OR REPLACE INTO profiles VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (rec["domain"], p.get("name"), p.get("type"), p.get("cuisine_or_specialty"),
             p.get("location"), p.get("short_description"), p.get("detailed_profile"),
             p.get("self_introduction"),
             json.dumps(p.get("intents") or [], ensure_ascii=False),
             json.dumps(p.get("features") or [], ensure_ascii=False),
             json.dumps(p.get("services") or [], ensure_ascii=False),
             p.get("audience"), p.get("price_level"), p.get("opening_hours"),
             json.dumps(p.get("keywords") or [], ensure_ascii=False),
             p.get("page_type"), int(bool(p.get("is_useful"))), p.get("confidence"),
             rec.get("source_verdict"), rec.get("source_lang"),
             rec.get("model") or model_hint or "", rec.get("ts"), rec.get("parse_error")),
        )
        n += 1
        useful += int(bool(p.get("is_useful")))
    dst.execute("INSERT OR REPLACE INTO meta VALUES ('kb_built_at', ?)",
                (time.strftime("%Y-%m-%d %H:%M:%S"),))
    dst.commit()
    dst.close()
    print(f"kb.db rebuilt: {n} profiles ({useful} is_useful)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="glm-5.3-flash")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--limit", type=int, default=None, help="only first N pages (smoke test)")
    ap.add_argument("--interval", type=float, default=5.0,
                    help="seconds between call starts (auto-adapts on 429)")
    ap.add_argument("--rebuild", action="store_true", help="rebuild kb.db from cache only")
    args = ap.parse_args()

    PACER.interval = args.interval

    if args.rebuild:
        rebuild_kb(args.model)
        return

    pages = fetch_pages(args.limit)
    CACHE.mkdir(parents=True, exist_ok=True)
    already = sum(1 for p in pages if (c := load_cache(p["domain"]))
                  and (c.get("profile") is not None or c.get("attempts", 0) >= MAX_ATTEMPTS))
    todo = len(pages) - already
    print(f"pages: {len(pages)} | cached/done: {already} | to call: {todo} | model={args.model} "
          f"| workers={args.workers}", flush=True)

    stats = {"ok": 0, "parse_error": 0, "api_error": 0, "rate_limited": 0, "useful": 0}
    t0 = time.time()
    done_count = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(run_one, args.model, p): p for p in pages}
        for fut in as_completed(futs):
            rec = fut.result()
            done_count += 1
            if rec.get("skipped"):
                continue
            err = rec.get("parse_error") or ""
            if err.startswith("rate_limited"):
                stats["rate_limited"] += 1
            elif err.startswith("api_error"):
                stats["api_error"] += 1
            elif err:
                stats["parse_error"] += 1
            elif rec.get("profile"):
                stats["ok"] += 1
                stats["useful"] += int(bool(rec["profile"].get("is_useful")))
            if done_count % 25 == 0:
                el = time.time() - t0
                print(f"  {done_count}/{todo} called ({el:.0f}s, {done_count/el:.2f}/s) "
                      f"interval={PACER.interval:.1f}s {stats}", flush=True)

    print(f"\ndone: {stats} in {time.time()-t0:.0f}s")
    print(f"API usage: {usage_report()}")
    # stamp source verdict/lang into cache for provenance, then rebuild kb
    con = sqlite3.connect(f"file:{SRC}?mode=ro", uri=True)
    verdicts = {r[0]: (r[1], r[2]) for r in con.execute("SELECT domain, verdict, lang FROM page_quality")}
    con.close()
    for f in CACHE.glob("*.json"):
        rec = json.loads(f.read_text())
        v, lang = verdicts.get(rec["domain"], ("", ""))
        if rec.get("source_verdict") != v:
            rec["source_verdict"], rec["source_lang"] = v, lang
            f.write_text(json.dumps(rec, ensure_ascii=False))
    rebuild_kb(args.model)


if __name__ == "__main__":
    main()

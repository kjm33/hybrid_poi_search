#!/usr/bin/env python3
"""Stage 0 prefilter: classify extracted amenity pages without any LLM calls.

Reads  data/extracted_content.db  (table extracted_content)
Writes data/enrichment.db        (table page_quality, one row per domain)

Verdicts:
  no_content  extraction failed / empty text            -> never sent to LLM
  quarantine  obvious garbage (parked domain, redirect,
              error page, under construction, shell)    -> never sent to LLM
  review      borderline (short, possible error, ...)   -> sent to LLM, flagged
  ok          useful page                                -> sent to LLM

Non-English pages stay ok/review: the LLM prompt translates to English.
See efforts/2026-11-07-amenity-hybrid-search/tasks.md
"""
from __future__ import annotations

import re
import sqlite3
import sys
import time
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
SRC = DATA / "extracted_content.db"
DST = DATA / "enrichment.db"

# --- garbage patterns (deliberately narrow: "parking" alone matches real parking lots) ---
PARKING_RE = re.compile(
    r"(is for sale|hugedomains|buy this domain|domain parking|sedoparking|"
    r"sedo\.com|afternic\.com|domain has expired|this domain is available|"
    r"domain_name_for_sale|register this domain)",
    re.IGNORECASE,
)
CONSTRUCTION_RE = re.compile(
    r"(under construction|coming soon|공사중|currently renovat|site in maintenance|"
    r"website under maintenance|new website coming)",
    re.IGNORECASE,
)
# Injected SEO/link spam (hacked sites: gambling/betting sections, mostly
# Indonesian + multilingual casino link-building). Split by evidence strength:
# Indonesian online-gambling terms never appear on legit CA business pages.
SPAM_STRONG_RE = re.compile(
    r"(gacor|togel|judi online|prediksi skor|situsslot|slot gacor|rtp slot|daftar slot|"
    r"bandar togel|hokiemas|situs judi|agen slot|mesin slot|judi bola|sbobet|idnpoker)",
    re.IGNORECASE,
)
SPAM_MEDIUM_RE = re.compile(
    r"(parlay|sportsbook|betonline|bovada|mybookie|crypto sportsbook|casino ?online|"
    r"betting sites|online casino|slot\d{2,}|deposit bonus|accumulator[s]? boost)",
    re.IGNORECASE,
)
REDIRECT_RE = re.compile(r"^\s*redirect\s*$", re.IGNORECASE)
ERROR_TITLE_RE = re.compile(r"^(error|404|not found|page not found|forbidden|oops)$", re.IGNORECASE)
ERROR_BODY_RE = re.compile(
    r"(404 error|page not found|something went wrong|oops!?\s*\.{0,3}\s*error|"
    r"error 40[03]|internal server error)",
    re.IGNORECASE,
)

# English function words for a cheap language heuristic
EN_WORDS = {
    "the", "and", "of", "to", "in", "is", "for", "with", "you", "your", "our", "we",
    "a", "an", "at", "on", "are", "be", "this", "that", "it", "from", "or", "by",
    "as", "has", "have", "was", "were", "will", "can", "us", "their", "its", "all",
    "about", "our", "new", "best", "menu", "order", "call", "open", "hours", "location",
}

# lines that are pure markdown/table decoration
NOISE_LINE_RE = re.compile(r"^[\s|:\-–—=*_#>\[\](){}.,;!?\\/‹›«»’‘“”\"']*$")
URL_RE = re.compile(r"https?://\S+|\(https?://[^)]*\)")


def split_front_matter(text: str) -> tuple[dict, str]:
    """Split trafilatura front-matter (---\\nkey: val\\n---) from body."""
    if text.startswith("---"):
        lines = text.split("\n")
        for i in range(1, min(len(lines), 40)):
            if lines[i].rstrip() in ("---", "--- ") or lines[i].rstrip().startswith("--- ") and lines[i].strip() == "---":
                fm = {}
                for line in lines[1:i]:
                    if ":" in line:
                        k, v = line.split(":", 1)
                        fm[k.strip().lower()] = v.strip()
                return fm, "\n".join(lines[i + 1 :])
    return {}, text


def clean_body(body: str) -> str:
    """Drop decoration lines and bare URLs; keep real content lines."""
    kept = []
    for line in body.split("\n"):
        if NOISE_LINE_RE.match(line):
            continue
        kept.append(URL_RE.sub(" ", line))
    text = "\n".join(kept)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def english_ratio(body: str) -> tuple[float, int]:
    """(share of English function words, word count) over first ~1500 chars."""
    sample = body[:1500].lower()
    words = re.findall(r"[a-zà-ÿ']+", sample)
    if not words:
        return 0.0, 0
    hits = sum(1 for w in words if w in EN_WORDS)
    return hits / len(words), len(words)


def classify(domain: str, text: str | None, error: str | None) -> dict:
    reasons: list[str] = []

    if error or not text:
        return {"verdict": "no_content", "reasons": ["extraction_failed"], "lang": "", "fm": {}, "clean": ""}

    fm, raw_body = split_front_matter(text)
    body = clean_body(raw_body)
    clean_chars = len(body)
    title = (fm.get("title") or "")[:300]
    fm_description = fm.get("description") or ""

    # 1. parked / for-sale domain — unambiguous garbage
    haystack = f"{title} {fm_description} {body[:3000]}"
    if PARKING_RE.search(haystack):
        return {"verdict": "quarantine", "reasons": ["domain_parking"], "lang": "en",
                "fm": fm, "clean": body, "title": title, "fm_description": fm_description,
                "clean_chars": clean_chars}

    # 2. pure redirect stub
    if REDIRECT_RE.match(body.strip()) and clean_chars < 60:
        return {"verdict": "quarantine", "reasons": ["redirect_stub"], "lang": "",
                "fm": fm, "clean": body, "title": title, "fm_description": fm_description,
                "clean_chars": clean_chars}

    # 3. injected gambling/betting spam (hacked sites)
    strong_spam = len(SPAM_STRONG_RE.findall(body))
    medium_spam = len(SPAM_MEDIUM_RE.findall(body))
    spam_score = strong_spam * 2 + medium_spam
    spam_at_top = bool(
        (strong_spam and SPAM_STRONG_RE.search(body[:300]))
        or (medium_spam >= 2 and SPAM_MEDIUM_RE.search(body[:300]))
    )
    if spam_score >= 5 or spam_at_top:
        return {"verdict": "quarantine", "reasons": ["spam_dominant"], "lang": "",
                "fm": fm, "clean": body, "title": title, "fm_description": fm_description,
                "clean_chars": clean_chars}
    if spam_score >= 1:
        reasons.append("spam_present")

    # 4. under construction / coming soon — quarantine if nothing else to say
    if CONSTRUCTION_RE.search(haystack):
        if clean_chars < 500:
            return {"verdict": "quarantine", "reasons": ["under_construction"], "lang": "",
                    "fm": fm, "clean": body, "title": title, "fm_description": fm_description,
                    "clean_chars": clean_chars}
        reasons.append("mentions_construction")

    # 5. error page — quarantine only if it has no real content
    title_is_error = bool(title) and bool(ERROR_TITLE_RE.match(title.strip()))
    body_is_error = bool(ERROR_BODY_RE.search(body[:500]))
    if (title_is_error or body_is_error) and clean_chars < 300:
        return {"verdict": "quarantine", "reasons": ["error_page"], "lang": "",
                "fm": fm, "clean": body, "title": title, "fm_description": fm_description,
                "clean_chars": clean_chars}
    if title_is_error or body_is_error:
        reasons.append("possible_error_page")

    # 5. language heuristic (real foreign-language businesses stay in the LLM path)
    ratio, n_words = english_ratio(body)
    lang = "en" if ratio >= 0.03 or n_words < 50 else "other"
    if lang == "other":
        reasons.append("non_english")

    # 6. too short after cleaning
    if clean_chars < 200:
        return {"verdict": "quarantine", "reasons": reasons + ["too_short"], "lang": lang,
                "fm": fm, "clean": body, "title": title, "fm_description": fm_description,
                "clean_chars": clean_chars}
    if clean_chars < 500:
        reasons.append("short")

    verdict = "ok" if not reasons else "review"
    return {"verdict": verdict, "reasons": reasons or ["clean"], "lang": lang,
            "fm": fm, "clean": body, "title": title, "fm_description": fm_description,
            "clean_chars": clean_chars}


def main() -> None:
    if not SRC.exists():
        sys.exit(f"missing {SRC}")
    t0 = time.time()
    src = sqlite3.connect(f"file:{SRC}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row

    DST.parent.mkdir(parents=True, exist_ok=True)
    dst = sqlite3.connect(DST)
    dst.row_factory = sqlite3.Row
    dst.executescript(
        """
        DROP TABLE IF EXISTS page_quality;
        CREATE TABLE page_quality (
            domain TEXT PRIMARY KEY,
            verdict TEXT NOT NULL,          -- ok | review | quarantine | no_content
            reasons TEXT NOT NULL,          -- json array
            lang TEXT,
            clean_chars INTEGER,
            title TEXT,
            fm_description TEXT,
            fm_url TEXT,
            fm_sitename TEXT,
            body TEXT                       -- cleaned, front-matter stripped (LLM input)
        );
        CREATE INDEX idx_pq_verdict ON page_quality(verdict);
        CREATE INDEX idx_pq_clean_chars ON page_quality(clean_chars);
        CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
        """
    )

    rows = src.execute(
        "SELECT domain, url, text, title, description, error FROM extracted_content"
    ).fetchall()
    print(f"source rows: {len(rows)}")

    stats: dict[str, int] = {}
    reason_stats: dict[str, int] = {}
    insert = (
        "INSERT OR REPLACE INTO page_quality (domain, verdict, reasons, lang, clean_chars, "
        "title, fm_description, fm_url, fm_sitename, body) VALUES (?,?,?,?,?,?,?,?,?,?)"
    )
    payload = []
    for r in rows:
        d = classify(r["domain"], r["text"], r["error"])
        v = d["verdict"]
        stats[v] = stats.get(v, 0) + 1
        for reason in d["reasons"]:
            reason_stats[reason] = reason_stats.get(reason, 0) + 1
        fm = d.get("fm", {})
        payload.append(
            (
                r["domain"], v,
                __import__("json").dumps(d["reasons"]),
                d.get("lang", ""),
                d.get("clean_chars", 0),
                d.get("title") or r["title"] or "",
                d.get("fm_description", "") or r["description"] or "",
                fm.get("url") or r["url"] or "",
                fm.get("sitename", ""),
                d.get("clean", "")[:30000],
            )
        )
    dst.executemany(insert, payload)
    dst.execute(
        "INSERT OR REPLACE INTO meta VALUES ('prefilter_run_at', ?)", (time.strftime("%Y-%m-%d %H:%M:%S"),)
    )
    dst.commit()

    print(f"\nverdicts ({len(rows)} rows, {time.time()-t0:.1f}s):")
    for v in ("ok", "review", "quarantine", "no_content"):
        n = stats.get(v, 0)
        print(f"  {v:<11} {n:>6}  ({n/len(rows):5.1%})")
    print("\nreasons:")
    for reason, n in sorted(reason_stats.items(), key=lambda kv: -kv[1]):
        print(f"  {reason:<28} {n:>6}")

    print("\nsample quarantined domains per reason:")
    for reason in sorted(reason_stats):
        if reason in ("extraction_failed", "clean"):
            continue
        doms = dst.execute(
            "SELECT domain FROM page_quality WHERE verdict='quarantine' AND reasons LIKE ? LIMIT 3",
            (f'%"{reason}"%',),
        ).fetchall()
        if doms:
            print(f"  {reason:<28} {', '.join(x['domain'] for x in doms)}")
    dst.close()
    src.close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""audience-tags Stage 3: assign tags to profiles (shortlist → LLM verify).

Shortlist: cosine between each tag's definition embedding (bge-m3) and the existing
kb.db profile embeddings (13,199) → top --top candidates per tag (min --min-sim).
Verify:   glm-5.3-flash reads each candidate's text and answers verdict + EVIDENCE
          QUOTE (verbatim sentence) per (tag, domain). Resumable per tag-batch.

Outputs (effort dir tier3/):
  verify_cache/tag_<t>_batch_<i>.json   raw LLM answers
  verified.json     {tag: [{"domain", "verdict", "evidence"}, ...]}
  qa_report.md      per-tag counts, evidence spot-check samples, gold recall

Usage:
  .venv/bin/python scripts/tag_profiles.py [--top 300] [--min-sim 0.35] [--per-call 12]
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sqlite3
import time
from pathlib import Path

import numpy as np

from zai_client import chat, usage_report

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "kb.db"
EFFORT = ROOT / "efforts" / "2026-11-08-audience-tags"
T3 = EFFORT / "tier3"
MODEL = os.environ.get("LLM_MODEL", "glm-5.3-flash")

PROMPT = """You are verifying audience/vibe tags for a "places" knowledge base.

TAG: {tag} — {definition}

For each PLACE below, decide whether TAG genuinely applies: does the text say the
place serves, welcomes, or hosts this audience — or clearly has this vibe?

PLACES:
{places}

Answer with ONE JSON array of objects, one per place:
  {{"domain": "<the exact domain>", "verdict": true|false|"unsure", "evidence": "<sentence>"}}
Rules:
- evidence MUST be copied VERBATIM from the place text and must support true;
  empty string "" for false.
- "unsure" only when the text hints at it without saying it (evidence = closest sentence).
- Do not infer from silence: if nothing in the text supports the tag, verdict false."""


def load_profiles() -> dict[str, str]:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT domain, self_introduction, audience, detailed_profile FROM profiles WHERE is_useful=1"
    ).fetchall()
    con.close()
    out = {}
    for r in rows:
        text = " | ".join(x for x in (r["self_introduction"], r["audience"], r["detailed_profile"]) if x)
        out[r["domain"]] = text[:6000]
    return out


def load_profile_vecs() -> tuple[list[str], np.ndarray]:
    con = sqlite3.connect(DB)
    vecs, domains = [], []
    for domain, blob in con.execute("SELECT domain, vec FROM embeddings WHERE model='bge-m3'"):
        domains.append(domain)
        vecs.append(np.frombuffer(blob, dtype=np.float32))
    con.close()
    V = np.stack(vecs)
    V /= np.linalg.norm(V, axis=1, keepdims=True) + 1e-12
    return domains, V


def shortlist(domains: list[str], V: np.ndarray, defs: dict[str, str], top: int, min_sim: float):
    from sentence_transformers import SentenceTransformer
    st = SentenceTransformer("BAAI/bge-m3", device="cpu")
    tags = list(defs)
    D = st.encode([defs[t] for t in tags], normalize_embeddings=True)
    S = V @ D.T
    out = {}
    for ti, t in enumerate(tags):
        order = np.argsort(-S[:, ti])
        cands = [(domains[i], float(S[i, ti])) for i in order[:top] if S[i, ti] >= min_sim]
        out[t] = cands
    return out


def make_jobs(cands: dict[str, list], per_call: int):
    jobs = []
    for t, cs in cands.items():
        for bi in range(0, len(cs), per_call):
            jobs.append((t, bi, cs[bi:bi + per_call]))
    return jobs


def verify_all(defs: dict[str, str], cands: dict[str, list], texts: dict[str, str],
               cache: Path, per_call: int, workers: int) -> dict[str, list[dict]]:
    from concurrent.futures import ThreadPoolExecutor
    import threading

    jobs = make_jobs(cands, per_call)
    print(f"{len(jobs)} verify calls ({workers} workers)", flush=True)
    results: dict[str, list] = {t: [] for t in cands}
    lock = threading.Lock()
    t0 = time.time()

    def one(job):
        tag, bi, b = job
        cf = cache / f"tag_{tag}_batch_{bi:03d}.json"
        if cf.exists():
            arr = json.loads(cf.read_text())
            if arr is not None:
                return tag, arr
        places = "\n".join(f"{j + 1}. {d}: {texts.get(d, '')[:4000]}" for j, (d, _) in enumerate(b))
        prompt = PROMPT.format(tag=tag, definition=defs[tag], places=places)
        arr = None
        for attempt in range(2):
            try:
                content, _ = chat(MODEL, [{"role": "user", "content": prompt}], max_tokens=16384, timeout=300)
            except Exception as e:
                print(f"  {tag} b{bi} error: {e!r}", flush=True)
                break
            m = re.search(r"\[.*\]", content, re.S)
            if not m:
                continue
            try:
                cand = json.loads(m.group(0))
            except json.JSONDecodeError:
                continue
            want = {d.lower() for d, _ in b}
            if isinstance(cand, list) and cand and all(
                    isinstance(o, dict) and str(o.get("domain", "")).lower() in want for o in cand):
                arr = cand
                break
        cf.write_text(json.dumps(arr, ensure_ascii=False))
        return tag, arr or []

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for n, (tag, arr) in enumerate(ex.map(one, jobs), 1):
            with lock:
                results[tag].extend(arr)
            if n % 10 == 0 or n == len(jobs):
                print(f"  {n}/{len(jobs)} calls ({time.time() - t0:.0f}s) — {usage_report()}", flush=True)
    return results


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=300)
    ap.add_argument("--min-sim", type=float, default=0.35)
    ap.add_argument("--per-call", type=int, default=12)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    cache = T3 / "verify_cache"
    cache.mkdir(parents=True, exist_ok=True)
    ap_ = json.loads((EFFORT / "tier1" / "approved_tags.json").read_text())
    defs = ap_["definitions"]

    texts = load_profiles()
    domains, V = load_profile_vecs()
    print(f"profiles with text: {len(texts)} | embeddings: {len(domains)}", flush=True)
    sl = shortlist(domains, V, defs, args.top, args.min_sim)
    for t, c in sl.items():
        print(f"  {t:<20} candidates: {len(c)} (top sim {c[0][1]:.3f})" if c else f"  {t:<20} candidates: 0", flush=True)

    verified = verify_all(defs, sl, texts, cache, args.per_call, args.workers)
    (T3 / "verified.json").write_text(json.dumps(verified, ensure_ascii=False, indent=1))

    # ---- QA report ----
    lines = ["# Stage-3 QA — profile-level tag verification", "",
             f"- shortlist: top {args.top} per tag, min sim {args.min_sim}",
             f"- {usage_report()}", "", "| tag | true | unsure | false | kept |", "|---|---|---|---|---|"]
    kept: dict[str, list[dict]] = {}
    for t, arr in verified.items():
        vt = sum(1 for o in arr if o.get("verdict") is True)
        vu = sum(1 for o in arr if o.get("verdict") == "unsure")
        vf = sum(1 for o in arr if o.get("verdict") is False)
        kept[t] = [o for o in arr if o.get("verdict") is True and o.get("evidence")]
        lines.append(f"| {t} | {vt} | {vu} | {vf} | {len(kept[t])} |")
    lines += ["", "## Evidence spot-check (random 3 per tag)", ""]
    random.seed(8)
    for t, arr in kept.items():
        lines.append(f"### {t}")
        for o in random.sample(arr, min(3, len(arr))):
            lines.append(f"- **{o['domain']}**: “{o['evidence'][:200]}”")
        lines.append("")
    (T3 / "qa_report.md").write_text("\n".join(lines) + "\n")
    print(f"report → {T3 / 'qa_report.md'}", flush=True)


if __name__ == "__main__":
    main()

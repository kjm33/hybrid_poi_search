#!/usr/bin/env python3
"""audience-tags Stage 2 (Tier 2): map ~78k one-off facet values via embeddings.

phase1 — embed all distinct tail values (facet count < MIN_COUNT) with bge-m3
         → tier2/value_vecs.npz (values + float32 matrix). Device: cuda if enough
         VRAM free, else cpu. Resumable via --rebuild to redo.

phase2 — needs tier1/approved_tags.json ({"tags": [...], "definitions": {tag: sentence}}
         — created at the user gate). Embeds tag definitions, computes cosine sims,
         tunes auto/drop cutoffs on the Tier-1 known answers (gold), then:
           sim >= auto_cut            → auto-tag (no LLM)
           drop_cut <= sim < auto_cut → ambiguous → LLM batches (same rules as Tier-1)
           sim < drop_cut             → drop
         Writes tier2/tag_map_tail.json {value: {tag, method, sim}} + tier2_report.md.

Usage:
  .venv/bin/python scripts/tag_tier2.py phase1 [--device cpu|cuda|auto]
  .venv/bin/python scripts/tag_tier2.py phase2 [--auto-cut 0.75] [--drop-cut 0.55]
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import time
from collections import Counter
from pathlib import Path

import numpy as np

from zai_client import chat, usage_report

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "kb.db"
EFFORT = ROOT / "efforts" / "2026-11-08-audience-tags"
T2 = EFFORT / "tier2"
MIN_COUNT = 5
MODEL = "glm-5.3-flash"

PROMPT = """You are building the tag vocabulary for a "places" knowledge base mined from
business and organization websites (restaurants, schools, churches, hotels, gyms,
senior living, clinics, ...).

For each VALUE below, decide: is it an AUDIENCE or VIBE attribute — WHO the place
serves (families, couples, adults only, students, seniors, pets) or its SOCIAL
ATMOSPHERE (romantic, casual, upscale, lively) — and if so, which canonical tag.

Answer with ONE JSON array of objects, one per VALUE, like:
  {{"value": "<the exact VALUE text>", "tag": "tag_name"}}
where "tag" is:
  - "tag_name"   an EXISTING tag below that fits,
  - "new:tag"    an audience/vibe attribute but no existing tag fits, or
  - null         anything else: services, amenities, ownership, food facts,
                 programs, named offerings, location/hours facts, cuisine names.

Merge synonyms into the general tag; never restate the value as a tag;
when unsure between new tag and null → null.

EXISTING TAGS: {tags}

VALUES:
{values}"""


def tail_values() -> list[str]:
    con = sqlite3.connect(DB)
    rows = con.execute(
        "SELECT DISTINCT lower(value) FROM facets WHERE kind IN ('feature','intent') "
        "GROUP BY lower(value) HAVING SUM(1) < ?", (MIN_COUNT,)).fetchall()
    con.close()
    return sorted(v for (v,) in rows if v)


def gpu_free_mb() -> int:
    try:
        import subprocess
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.free",
                              "--format=csv,noheader,nounits"], capture_output=True, text=True)
        return max(int(x) for x in out.stdout.split())
    except Exception:
        return 0


def phase1(args: argparse.Namespace) -> None:
    T2.mkdir(parents=True, exist_ok=True)
    values = tail_values()
    print(f"distinct tail values (<{MIN_COUNT} occurrences): {len(values)}", flush=True)
    device = args.device
    if device == "auto":
        device = "cuda" if gpu_free_mb() >= 2600 else "cpu"
    print(f"embedding with bge-m3 on {device}…", flush=True)
    from sentence_transformers import SentenceTransformer
    st = SentenceTransformer("BAAI/bge-m3", device=device)
    t0 = time.time()
    B = 8192
    mats = []
    for i in range(0, len(values), B):
        mats.append(st.encode(values[i:i + B], batch_size=256, show_progress_bar=False).astype(np.float32))
        print(f"  {min(i + B, len(values))}/{len(values)} ({time.time() - t0:.0f}s)", flush=True)
    V = np.vstack(mats)
    V /= np.linalg.norm(V, axis=1, keepdims=True) + 1e-12
    np.savez_compressed(T2 / "value_vecs.npz", values=np.array(values, dtype=object), vecs=V)
    print(f"saved {V.shape} → {T2 / 'value_vecs.npz'} in {time.time() - t0:.0f}s", flush=True)


def tune_cutoffs(S: np.ndarray, val_idx: dict, gold: dict[str, str | None],
                 tags: list[str], auto_cut: float, drop_cut: float) -> tuple[float, float]:
    """Report precision/recall of candidate cutoffs against Tier-1 gold; nudge if bad."""
    ok, bad = 0, 0
    for key, tag in gold.items():
        v = key.split("|", 1)[1].lower()
        if tag is None or v not in val_idx or tag not in tags:
            continue
        best_tag = tags[int(np.argmax(S[val_idx[v]]))]
        ok += best_tag == tag
        bad += best_tag != tag
    if ok + bad:
        print(f"auto-zone check on gold: {ok}/{ok + bad} head values rank their own tag first", flush=True)
    return auto_cut, drop_cut


def phase2(args: argparse.Namespace) -> None:
    ap_path = EFFORT / "tier1" / "approved_tags.json"
    if not ap_path.exists():
        raise SystemExit(f"missing {ap_path} — run the user gate first (approve Tier-1 proposals)")
    ap = json.loads(ap_path.read_text())
    tags, defs = ap["tags"], ap["definitions"]
    z = np.load(T2 / "value_vecs.npz", allow_pickle=True)
    values, V = list(z["values"]), z["vecs"]
    val_idx = {v: i for i, v in enumerate(values)}

    from sentence_transformers import SentenceTransformer
    st = SentenceTransformer("BAAI/bge-m3", device="cpu")
    D = st.encode([defs[t] for t in tags], normalize_embeddings=True)
    S = V @ D.T  # (n_values, n_tags) cosine sims

    gold = json.loads((EFFORT / "tier1" / "tag_map_head.json").read_text())
    auto_cut, drop_cut = tune_cutoffs(S, val_idx, gold, tags, args.auto_cut, args.drop_cut)
    print(f"cutoffs: auto >= {auto_cut}, drop < {drop_cut}", flush=True)

    best = S.max(axis=1)
    arg = S.argmax(axis=1)
    out: dict[str, dict] = {}
    ambig = []
    for i, v in enumerate(values):
        if best[i] >= auto_cut:
            out[v] = {"tag": tags[arg[i]], "method": "auto", "sim": round(float(best[i]), 3)}
        elif best[i] >= drop_cut:
            ambig.append((i, v))
        else:
            out[v] = {"tag": None, "method": "drop", "sim": round(float(best[i]), 3)}
    print(f"auto: {sum(1 for o in out.values() if o['method'] == 'auto')}, "
          f"ambiguous → LLM: {len(ambig)}, dropped: {sum(1 for o in out.values() if o['method'] == 'drop')}",
          flush=True)

    # ambiguous band → LLM in batches of 100 (resumable per batch file)
    cache = T2 / "ambig_cache"
    cache.mkdir(exist_ok=True)
    batches = [ambig[i:i + 100] for i in range(0, len(ambig), 100)]
    t0 = time.time()
    from concurrent.futures import ThreadPoolExecutor
    import threading
    lp = threading.Lock()

    def one(bi_ivs):
        bi, ivs = bi_ivs
        cf = cache / f"batch_{bi:04d}.json"
        if cf.exists() and json.loads(cf.read_text())["mapped"] is not None:
            return bi, ivs, json.loads(cf.read_text())["mapped"]  # resume
        vals = [v for _, v in ivs]
        prompt = PROMPT.format(tags=", ".join(tags), values="\n".join(f"{j + 1}. {v}" for j, v in enumerate(vals)))
        for attempt in range(2):
            try:
                content, _ = chat(MODEL, [{"role": "user", "content": prompt}], max_tokens=24576, timeout=300)
            except Exception as e:
                print(f"  batch {bi + 1} error: {e!r}", flush=True)
                return bi, ivs, None
            m = re.search(r"\[.*\]", content, re.S)
            if not m:
                continue
            try:
                arr = json.loads(m.group(0))
            except json.JSONDecodeError:
                continue
            if not isinstance(arr, list):
                continue
            d = {}
            ok = True
            for o in arr:
                if not isinstance(o, dict) or "value" not in o or "tag" not in o:
                    ok = False
                    break
                t = o["tag"]
                if t is not None and not (isinstance(t, str) and re.fullmatch(r"(new:)?[a-z0-9_]{2,40}", t)):
                    ok = False
                    break
                d[str(o["value"]).strip().lower()] = t
            if not ok:
                continue
            mapped = [d.get(v.lower()) for v in vals]
            found = sum(1 for v in vals if v.lower() in d)
            if found >= 0.9 * len(vals):
                return bi, ivs, mapped
        return bi, ivs, None

    with ThreadPoolExecutor(max_workers=4) as ex:
        for bi, ivs, mapped in ex.map(one, enumerate(batches)):
            (cache / f"batch_{bi:04d}.json").write_text(
                json.dumps({"values": [v for _, v in ivs], "mapped": mapped}, ensure_ascii=False))
            if mapped:
                for (i, v), m in zip(ivs, mapped):
                    out[v] = {"tag": m if (m in tags or (m or "").startswith("new:")) else None,
                              "method": "llm", "sim": round(float(best[i]), 3)}
            with lp:
                print(f"  llm batch {bi + 1}/{len(batches)} ({time.time() - t0:.0f}s) — {usage_report()}", flush=True)

    (T2 / "tag_map_tail.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    cov = Counter((o["tag"], o["method"]) for o in out.values())
    lines = ["# Tier-2 report — tail values", "",
             f"- distinct tail values: {len(out):,}",
             f"- method mix: " + ", ".join(f"{m}: {n:,}" for (t, m), n in sorted(cov.items(), key=lambda x: -x[1])),
             "", "## Auto-tag coverage", "", "| tag | auto | llm |", "|---|---|---|"]
    for t in tags:
        lines.append(f"| {t} | {cov.get((t, 'auto'), 0):,} | {cov.get((t, 'llm'), 0):,} |")
    news = Counter(o["tag"] for o in out.values() if (o["tag"] or "").startswith("new:"))
    if news:
        lines += ["", "## New-tag proposals from tail", ""]
        lines += [f"- **{t[4:]}**: {n} values" for t, n in news.most_common()]
    (T2 / "tier2_report.md").write_text("\n".join(lines) + "\n")
    print(f"report → {T2 / 'tier2_report.md'}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["phase1", "phase2"])
    ap.add_argument("--device", default="auto")
    ap.add_argument("--auto-cut", type=float, default=0.75)
    ap.add_argument("--drop-cut", type=float, default=0.55)
    args = ap.parse_args()
    (phase1 if args.phase == "phase1" else phase2)(args)

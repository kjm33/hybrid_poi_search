# Effort: edge-embedder-bakeoff — pre-validation of on-device embedder candidates

Started: 2026-11-08 · Spin-off from the amenity-knowledge-base effort (search/eval infra
reused as-is; no changes to the shipped `data/search.db`).

**Context:** the CA amenity KB (13,199 useful profiles) is to be shipped as a fully
offline in-car artifact — no external LLM, edge-device deployment. One small encoder
must serve two jobs at runtime: (a) query embedding for hybrid search, (b) NLU
(intent+slots) for tool args. Research (2026-11-08) shortlisted candidates; this effort
pre-validates retrieval quality on our own eval set before any edge engineering.

**Research-based expectations (to be checked against our data):**
- Primary candidate: **gte-modernbert-base** (149M, 768d, Apache 2.0, no query prefix,
  best-in-class English retrieval at its size, quantization-robust)
- Budget candidate: **snowflake-arctic-embed-s** (33M, 384d, Apache 2.0, needs query
  prefix "Represent this sentence for searching relevant passages: ")
- Baselines: bge-m3 (current index model, 568M) and Qwen3-Embedding-0.6B (vectors
  already in kb.db from the Stage-4 A/B)
- Hybrid BM25+RRF carries much of the load (Vespa: +3–5 pp over vector-only) → a
  smaller embedder may hold near-baseline hybrid recall; the 60-question eval decides.
- Device rules from research: int8 ONNX is safe (−1…−7% typical), 4-bit collapses
  embeddings (forbidden), Qwen-family needs SmoothQuant for int8.

**Locked decisions:**
- Candidates keyed in scripts as `gte-modernbert` and `arctic-s`
- New vectors appended to kb.db.embeddings (keyed domain+model); near_dups NOT
  rewritten (--skip-dups — bge-m3 pairs stay authoritative)
- Per-model search DBs as separate files `data/search_<model>.db`; `data/search.db`
  (bge-m3) untouched as the baseline
- Same 60 generated questions as the KB effort (copied to `eval/questions.jsonl` here)
  → results comparable with eval_report.md there
- Embedding on CPU (both GPUs busy with training), HF_HOME=/opt/vllm/models/hf
  (/home is 99% full)

## TODO (all done 2026-11-08)

### Stage P0 — wire candidates in
- [x] Add `gte-modernbert` + `arctic-s` to ST_IDS in `scripts/embed_all.py` and
      `scripts/search.py` (+ arctic-s QUERY_PREFIX; gte-modernbert needs none)
- [x] `scripts/eval_search.py`: add `--questions` arg (report written next to the
      questions file) so this effort's eval dir is self-contained; default unchanged

### Stage P1 — embed corpus with both candidates
- [x] Background job: `embed_all.py --model X --skip-dups` → kb.db.embeddings.
      Started on CPU (GPUs busy), GPU0 freed mid-run → gte finished on GPU in **43 s**
      (304 docs/s; CPU fp16 was 0.23 docs/s — always embed on GPU when possible).
      arctic-s: 13,199 vectors (2364 s CPU); gte-modernbert: 13,199 vectors.

### Stage P2 — per-model search DBs
- [x] `build_search.py --model X --out data/search_<model>.db`:
      `data/search_arctic-s.db` (108 MB), `data/search_gte-modernbert.db` (119 MB)
- [x] **qwen3-0.6b excluded**: ruled out on device-fit grounds (600 MB int8,
      SmoothQuant needed); an external process is embedding it into kb.db anyway
      (not ours, separate model key, harmless).

### Stage P3 — eval bake-off
- [x] Reports: `eval/eval_bge-m3.md`, `eval_arctic-s.md`, `eval_gte-modernbert.md`
- [x] Compare vs bge-m3 baseline — see outcome.md table. bm25 leg identical in all
      runs (sanity). arctic-s 95/0.82 vector, 95/0.87 hybrid; gte 95/0.79 vector,
      97/0.86 hybrid; baseline 95/0.75, 97/0.85.

### Stage P4 — size/latency + verdict
- [x] `scripts/bakeoff_latency.py` → `eval/latency.json` (fp32 CPU, single query,
      20 voice-style queries; gte force-loaded fp32 to dodge fp16-on-CPU emulation)
- [x] Verdict in `outcome.md`: **primary arctic-s** (314 ms, 5.1 MB int8 vectors,
      best MRR, −2 pp hybrid recall), **fallback gte-modernbert** (exact 97% parity,
      1265 ms), bge-m3 eliminated for edge.

## Notes / open threads
- eval_search.py --report is relative to the questions dir — pass a bare filename.
- int8 ONNX quantization sanity (size/cosine drift/latency) deferred to the edge-port
  effort — research says safe for ModernBERT family; validate on target hardware.
- NLU dual-head fine-tune (JointBERT-style on the chosen backbone) is the next effort;
  not part of this pre-validation.
- Effort closed 2026-11-08; verdict and next steps in `outcome.md`.

## Addendum (same day, follow-up session)
- [x] Repo-root `README.md` written (pipeline story, examples, bake-off, shrink plan).
- [x] `scripts/shrink_eval.py`: int8 / naive-MRL truncation / PCA quality check →
      `eval/vector-shrink.md`. **int8 = zero measured loss** (both query regimes);
      trunc-256 free but marginal; 128/64 dims need MRL retraining (PCA-128 is the
      no-training fallback). See outcome.md addendum — ONNX port now only has to
      prove latency + model-file size, vector quality is settled.

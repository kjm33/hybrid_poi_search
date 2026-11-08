# Outcome: edge-embedder bake-off (pre-validation)

Date: 2026-11-08 · Eval set: same 60 generated questions as the KB effort
(`eval/questions.jsonl`) · recall@10 / MRR@10 · baseline = bge-m3 index
(`data/search.db`, numbers identical to KB effort → valid comparison).

## Results

| model | params | dim | vector | hybrid | CPU query ms (mean/p95) | corpus vectors int8 |
|---|---|---|---|---|---|---|
| bge-m3 (baseline) | 568M | 1024 | 95% / 0.75 | **97%** / 0.85 | 2826 / 4834 | 13.5 MB |
| gte-modernbert | 149M | 768 | 95% / 0.79 | **97% / 0.86** | 1265 / 2442 | 10.1 MB |
| arctic-s | 33M | 384 | 95% / **0.82** | 95% / **0.87** | **314 / 1079** | **5.1 MB** |

bm25 leg identical in all runs (95% / 0.85 — same corpus text) → sanity check passed.
Per-model reports: `eval/eval_bge-m3.md`, `eval_gte-modernbert.md`, `eval_arctic-s.md`,
raw latency in `eval/latency.json`.

## Plain-language reading

- **arctic-s (33M) is the surprise**: ties the 568M baseline on vector recall (95%),
  beats every model on ranking quality (MRR 0.82 vector / 0.87 hybrid), encodes a
  voice query in ~0.3 s on a busy CPU in plain fp32 — before int8. Costs exactly
  2 of 60 questions on hybrid recall (95% vs 97%).
- **gte-modernbert (149M) is the exact-parity pick**: matches the baseline's 97%
  hybrid recall with slightly better MRR (0.86), at 1/4 the parameters. But 1.27 s
  fp32 CPU per query is borderline for voice; int8 ONNX (~2–4× expected, ModernBERT
  quantizes best-in-class per research) should bring it to ~300–600 ms.
- **bge-m3 is eliminated for edge**: ~2.8 s per query on CPU, 568M params. Stays as
  the server-side baseline.

## Verdict

**Primary for the edge artifact: snowflake-arctic-embed-s.** Smallest, fastest,
best-ranking; the −2 pp hybrid recall is the only cost and the cheapest to buy back
(RRF weight tuning, int8 re-eval). **Named fallback: gte-modernbert-base** if the
int8-ONNX re-eval on target hardware shows arctic-s losing more than ~2 pp — it is
the guaranteed-quality option at still-reasonable latency.

Decision rule from research was "smallest model holding hybrid quality": strictly,
that is gte (97%). We take the 2 pp trade deliberately because latency and footprint
are hard constraints in-car while the missing 2 questions are name-heavy queries the
BM25 leg already nearly covers.

## Caveats

- Latency measured single-query fp32 on this machine's CPU **while an external
  qwen3-0.6b embed job competed for cores** → absolute numbers inflated, ratios and
  ordering reliable. On the target SoC expect different absolutes; rerun there.
- gte-modernbert ships fp16 weights → on CPU it must be loaded fp32
  (`scripts/bakeoff_latency.py` does this) or it emulates fp16 ~25× slower.
- Build-time lesson: embed on GPU whenever one is free — gte did 13,199 docs in
  **43 s on GPU0 (304 docs/s)** vs a projected ~16 h in fp16-on-CPU.
- qwen3-0.6b excluded (ruled out on device-fit: ~600 MB int8, SmoothQuant needed);
  an external process is still embedding it into kb.db (separate model key, harmless).

## Next steps (separate efforts)

1. **Edge port**: int8 ONNX export of arctic-s (+ gte fallback), cosine-drift check,
   re-run this eval, latency on target hardware. (Research: int8 safe −1…−7%;
   4-bit forbidden.)
2. **NLU dual-head**: JointBERT-style intent+slots fine-tune on the chosen backbone
   (GLM-synthesized utterances at build time).
3. **Geo blocker**: crack the POI join key for `california_amenities-matched-flat.db`
   (74k POIs) → H3 index in the artifact.

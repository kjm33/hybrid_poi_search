# web_mining — California amenity knowledge base & edge search

This repo turns ~13,500 California amenity websites (restaurants, dentists, nightclubs,
surf cafés…) into a compact, offline, car-navigation-ready search package:
**place cards → hybrid BM25 + vector search → a single SQLite artifact** small enough
for an edge head unit. All heavy AI runs once at build time; the car only searches.

Current state (Nov 2026): knowledge base built, hybrid search at **97% recall@10**
(bge-m3) on the 60-question eval, edge embedder bake-off done —
**`arctic-s` selected** (95% recall / 0.87 MRR, 314 ms/query on CPU, 5.1 MB of int8
vectors), `gte-modernbert` as fallback. int8 quantization verified **loss-free** on
the eval (§7); minimum edge artifact sized at **~18 MB** (§8).
Next: int8 ONNX port, tiny NLU head, geo join.

---

## 1. How webpage content was processed (build time)

A local LLM (qwen3-30b via vLLM) read every website once and wrote one
**place card** per business — a standardized row in `data/kb.db` (`profiles` table,
13,521 rows, 13,199 useful after gating). Real card (`steamerlanesc.com`):

| Field | Content (trimmed) |
|---|---|
| **self_introduction** | "We are Steamer Lane Supply, a beachside spot offering healthy food, drinks, and surf gear right across the street from the famous Steamer Lane surf break… We also welcome your furry companions with a dog menu, water bowl, and free treats." |
| **detailed_profile** | "…serves as a go-to spot for surfers, beachgoers… All seating is outdoors in the park…" |
| **keywords** | `surf food`, `dog friendly surf spot`, `healthy post-surf meal`, `snacks near steamer lane` … |
| **intents** | `healthy post-surf meal`, `dog-friendly beach food`, `outdoor beach dining` … |
| **features** | `outdoor seating`, `dog-friendly`, `kid-friendly`, `surf supplies` |

Plus structured facets (`osm_type`, `city`, `price_level`, cuisine…), `opening_hours`,
and near-duplicate detection (`near_dups`, 58 known pairs).

## 2. How search works

Each query is answered by **two "librarians" fused into one ranking** (RRF, k=60):

- **BM25 word index (FTS5)** — exact word matching. Great for names ("Jalisco's").
- **Vector search** — every card is embedded into meaning-coordinates; the query is
  embedded the same way and the nearest cards win. Catches slang the word index
  can't: *"dog friendly post-surf food in Santa Cruz"* → **Steamer Lane Supply**
  (no card literally says "post-surf food").

Eval: 60 generated driver-style questions (`efforts/*/eval/questions.jsonl`),
metrics recall@10 ("was the right card in the top 10?") and MRR@10 ("how high?"
— 1.0 = always first).

## 3. Embeddings & database layout

`scripts/embed_all.py` embeds each card as
`self_introduction + detailed_profile + keywords` → one vector per card, **stored per
model** in `kb.db.embeddings` (keyed `(domain, model)` — the same card has separate,
mutually incomparable vectors under each model). Then `scripts/build_search.py`
produces **standalone per-model search databases**:

| File | Meaning model | Vector dim | Size |
|---|---|---|---|
| `data/search.db` | bge-m3 | 1024 | 136 MB |
| `data/search_gte-modernbert.db` | gte-modernbert | 768 | 119 MB |
| `data/search_arctic-s.db` | **arctic-s (chosen)** | 384 | 108 MB |

Each DB is self-contained: card text + FTS5 word index + that model's vectors +
facets + near_dups, with `meta.model` recording its pairing. Swapping the meaning
model on the device = swapping one `.db` + one model file.

## 4. The edge bake-off (effort `2026-11-08-edge-embedder-bakeoff`)

bge-m3 needs **2.8 s per query on CPU** — unusable for voice. Three candidates,
same 60 questions, query encoding on GPU, latency measured on CPU (stands in for
the car chip):

| Model | hybrid recall@10 | hybrid MRR | CPU ms/query (mean/p95) | int8 vectors |
|---|---|---|---|---|
| bge-m3 (568M) | 97% | 0.85 | 2826 / 4834 | 13.5 MB |
| gte-modernbert (149M) | 97% | 0.86 | 1265 / 2442 | 10.1 MB |
| **arctic-s (33M)** | 95% | **0.87** | **314 / 1079** | **5.1 MB** |

**Verdict:** arctic-s — voice-grade latency, smallest, best ranking; the cost is 2 of
60 questions in hybrid recall. gte-modernbert is the guaranteed-parity fallback if
int8 re-eval ever drops arctic-s by more than ~2 points. Full write-up:
`efforts/2026-11-08-edge-embedder-bakeoff/outcome.md`.

## 5. What is arctic-s, exactly?

The most old-school model that won: a **plain 12-layer BERT** (33M params, 384-dim,
classic 30,522 English vocab, 512-token window, 133 MB fp32) retrained by Snowflake
with modern contrastive recipes. Three habits to respect:

1. **Query prefix required**: `"Represent this sentence for searching relevant passages: "`
   must be glued before every *query* (never documents) — wired into
   `search.py:QUERY_PREFIX`.
2. **English-only** — fine by project decision.
3. **512-token span** — our cards fit comfortably.

It only maps text → 384 numbers; it cannot classify or generate. Intent/slot
understanding ("open now near me", "cheap") is planned as a separate tiny
JointBERT-style head.

## 6. Making it smaller & sharper

The 108 MB `search_arctic-s.db` breaks down as: card text ~34 MB, **vectors 20.3 MB
(float32)**, FTS5's duplicate copy of the text 21.8 MB, facets 21.8 MB, inverted
index ~10 MB. Shrink ladder:

1. **int8 stored vectors** — 20.3 → 5.1 MB; ~1–2% quality cost expected
   (verified in §7 below).
2. **FTS5 external-content mode** — removes the 21.8 MB duplicate; DB is read-only
   on the device, so this is free.
3. **Facets re-shape** (PK order / dictionary encoding) — up to −15 MB, zero risk.
4. **Text diet** — gzip display-only fields, don't ship long profiles.
5. **Matryoshka / shorter vectors** — see §7.

Quality lever (later): **contrastive fine-tuning** on synthetic driver queries with
hard negatives mined from our own facets (same city + category decoys), keeping the
60 eval questions held out. Distillation from bge-m3/gte can ride along as a second
loss.

## 7. Shrink experiments — int8, Matryoshka, PCA

Measured by `scripts/shrink_eval.py`. Baseline float32: vector 95%/0.82, hybrid
95%/0.87. How each variant is computed:

- **int8** — per vector: scale so the largest |value| maps to 127, round to whole
  bytes, dequantize back for scoring. This ranking is mathematically identical to
  true on-device int8 dot products (same per-vector absmax scale), so quality is
  measurable without any ONNX machinery.
- **Truncation ("naive Matryoshka")** — keep the first N of the 384 numbers of
  docs *and* queries, renormalize. A model truly trained the Matryoshka way
  (MRL, after the nesting dolls) has its dimensions deliberately sorted by
  importance, so every prefix is a valid shorter embedding. arctic-s is not such
  a model — its meaning is smeared evenly across dimensions (dim #17 no more
  important than dim #300, like judging a book by a random half of its pages),
  so truncation is the pessimistic bound.
- **PCA-128 / PCA-64** — fitted on our own 13,199 card vectors: subtract the mean
  card, run SVD, keep the top-k directions in which the card cloud spreads most
  (128 axes retain **76%** of total variance, 64 retain **58%**), project every
  card onto them, renormalize to unit length. Queries get the same *frozen*
  transform (same mean, same axes — fitted on cards only, never on questions).
  Like photographing a 3D object from its most informative angle: drop
  dimensions, keep recognizability. Unlike truncation, PCA *measures* which
  mixtures of the 384 dims matter most on our cards, instead of assuming they
  came pre-sorted.

**Results** (`scripts/shrink_eval.py`, report in `efforts/2026-11-08-edge-embedder-bakeoff/eval/vector-shrink.md`; baseline row reproduces the bake-off numbers exactly — internal sanity ✓):

| variant | dim | total MB | vector R@10 / MRR | hybrid R@10 / MRR |
|---|---|---|---|---|
| float32 (baseline) | 384 | 5.1 (as int8) | 95% / 0.82 | 95% / 0.87 |
| **int8 docs, float query** | 384 | **5.1** | 95% / 0.83 | **95% / 0.87** |
| int8 docs + int8 query | 384 | 5.1 | 95% / 0.82 | 95% / 0.87 |
| trunc-256 (naive MRL) | 256 | 3.4 | 95% / 0.78 | 95% / 0.87 |
| trunc-128 (naive MRL) | 128 | 1.7 | 90% / 0.73 | 95% / 0.81 |
| trunc-64 (naive MRL) | 64 | 0.8 | 77% / 0.68 | 97% / 0.77 |
| pca-128 (76% var.) | 128 | 1.7 | 93% / 0.78 | 97% / 0.85 |
| pca-64 (58% var.) | 64 | 0.8 | 92% / 0.61 | 95% / 0.83 |

Plain-language reading:

- **int8 quantization is free on our data** — identical recall, MRR, and miss list in
  both directions (quantizing only stored vectors, or queries too). 20.3 → 5.1 MB,
  zero measured quality cost (better than the −1…2% research expectation). The
  planned int8 ONNX port is green-lit by this.
- **Naive truncation to 256 dims costs nothing in hybrid** (95%/0.87) — but only
  saves 1.7 MB, so 384 int8 stays the default.
- **arctic-s is NOT usable at 128/64 dims without retraining** — the vector leg
  degrades sharply (MRR 0.82 → 0.73/0.68). If 1.7 MB ever matters, the no-training
  compromise is **PCA-128** (hybrid 97%/0.85, −0.02 MRR); the proper fix is a
  Matryoshka (MRL) fine-tune.
- The "+2pp" hybrid recall cells at trunc-64/pca-128 are **fusion noise, not gains**:
  a weaker vector leg shifts weight to BM25, which happened to rescue 1–2 questions
  into the top 10 — while overall ranking (MRR) got worse. Trust MRR here.
- **PCA's failure mode is graceful, truncation's is not**: pca-64 still finds the
  right card in the top 10 for 92% of questions while MRR collapses (0.82 → 0.61) —
  broad neighborhoods survive ("taco place, not a dentist"), the fine ordering
  inside them scrambles ("*which* taco place first"). Naive trunc-64 instead loses
  the answer entirely for 1 in 4 questions (recall 77%).
- **trunc-256 being free is a real (if useless) fact**: the 13k cards live in a
  corner of the 384-dim space and don't exercise the last ~128 dims at all. A true
  MRL fine-tune (train so every prefix stays a good embedding, on our synthetic
  queries) would make 128-dim truncation safe — only worth it if ~3 MB ever
  matters, which it doesn't (the DB is text-dominated).

## 8. What actually ships — the edge artifact

Query flow on the device — two retrievers **in parallel**, fused by rank. This is
*not* a retrieve-then-rerank pipeline:

```
"dog friendly post-surf food in Santa Cruz"
     ├── BM25 leg (FTS5 word index over card text) ───► top-10 list A
     └── arctic-s embeds the question (~314 ms, the    ┐
         only expensive step)                           ▼
         dot-product vs ALL 13,199 int8 vectors (~1–3 ms) → top-10 list B
     └── RRF fuse A + B by rank position ─────────────► final top-10
```

Notes against common misconceptions:

- **No candidate pre-selection stage.** The vector leg scans *all* 13,199 cards on
  every query — ~5M multiply-adds ≈ 1–3 ms, noise next to the 314 ms query
  encoding. At this scale brute force beats any prefilter, and a cross-encoder
  "rerank" second pass would be *more* expensive (one neural pass per candidate),
  not less.
- **We embed the question text, not an "intent".** Intent (open-now, near-me,
  cheap) is the separate JointBERT head from the roadmap — its output becomes
  *filters* (city / type / open_now), not part of the similarity vector.

Minimum shippable brain — **~18 MB**, keeps full hybrid quality:

| Artifact | Contents | Size |
|---|---|---|
| vectors blob | int8 384-dim vectors + integer IDs | 5.1 MB |
| display metadata | name, city, one-liner, URL — what the driver sees | ~3 MB |
| BM25 word index | FTS5 inverted index (external-content mode) | ~10 MB |
| *(optional)* full cards | long profiles, only if the agent explains them | ~40 MB |

Why keep BM25 on the device at all: measured, vector-only matches hybrid recall
(95%) but loses ranking height (MRR 0.82 vs 0.87) — and the word index is the
insurance for exactly what a 33M-param model handles worst: **exact names and rare
words** ("Find Jalisco's"). Today's 108 MB `search_arctic-s.db` is the *workbench*
version (long profiles, duplicated FTS content); carving the ~18 MB artifact above
is roadmap item 5.

## 9. How to run

```bash
# hybrid search (auto model from meta table)
.venv/bin/python scripts/search.py "dog friendly post-surf food in Santa Cruz"
.venv/bin/python scripts/search.py --db data/search_arctic-s.db "late night tacos" --json

# evaluate a search DB on the 60 questions (report lands next to questions.jsonl;
# --report must be a BARE filename — it is resolved relative to the questions dir)
.venv/bin/python scripts/eval_search.py --db data/search_arctic-s.db \
    --questions efforts/2026-11-08-edge-embedder-bakeoff/eval/questions.jsonl \
    --report eval_arctic-s.md --device cuda

# CPU latency probe per model
.venv/bin/python scripts/bakeoff_latency.py

# int8 / truncation / PCA quality check (this effort)
HF_HOME=/opt/vllm/models/hf .venv/bin/python scripts/shrink_eval.py --device cuda
```

Env notes: models cached under `HF_HOME=/opt/vllm/models/hf` (home disk is nearly
full); embed on a free GPU when possible (13k cards: 43 s on GPU vs ~16 h on CPU).

## 10. Repo map

```
data/                  SQLite artifacts (gitignored): kb.db, search*.db, OSM POIs
scripts/               embed_all, build_search, search, eval_search, bakeoff_latency, shrink_eval
efforts/               dated effort dirs (spec/tasks/outcome per effort)
research/              notes from online research (embedder survey 2026-11)
```

## 11. Roadmap

1. int8 ONNX port of arctic-s + re-eval on target hardware (fallback: gte-modernbert).
2. JointBERT-style dual-head NLU (intent + slots) on the chosen backbone.
3. POI join-key blocker: link the 74k OSM POI coordinates to kb.db domains → H3 geo
   index for "near me".
4. Contrastive fine-tune with synthetic queries + hard negatives.
5. DB slimming → carve the ~18 MB edge artifact (§8): FTS5 external content,
   facets re-shape, text diet.

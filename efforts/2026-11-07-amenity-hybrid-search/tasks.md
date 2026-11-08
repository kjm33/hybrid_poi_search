> **SUPERSEDED 2026-11-07** → continue in `efforts/2026-11-07-amenity-knowledge-base/tasks.md`
> (Stage 0 here is done and authoritative; Stages 1-4 moved there, expanded with taxonomy,
> dedupe, CLI-first search, MCP, eval.)

# Effort: amenity-hybrid-search — LLM enrichment + hybrid search over CA amenity webpages

Started: 2026-11-07 · Source: `data/extracted_content.db` (18,089 rows; 15,798 with text)

**Goal:** effective semantic + keyword (hybrid) search over California amenity websites:
garbage filtered out, every useful page enriched by GLM into a structured profile
(incl. first-person `self_introduction` and `intents`), embedded with bge-m3,
clustered for facets/QA, indexed for fused BM25 + vector search.

**Locked decisions:**
- Language of all generated fields: **English only**
- Extraction model: **A/B test first** (GLM-4.6 vs Air variant, 50-page sample), then commit
- Embeddings: **local bge-m3** on `self_introduction + detailed_profile + keywords`
- **No POI join for now** — index keyed by `domain`; POI metadata (74k rows in
  `data/california_amenities-matched-flat.db`, join key still unknown) layered on later
- LLM verdict fields in the same pass as extraction (one call per page, no separate classifier)
- Non-English real-business pages stay in the LLM path (prompt says: translate to English)

## TODO

### Stage 0 — Rule-based prefilter (no LLM)
- [x] `scripts/prefilter.py`: parse front-matter, clean body, classify
      `ok / review / quarantine / no_content` with reason codes + language flag
- [x] Write `data/enrichment.db` → `page_quality` (domain, verdict, reasons, lang,
      clean_chars, title/description from front-matter, cleaned body for the LLM stage)
- [x] Run + verify — final counts: **10,017 ok + 3,506 review = 13,523 to LLM**;
      2,275 quarantine (too_short 2,005 · spam_dominant 158 · domain_parking 62 ·
      under_construction 40 · error_page 9 · redirect_stub 1); 2,291 no_content
      Spot-checked both sides; 158 spam quarantines verified as fully-replaced pages

### Stage 1 — A/B model test
- [ ] `scripts/extract_ab.py`: stratified 50-page sample (by length bucket),
      same prompt through GLM-4.6 and Air variant, outputs cached side by side
- [ ] Compare: JSON schema compliance, self-intro quality, intent coverage → pick winner
      (**needs user look at outputs before the full run**)

### Stage 2 — Full extraction pass (z.ai quota)
- [ ] `scripts/extract_all.py`: resumable per-domain response cache, concurrent workers,
      background job with log; re-runs failed pages
- [ ] Run over all `ok + review` pages (~13–15k; est. ~20M tokens, hours at 8–16 concurrency)
- [ ] Output schema per page: `name, type, cuisine, location, short_description,
      detailed_profile, self_introduction, intents[], features[], services[], audience,
      price_level, opening_hours, keywords[], page_type, is_useful, confidence`

### Stage 3 — Embeddings + clustering
- [ ] Install/verify bge-m3 locally; embed `self_introduction + detailed_profile + keywords`
      → vector table in `enrichment.db`
- [ ] HDBSCAN over vectors → facet candidates, residual garbage clusters, extraction QA report

### Stage 4 — Hybrid search index + eval
- [ ] `data/search.db`: FTS5(title, body, keywords, self_intro, intents) + vectors
      (current FTS in source DB covers only title/description — too thin)
- [ ] `scripts/search.py`: BM25 + vector → Reciprocal Rank Fusion; optional GLM rerank top-20
- [ ] Eval set of ~20 representative queries; sanity report with plain-language read

## Notes / open threads
- **NEW garbage class found:** hacked sites serving Indonesian gambling spam
  (slot gacor / togel / sbobet). 158 pages fully replaced → quarantined
  (`spam_dominant`); 40 real pages with injected spam sections → `review`
  (`spam_present`) — Stage 2 prompt must say: ignore injected gambling/betting
  sections; extract only real business info; if none, `is_useful=false`, `page_type="spam"`
- `matched_places.place_id` does not hash-match domain/url/name (md5/sha1/sha256/uuid5 tested);
  join key presumably lives in the upstream pipeline DB
- Careful with "parking" keyword: matches legit `amenity=parking` lots — only quarantine
  domain-parking phrases ("is for sale", "hugedomains", "buy this domain", …)
- Git repo initialized 2026-11-08 — this effort's Stage 0 landed as commit
  `feat(prefilter)`, the rest under the successor effort

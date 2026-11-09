# Effort: audience-tags — mine facet values → tag vocabulary → per-profile audience_fit facets

2026-11-08 · Continues `efforts/2026-11-07-amenity-knowledge-base` (its kb.db, embeddings,
facets, hybrid search are the substrate).

**Goal:** turn free-text feature/intent facet values into a controlled audience/vibe tag
vocabulary (family_friendly, business_friendly, …) and assign tags to the 13,521 profiles
as a new `facets` kind `audience_fit`, flowing into the existing hybrid search.

**Method (see `2026-11-08-audience-tags-solution-explained.md`):** Tier-1 LLM normalization
of ~3.5k head values → Tier-2 embedding sort of ~78k tail values (three zones, LLM only for
the ambiguous band) → per-profile shortlist + LLM verify with evidence quotes.

**Stack note (2026-11-08):** both GPUs busy (training job) → LLM calls via z.ai
glm-5.3-flash (`zai_client.py`), ~36 calls Tier-1; Stage-2 embedding on CPU if GPUs stay
busy. Fine-tuning embeddings: rejected for now, revisit triggers documented in the report.

## TODO

### Stage 1 — Tier-1 head normalization (LLM)
- [x] `scripts/tag_vocabulary.py`: head values (3,519 with ≥5×) batched 100/call to
      glm-5.3-flash — all mapped after echo-value format fix (off-by-one length bug)
- [x] Full run done (36 batches; 2 crash post-mortems: read timeout → 300s, budget → 24k tokens)
- [x] `tier1/tier1_report.md`: 8 seed tags + 18 proposals with examples
- [x] **User gate PASSED** — "accept all recommendations": 9 proposals approved
      (casual, upscale, cozy, community_focused, lively, seniors, beginner_friendly,
      adults_only, lgbtq_friendly), 8 rejected, senior_friendly→seniors merged;
      `scripts/tag_gate.py` wrote `tier1/approved_tags.json` (17 tags + definitions)
      and applied value overrides (date night→romantic — 1,260-row null miss)
  - Done when: report exists, every proposed tag has ≥3 example values attached ✓

### Stage 2 — Tier-2 tail mapping (embeddings)
- [x] `scripts/tag_tier2.py`: embed tail values — 75,453 distinct (<5×) embedded with
      bge-m3 on CPU (54 min, GPUs busy) → `tier2/value_vecs.npz` (75453×1024)
- [x] Cutoffs tuned on Tier-1 gold (396 tagged values): gold-to-own-definition median
      0.595, p90 0.703; null max-sim p95 0.602 → **auto_cut 0.65** (0.6% null leak),
      **drop_cut 0.55**; LLM band ≈ 6-7k values (~65 batches)
- [x] phase2 run DONE (105 LLM batches, 1.32M completion tokens, ~2.4 h): zones
      drop 63,699 / llm 10,471 / auto 1,283 → `tier2/tag_map_tail.json` +
      `tier2/tier2_report.md`. Per-tag tail values: groups_events 779, family_friendly
      680, casual 629, romantic 407, community_focused 377, seniors 352…;
      tail re-proposals (peaceful/calm ~50, historic/nostalgic ~37) recorded for
      possible v2 — NOT added (17 tags stay locked; note tag_map_tail.json contains
      new:* entries, Stage 4 must filter to approved tags only)
  - Done when: every distinct facet value has exactly one mapping; coverage stats in
      `tier2/tier2_report.md` ✓

### Stage 3 — profile-level assignment (shortlist + verify)
- [x] `scripts/tag_profiles.py`: cosine top-300 shortlist per tag vs existing
      kb.db embeddings → glm-5.3-flash verify with evidence quotes (parallel, resumable,
      echo-domain validation; final print had leftover NameError — fixed post-run,
      outputs were already written)
- [x] Run DONE: 425 calls / 4 workers / ~1.8 h / 1.57M completion tokens →
      `tier3/verified.json` + `tier3/qa_report.md` (2,212 true pairs, evidence quotes
      auditable; known gray zones: vets/groomers under pet_friendly, rehab clinics
      under accessible — evidence trail shows them honestly)
- [x] Recall vs gold: family_friendly facet-gold 2,172/2,172 = 100% (tautological via
      facet-dict source; stage3∪facets union is the design)
  - Done when: qa_report shows per-tag counts + evidence samples ✓

### Stage 4 — write facets + search integration
- [x] `scripts/tag_write_facets.py`: audience_fit = stage3-true ∪ facet-dict hits
      (tier1+tier2 dicts, new:* dropped, 17 approved tags) → **14,239 rows,
      7,556/13,521 profiles (56%)** → `tier4/facets_report.md` + provenance.json
- [x] search.py picks up any facets kind via generic `--facet key=value` path — no
      code change needed; `data/search.db` rebuilt (rm first: build_search.py doesn't
      drop the FTS table on re-run). GPU note: search.py fails loading bge-m3 on CUDA
      when a GPU is visible — run with CUDA_VISIBLE_DEVICES="" (CPU, ~2-5 s/query)
- [x] Smoke queries pass: romantic + "candlelit dinner for two" → restaurants;
      family_friendly + type=restaurant + "place to take the kids" → family
      restaurants; pet_friendly + "bring my dog" → dog café/daycare
  - Done when: smoke queries return sensible filtered hits via CLI ✓

### Stage 5 — close-out
- [ ] Update this file + KB effort tasks.md cross-link; commit
- [ ] Optional (only if tag set grows ≥50): distillation classifier on bge-m3 vectors
  - Done when: session-end three lines in STATE/tasks

## Done
- [x] Solution research (online) + design discussion (this conversation)
- [x] Plain-language report saved: `2026-11-08-audience-tags-solution-explained.md`
- [x] Report enhanced (2026-11-09) with post-run numbers & mechanics: corrected
      headline counts (153,168 facet rows / 79,038 spellings), Stage-4 union section,
      gate outcome, echo alignment, tuned cutoffs, 572-call economics, five intuitions.
      Note: the `.md.html` twin is a stale browser snapshot of the pre-enhancement md.

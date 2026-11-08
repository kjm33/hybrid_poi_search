# Effort: amenity-knowledge-base — profiles → taxonomy → hybrid search (CLI + agent)

Started: 2026-11-07 · Continues `efforts/2026-11-07-amenity-hybrid-search` (Stage 0 prefilter
done there: 13,523 ok+review pages in `data/enrichment.db` → `page_quality`).

**Goal:** turn cleaned CA amenity webpages into a knowledge base: LLM-enriched structured
profiles, normalized OSM-aligned taxonomy, local embeddings, dedupe + clustering QA,
hybrid BM25 + vector search with Reciprocal Rank Fusion — usable manually via CLI and
by an agent via MCP server.

**Locked decisions (this session):**
- All generated text fields: English only (unchanged)
- Extraction model: **local vLLM** — Qwen3-30B-A3B-Instruct-2507 (z.ai hit request-rate
  limits for the 13.5k-call full run; z.ai A/B of glm-5.3 vs glm-5.3-flash on 50 pages
  kept as quality reference — zero disagreements between the two). Originally FP8 TP=2,
  but GPU 1 was taken mid-flight by another session's training job (sft_lora heal_k18,
  ~18 GB) → pivoted to **cyankiwi/Qwen3-30B-A3B-Instruct-2507-AWQ-4bit (~18.1 GB) on
  GPU 0 alone** (TP=1, `--served-model-name qwen3-30b-a3b-awq`). If GPU 1 frees up
  before the full run, can switch back to FP8 TP=2 for more KV/concurrency.
- Embeddings: local, A/B **bge-m3 vs Qwen3-Embedding-0.6B** (3090s idle; Qwen3 leads MTEB
  multilingual 2026, bge-m3 gives dense+sparse in one model)
- Taxonomy: normalize LLM `type` → controlled OSM amenity vocabulary + dictionary tables
  for cuisine/feature/intent facets
- Search: SQLite FTS5 + sqlite-vec + RRF in one `data/search.db`; **CLI first**, MCP server
  as thin wrapper afterwards
- Eval: query-by-document — LLM generates ~50-100 questions whose answer is a known domain;
  recall@10 for BM25-only vs vector-only vs hybrid
- No POI join yet (join key still unknown); keyed by `domain`
- Index on `self_introduction + detailed_profile + keywords`; pages are short
  (median ~1.2k chars) → no chunking

## TODO

### Stage 1 — Extraction A/B (user gate before full run)
- [x] Run 50-page stratified sample through glm-5.3 + glm-5.3-flash
      (outputs in `ab/` here; run 2026-11-07, 100 calls, 268k tokens)
- [x] Read `ab/ab_report.md`; pick winner → **glm-5.3-flash** (zero disagreements
      with glm-5.3 on all 50 pages: same is_useful verdicts, same 9 garbage pages,
      same names; intros equal quality 41/41; flash ~10% faster, 22.4s vs 25.0s avg)
- [x] **User eyeballs side-by-side samples** → approved; pivot to local vLLM instead of
      z.ai for the full run (request-rate limits)
- [x] Serve Qwen3-30B-A3B via vLLM locally; re-ran same 50-page sample and compared
      against cached z.ai flash outputs. **Final setup: `cyankiwi/Qwen3-30B-A3B-Instruct-2507-AWQ-4bit`
      on GPU 0 only** (TP=1, `--served-model-name qwen3-30b-a3b-awq`; FP8 TP=2 plan dropped
      after GPU 1 was taken by another session's training job). Two launch fixes needed:
      `ninja` must be on PATH for flashinfer JIT (`PATH=/opt/vllm/env/bin:$PATH`), and
      vLLM 0.27 has no `--disable-log-requests`. **A/B result vs glm-5.3-flash (reference):
      100% valid JSON, 49/50 verdict agreement, all 41 both-useful intros pass (qwen avg
      343 chars vs 438), field fill qwen 88% vs flash 82%, avg latency 4.7s vs 20.3s —
      50-page batch took 59s at 4 workers.** Known diffs: 1 grounding failure
      (hoshiramen805.com — ADA-boilerplate-only page, qwen hallucinated a plausible intro,
      flash correctly discarded → add prompt rule for legal/policy boilerplate); qwen
      collapses page_type to `business` (14/50 diffs vs organization/chain_location/
      directory_listing → add prompt hint); emits intro on 2/8 garbage pages (harmless —
      indexing gated on is_useful). Logs: `/tmp/opencode/local_ab.log`, report
      `ab/ab_report.md` (z.ai copy preserved as `ab_report_zai.md`)

### Stage 2 — Full extraction pass
- [x] `scripts/extract_all.py` written: resumable per-domain cache
      (`data/extract_cache/*.json`), --workers/--limit/--rebuild; writes `data/kb.db`
      → `profiles` (rebuilt from cache; cache is source of truth)
- [x] **Full run DONE 2026-11-07** on local vLLM (qwen3-30b-a3b-awq, GPU 0, 12 workers,
      interval 0): 13,523/13,523 pages in 3h10m (1.19/s), 13,519 ok · 4 parse_error
      (0.03%, ignored) · 0 api_error. ~22M tokens, all local/free.
      `data/kb.db` rebuilt: 13,521 profiles, **13,199 is_useful (97.6%)** — higher than
      A/B's 82% because A/B sample was garbage-enriched and Stage 0 had already
      quarantined hard garbage. LLM caught the non-EN spam Stage 0 regexes miss
      (sourdoughandco.com = Spanish casino replacement, back2thegrind.com = Chinese
      betting — both correctly flagged). Useful fill rates: intro 99.98%, intents
      99.97%, keywords 99.98%, short_desc 94.2%, location 77.0%, hours 24.3%,
      price 27.7%. Confidence: 97.8% at 0.9 (minimal-profile rule rarely fires —
      accepted at gate). page_type: business 8,545 · organization 4,545 · other 46 ·
      directory 35 · chain_location 23. Garbage (320): spam 138 · other 119 · error 39.
      Note: 89/320 garbage rows still carry name/intro (LLM names the business from
      title even on spam-replaced pages) — harmless, gated by is_useful=0.
      (z.ai-era 429/RatePacer incident log superseded — local run used --interval 0.)
      Old z.ai flash cache (347 files, old prompt) parked at
      `data/extract_cache_zai_flash_oldprompt/`.

### Stage 3 — Taxonomy + facets
- [x] `scripts/normalize_taxonomy.py` written: ordered regex rules `type`+`cuisine`
      → OSM-style `osm_type`; facets table (osm_type/city/price/cuisine/feature/intent);
      QA report `taxonomy_qa.md`; adds `profiles.osm_type` via ALTER TABLE
- [x] **Run + iterated to clean state 2026-11-07.** Final classifier = two-phase:
      phase 1 `NAME_RULES` (high-precision, name+type+short_description only),
      phase 2 `RULES` (full haystack incl. services/keywords — LLM `type` is often
      generic 'business'/'organization', signal lives in other fields). Gotchas fixed:
      `er\b` matched every "-er" word (hospital 895→236 real), bare `bar` matched
      barber/barbeque (schools became bars), church pages hit `coffee`/`dining` first
      (worship now precedes restaurant in phase 2; weak tokens jesus/christ/prayer/mass
      dropped from phase 2, strong nouns live in phase 1). Result: place_of_worship 1,030
      (717 worship-named profiles: 716/717 correct, 1 legit Temple City vet),
      restaurant 4,469 · school 2,355 · cafe 795 · bar 636 · dentist 529 ·
      clinic 398 · other 158 (1.2%, genuine long-tail: casinos, Amtrak, memorials).
      Facets: intent 77,913 · feature 75,255 · cuisine 11,413 · city 6,475 (49%
      coverage — CA_CITIES list ∩ location text) · price 3,660

### Stage 4 — Embeddings + dedupe + clustering
- [x] `.venv` ready: torch 2.15+cu132 (CUDA on RTX 3090), sentence-transformers,
      sqlite-vec, scikit-learn, mcp
- [x] `scripts/embed_ab.py` written: bge-m3 vs Qwen3-Embedding-0.6B over A/B profiles,
      hit@1/MRR + encode speed → `embed_ab_report.md`
- [x] `scripts/embed_all.py` written: useful profiles → kb.db `embeddings` (resumable
      per model); near-dup pass cosine > 0.97 → `near_dups` (both directions deduped)
- [x] Run embed A/B → pick model; run embed_all; review near_dups
      - A/B (42 profiles, 10 probes): bge-m3 and qwen3-0.6b BOTH hit@1 = 10/10, MRR 1.00
        (ceiling — corpus too small to separate). Picked **bge-m3** (proven, plan default,
        1024-dim; switch later = one 5-min re-embed).
      - embed_all: 13,199 vectors in 160s (84/s), dim 1024.
      - near_dups cos>0.97: 58 pairs. Top = true mirrors (kevins/kevinnoodlehouse 0.998,
        fire.ca.gov/calfire.ca.gov 0.997) BUT several are template-similar DISTINCT
        businesses (woodsbeer.com↔cerveceriasf.com 0.997, dadscafeeastbay↔assemblekitchen
        0.991) → decision: drop nothing; near_dups copied into search.db as metadata.
- [x] HDBSCAN over vectors → clusters; QA report (residual garbage, facet candidates)
      - raw cosine HDBSCAN: 5 clusters, 73% noise, giant clusters incoherent → added
        UMAP(cosine→10d) stage to cluster.py (umap-learn installed in .venv)
      - final: 96 clusters, 27% noise; coherent tops (christian-church 874, italian/pizza
        637, mexican 610, dentist 531, specialty-coffee 392...); QA → cluster_qa.md

### Stage 5 — Hybrid search + eval
- [x] `scripts/build_search.py` written: `data/search.db` = docs + FTS5(porter unicode61)
      + facets + vector BLOBs; drops near-dup secondaries
- [x] `scripts/search.py` written: BM25 + vector → RRF(k=60); `--facet type=… city=…
      price=… intent=… feature=…`; `--facets`; `--show DOMAIN`; `--json`; `--mode`
- [x] `scripts/gen_eval.py` + `scripts/eval_search.py` written (query-by-document,
      recall@10 + MRR per mode)
- [x] Run build + eval after Stage 4; hand-check ~10 queries
      - search.db built: 13,199 docs + vectors + facets + near_dups metadata; FTS5 smoke ok
      - gen_eval (z.ai glm-5.3-flash): 60 questions, 3 styles; eval_report.md:
        **bm25 95% / vector 95% / hybrid 97% recall@10; MRR 0.85/0.75/0.85**
      - hand-check of 2 hybrid misses: both fair competition (generic queries, many
        valid answers — e.g. "college prep high school" ranks Wonderful College Prep
        Academy #1 vs target Calaveras HS); not ranking bugs → accepted

### Stage 6 — Agent door
- [x] `scripts/kb_mcp.py` written: FastMCP tools `search`/`get_profile`/`facets`;
      BM25-only fallback if vectors unavailable; compiles
- [x] Register in opencode.json after Stage 5; test from opencode
      - registered as `amenity-kb` in ~/.config/opencode/opencode.json (backup
        opencode.json.bak-amenity-kb); absolute paths + HF_HOME=/opt/vllm/models/hf
      - ported to mcp 2.x (FastMCP → MCPServer; venv has mcp 2.3.0); embedder pinned
        to CPU (single-query encode ~100ms, keeps GPUs free for training)
      - fixed: sqlite ProgrammingError (mcp 2.x runs tools in worker threads →
        check_same_thread=False on the read-only connection)
      - verified over raw stdio: initialize + tools/list + get_profile + search all OK
        (ramen san jose → 2 San Jose ramen spots top-2); opencode-side reconnection
        pending — server was killed to pick up the fix; user runs /mcps → reconnect
        amenity-kb (or restarts opencode)

## Notes / open threads
- Old effort `2026-11-07-amenity-hybrid-search` superseded by this one (Stage 0 result
  still authoritative); its tasks.md points here
- Stage 2 prompt must keep the injected-spam rule (ignore gambling/betting sections)
- `matched_places.place_id` join key still unknown — POI metadata layered later
- Git repo initialized 2026-11-08: one commit per pipeline stage (prefilter →
  extract A/B → extract full → taxonomy → embed/cluster → search/eval → MCP),
  plus research sketch, A/B evidence, eval set and these effort records.
  `data/` (DBs + caches, 375 MB) is gitignored — rebuildable from scripts.

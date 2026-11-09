# Audience tags: the solution in plain words

2026-11-08 · How we turn 13,521 mined place profiles into filterable tags like "family friendly"
*(enhanced 2026-11-09 with post-run numbers and mechanics; counts verified against `data/kb.db`)*

## The problem in one sentence

Every profile in `data/kb.db` already says *who a place is for* ("families, couples,
business diners", "family-friendly environment"), but it says it in **79,038 different
spellings across 153,168 feature/intent facet rows** — useless for filtering until it
becomes one consistent vocabulary of 17 tags.

## What the "cards" actually are

The pipeline doesn't read websites; it reads cards that an earlier step already wrote.
`scripts/extract_common.py` defines the card schema: for each place website, an LLM
produced one JSON card with 16 fields — `name`, `type`, `intents`, `features`,
`services`, `audience`, `self_introduction`, … (e.g. `intents: ["date night",
"weekend brunch"]`, `features: ["family-friendly environment", "outdoor seating"]`).
The cards live in `data/kb.db`; every list item became a row in the `facets` table
(`kind` = `feature` or `intent`, `value` = the phrase). Tag extraction mined exactly
those rows — a human instantly knows "good for kids", "kid-friendly" and "children
welcome" are the same fact; a database knows none of them are. Tags teach it.

## The big idea: one librarian, one fast assistant, three piles

Think of a library with all returned books and one librarian (the LLM). Reading every
book would take days. Instead the librarian writes a **description card per shelf**
("this shelf: places where kids are welcome — kids menus, play areas, classes for all
ages"), and a fast assistant (embedding similarity — turning text into numbers that
measure how alike two texts are) sorts everything into three piles:

1. **Obvious fit** → shelved instantly, no librarian needed.
2. **Obviously irrelevant** ("my ruby's rewards program") → discarded.
3. **Can't decide** ("family recipes" — family word, but it's about food heritage) →
   the small tray the librarian actually reads.

The librarian only reads the tray. That's the whole design: **cheap bulk sorting,
expensive judgment only where it's needed.** And it ran **twice**: once for *phrases*
(Stages 1–2) and once for *places* (Stage 3), united in Stage 4.

## The four stages (with real values from our data)

### Stage 1 — the ~3,500 repeating values: ask the librarian directly

Values seen 5+ times — 3,519 distinct phrases covering 59,427 rows (4.5% of spellings,
39% of all rows) — went to glm-5.3-flash in batches of 100. Each value got exactly one
answer: a canonical tag, a `new:<tag>` proposal, or null. The heart of it is the **null
rule** — what the prompt forbids (`tag_vocabulary.py`): services (takeout, delivery),
amenities (outdoor seating, wifi), **ownership (family-owned)**, food facts (vegetarian
options), programs, cuisine names. This exists because of the trap in our own data:

| raw value (real, with counts) | LLM answer | why |
|---|---|---|
| family-friendly (753×) | `family_friendly` | audience |
| family-friendly environment (102×) | `family_friendly` | same thing, other words |
| kid-friendly (22×) | `family_friendly` | same thing |
| family-owned (422×) | null | **ownership, not audience** — the trap |
| family dental care (21×) | null | a service name |
| meeting rooms (9×) | `business_friendly` | audience attribute |
| 21+ only (17×) | `new:adults_only` | proposal for review |

Cost: 36 calls, minutes. Two mechanical details worth knowing:

- **Echo alignment**: the model must repeat each value in its answer, and results are
  matched by value *text*, not position — LLMs miscount long lists, this makes a
  miscount harmless instead of corrupting the mapping.
- **Resumable cache**: one JSON file per batch in `tier1_cache/`; a crashed run loses
  nothing, re-runs skip finished batches.

The proposals landed in `tier1/tier1_report.md` with example values, and were reviewed
by hand — **the only human gate in the whole pipeline**. Outcome: 8 seed tags + 9
approved proposals (casual, upscale, cozy, community_focused, lively, seniors,
beginner_friendly, adults_only, lgbtq_friendly) = **17 locked tags** with definition
sentences in `tier1/approved_tags.json` (e.g. *romantic: "A romantic atmosphere for
couples and date nights: candlelit dinner, intimate ambiance, romantic setting for
two."*). 8 proposals rejected (welcoming, students, modern, kids, relaxing, all_girls,
quiet, social_atmosphere); senior_friendly merged into seniors; and one override fixed
a big miss: "date night" (1,260 rows) had been nulled → mapped to `romantic`.

### Stage 2 — the ~75,000 one-off values: the sorting room

Each of the 75,453 rare phrases (seen <5×) was embedded with bge-m3 — the model already
in kb.db — on CPU (54 min) and compared to each tag's *definition sentence* by cosine
similarity (a 0–1 "how close in meaning" score). Three zones:

- **≥ 0.65** → auto-tag. ("safe for kids playground area" → family_friendly)
- **0.55–0.65** → ambiguous tray → batched to the LLM.
- **< 0.55** → dropped as noise.

The cutoffs are not guessed: **the Stage-1 answers double as free tuning data** — every
value Stage 1 already tagged is a known right answer (396 of them). On that gold,
values belonging to their tag score median 0.595 (p90 0.703) while nulls almost never
exceed 0.602 — so 0.65 lets only ~0.6% of garbage through ("null leak" ≈ 6 wrong
auto-tags per thousand) and 0.55 keeps nearly everything real.

Run outcome: **drop 63,699 / LLM band 10,471 / auto 1,283** — the assistant confidently
discarded 84% of the tail and the librarian read 14% (105 batches, ~2.4 h). Result is
saved as a plain dictionary (`tier2/tag_map_tail.json`, `raw value → tag`): auditable,
and lookups never cost an LLM call again.

### Stage 3 — tagging the 13,199 places themselves

Stages 1+2 tag *phrases*; now we tag *places* — because a place can *be* family-friendly
without ever using the phrase; the vibe sits in its description. Each tag's definition
was embedded and compared against the 13,199 profile embeddings already in the database
— one matrix multiplication. The top 300 candidates per tag (similarity ≥ 0.35) went to
glm-5.3-flash, which read each candidate's text (`self_introduction | audience |
detailed_profile`) and answered **true/false/unsure plus a verbatim quote from the
place's own text as evidence**:

> **confidentialcoffee.com** → `work_friendly`: "The shop features complimentary Wi-Fi,
> numerous electrical outlets, a large community table for groups…"

The quote is the anti-hallucination device: a made-up verdict has no sentence to quote,
so spot-checking 20 quotes per tag (`tier3/qa_report.md`) exposes lying instantly. Known
gray zones show up honestly this way — vets/groomers under `pet_friendly` (they *serve*
pets; are they *pet friendly*?), rehab clinics under `accessible`.

~25 minutes per tag instead of 4.5 hours of LLM-calling every profile. Total: 431
calls, ~1.8 h → **2,212 confirmed (place, tag) pairs** (casual 221, community_focused
226, family_friendly 216, lgbtq_friendly 51, …).

### Stage 4 — the union, written where search already looks

Final tags per place = **Stage-3 confirmations ∪ dictionary hits** (any approved-tag
phrase from Stage 1/2 appearing on the card) — two independent paths: the dictionary
path catches explicit claims ("family-friendly environment"), the profile path catches
implicit vibes (a daycare never writes "family-friendly"; it doesn't need to). Written
as a new facet kind `audience_fit` — **14,239 rows on 7,556 of 13,521 profiles (56%)**
— which `search.py` picks up with zero code change, because facets were already a
generic filter (`--facet family_friendly=true`). Recall check: 2,172/2,172 places with
an explicit "family-friendly" value got the tag — 100%, by construction of the union.

## The economics in one line

36 + 105 + 431 = **572 LLM calls** total. The naive alternative — asking the LLM about
every place × every tag — would have been 13,521 × 17 ≈ **230,000 calls**.

## Why not the simpler-looking options

- **Regex rules** (like `normalize_taxonomy.py` uses for `type`): "family-owned" and
  "family-friendly" share the word family; rules can't tell ownership from audience.
  Also 79,000 unique spellings.
- **Just a cosine threshold on the profile text**: similarity is good at *ranking*
  (near vs far) but bad at *deciding* (is this really family friendly?). Every
  hospitality text sounds a bit "friendly". Research and practice agree: use cosine
  to shortlist, an LLM to decide.
- **Fine-tuning custom embeddings**: premature. Our own A/B (`embed_ab_report.md`)
  scored off-the-shelf bge-m3 and Qwen3-0.6B a perfect 10/10 on retrieval probes;
  there's no measured gap to close, and no labeled pairs to train on. It earns its
  place only if: (1) colloquial queries start missing in `eval_search.py`, (2) a future
  50+ tag classifier plateaus, or (3) real query logs demand ranking fixes.
  Cheaper first moves then: instruction-prefixed queries, a reranker, SetFit few-shot.

## What gets built

| artifact | what it is |
|---|---|
| `scripts/tag_vocabulary.py` | Stage 1: LLM normalization of head values, resumable cache |
| `scripts/tag_tier2.py` | Stage 2: embed tail values, three-zone mapping, threshold tuning |
| `scripts/tag_profiles.py` | Stage 3: shortlist + LLM verify with evidence quotes |
| `scripts/tag_write_facets.py` | Stage 4: union write of `audience_fit` facets |
| `tier1/approved_tags.json` | the 17 locked tags + definition sentences (the vocabulary) |
| `tier1/tag_map_head.json`, `tier2/tag_map_tail.json` | phrase → tag dictionaries (auditable, free forever) |
| `facets` kind `audience_fit` in `kb.db` | the actual tags, per profile |
| QA reports in this effort dir | proposals for review, per-tag counts, evidence spot-checks |

## The quality loop

- Stage-1 proposals reviewed by hand once (the only human gate).
- Thresholds tuned on Stage-1 answers (free gold data).
- Stage-3 spot-check: 20 evidence quotes per tag.
- ~950 profiles already carry an explicit "family-friendly" value — a ready-made
  gold set to measure final recall (100% via the union).

## The five intuitions to keep

1. **Pay for judgment by ambiguity, not by volume.** Cosine ranks well but decides
   badly; the LLM decides well but costs. Use each for what it does — that's the
   572-vs-230,000 gap.
2. **Frequency is free triage.** 3,519 phrases are 4.5% of spellings but 39% of rows —
   the librarian reads the head, the assistant sorts the tail.
3. **Yesterday's answers are today's training data.** No labeling budget existed;
   Stage 1's output became the gold that tuned Stage 2's thresholds.
4. **Nulls are a feature.** The most common answer is "not about audience" — takeout
   (283×), outdoor seating (216×). A tagger that tags everything is useless for
   filtering.
5. **Everything is a file you can open.** `tag_map_head.json`,
   `tag_map_tail.json`, `approved_tags.json`, `qa_report.md` with quotes — every
   automatic decision has a visible trail.

Where the library analogy breaks down: the assistant doesn't "read" at all — it only
knows how alike two texts are, from having seen millions during training; and the
librarian never tires but *can* confidently lie — which is exactly why the
evidence-quote rule exists.

## Bottom line

Mine what the extraction already wrote, let embeddings do the bulk sorting for pennies,
let the LLM spend its calls only on judgment calls, and write the result into the facet
table the search already understands. No fine-tuning, no new infrastructure.

# Audience tags: the solution in plain words

2026-11-08 · How we turn 13,521 mined place profiles into filterable tags like "family friendly"

## The problem in one sentence

Every profile in `data/kb.db` already says *who a place is for* ("families, couples,
business diners", "family-friendly environment"), but it says it in ~82,000 different
spellings scattered across the `features` and `intents` fields — useless for filtering
until it becomes one consistent vocabulary.

## The big idea: one librarian, one fast assistant, three piles

Think of a library with 82,000 returned books and one librarian (the LLM). Reading every
book would take days. Instead the librarian writes a **description card per shelf**
("this shelf: places where kids are welcome — kids menus, play areas, classes for all
ages"), and a fast assistant (embedding similarity — turning text into numbers that
measure how alike two texts are) sorts everything into three piles:

1. **Obvious fit** → shelved instantly, no librarian needed.
2. **Obviously irrelevant** ("my ruby's rewards program") → discarded.
3. **Can't decide** ("family recipes" — family word, but it's about food heritage) →
   the small tray the librarian actually reads.

The librarian only reads the tray. That's the whole design: **cheap bulk sorting,
expensive judgment only where it's needed.**

## The three stages (with real values from our data)

### Stage 1 — the ~3,500 repeating values: ask the librarian directly

Values seen 5+ times (1,873 feature + 1,646 intent values) cover almost half of all rows.
They go to the LLM in batches of 100, each mapped to a canonical tag, a proposed
`new:<tag>`, or null:

| raw value (real, with counts) | LLM answer | why |
|---|---|---|
| family-friendly (753×) | `family_friendly` | audience |
| family-friendly environment (102×) | `family_friendly` | same thing, other words |
| kid-friendly (22×) | `family_friendly` | same thing |
| family-owned (422×) | null | **ownership, not audience** — the trap |
| family dental care (21×) | null | a service name |
| meeting rooms (9×) | `business_friendly` | audience attribute |

Cost: ~36 API calls, minutes. Proposals for new tags land in a review file —
the "LLM invents categories outside your list" behavior becomes a feature:
each proposal comes with example values, you approve or reject once.

### Stage 2 — the ~78,000 one-off values: the sorting room

Each rare phrase gets embedded (bge-m3, the model already in `kb.db`) and compared to
the Stage-1 tag cards by cosine similarity (a 0–1 "how close in meaning" score):

- **> ~0.75** → auto-tag. ("safe for kids playground area" → family_friendly)
- **~0.55–0.75** → ambiguous tray → batched to the LLM.
- **< ~0.55** → dropped as noise.

The cutoffs are not guessed: the Stage-1 answers double as free tuning data — every
value Stage 1 already tagged is a known right answer, so we pick thresholds where the
known answers land in the right pile. Result is saved as a dictionary
(`raw value → tag`), so it's auditable and never costs LLM calls again.

### Stage 3 — tagging the 13,521 profiles themselves

Stage 1+2 tag *phrases*; now we tag *places*. Each tag's definition sentence is embedded
and compared against the 13,199 profile embeddings already in the database — one matrix
multiplication. The top ~300 candidate profiles per tag go to the LLM, which answers
with a yes/no **plus a quoted sentence from the profile as evidence** ("safe, supportive,
and family-friendly environment"). The quote is the quality check: hallucinations are
instantly visible when spot-checking.

~25 minutes per tag instead of 4.5 hours of LLM-calling every profile.

Final tags are written as a new facet kind `audience_fit` — they flow into the existing
hybrid search unchanged, so "family friendly restaurants in San Jose" works day one.

## Why not the simpler-looking options

- **Regex rules** (like `normalize_taxonomy.py` uses for `type`): "family-owned" and
  "family-friendly" share the word family; rules can't tell ownership from audience.
  Also 78,000 unique spellings.
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
| `facets` kind `audience_fit` in `kb.db` | the actual tags, per profile |
| QA reports in this effort dir | proposals for review, per-tag counts, evidence spot-checks |

## The quality loop

- Stage-1 proposals reviewed by hand once (the only human gate).
- Thresholds tuned on Stage-1 answers (free gold data).
- Stage-3 spot-check: 20 evidence quotes per tag.
- ~950 profiles already carry an explicit "family-friendly" value — a ready-made
  gold set to measure final recall.

## Bottom line

Mine what the extraction already wrote, let embeddings do the bulk sorting for pennies,
let the LLM spend its calls only on judgment calls, and write the result into the facet
table the search already understands. No fine-tuning, no new infrastructure.

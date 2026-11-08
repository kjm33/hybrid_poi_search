#!/usr/bin/env python3
"""audience-tags Stage 1 gate: apply the human verdict on Tier-1 proposals.

Edits tier1/tag_map_head.json in place:
  - approved proposals  "new:casual" → "casual"
  - merged proposals    "new:senior_friendly" → "seniors"
  - rejected proposals  "new:modern" → null
  - value overrides     "date night" → romantic (LLM null-miss, 1,260 rows), etc.
Writes tier1/approved_tags.json: {"tags": [...], "definitions": {tag: sentence}}.

Usage: .venv/bin/python scripts/tag_gate.py
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

EFFORT = Path(__file__).resolve().parents[1] / "efforts" / "2026-11-08-audience-tags"
T1 = EFFORT / "tier1"

SEED = ["family_friendly", "business_friendly", "work_friendly", "pet_friendly",
        "romantic", "groups_events", "late_night", "accessible"]

APPROVED_NEW = ["casual", "upscale", "cozy", "community_focused", "lively", "seniors",
                "beginner_friendly", "adults_only", "lgbtq_friendly"]
MERGES = {"senior_friendly": "seniors"}  # rejected as separate name, folded in
# rejected proposals (welcoming, quiet, students, modern, kids, relaxing, all_girls,
# social_atmosphere) are not listed anywhere → they become null by default

DEFINITIONS = {
    "family_friendly": "A place that welcomes families with children: kids menus, play areas, children's programs, activities for all ages, child care.",
    "business_friendly": "A place suited for business customers: meeting rooms, business lunches, corporate events, services for business travelers and colleagues.",
    "work_friendly": "A place where people can work: wifi, laptop-friendly seating, quiet space to work, remote workers and students welcome.",
    "pet_friendly": "A place that welcomes pets and dogs: dogs allowed, pet-friendly patio, pet amenities, animal-friendly policy.",
    "romantic": "A romantic atmosphere for couples and date nights: candlelit dinner, intimate ambiance, romantic setting for two.",
    "groups_events": "A place that hosts groups, parties and events: private event space, group dining, banquet rooms, party hosting, event venues.",
    "late_night": "A place open late at night with nightlife: late-night hours, nightclub, dancing, bar atmosphere after dark.",
    "accessible": "A place accessible to people with disabilities: wheelchair-accessible entrance, ADA compliance, accessible restrooms and facilities.",
    "casual": "A casual, relaxed place for everyday visits: casual dining, informal atmosphere, no dress code, everyday meals with friends.",
    "upscale": "An upscale, elegant, fine-dining experience: fine dining, refined ambiance, luxury setting, upscale cuisine and service.",
    "cozy": "A cozy, intimate, comfortable atmosphere: warm cozy ambiance, small intimate space, comfortable relaxed setting.",
    "community_focused": "A community-oriented place serving local residents: community gatherings, neighborhood events, community atmosphere.",
    "lively": "A lively, vibrant, energetic atmosphere: vibrant ambiance, bustling energy, sports-bar excitement, music-filled social scene.",
    "seniors": "A place serving seniors and elderly adults: senior living, assisted living, memory care, elder care, senior programs.",
    "beginner_friendly": "Classes and activities suitable for beginners: beginner-level instruction, newcomers without experience welcome.",
    "adults_only": "A venue restricted to adults: 21 and over, adults-only atmosphere, no children allowed.",
    "lgbtq_friendly": "A place that is LGBTQ-friendly and affirming: welcoming to LGBTQ customers, inclusive pride-friendly atmosphere.",
}

# value-level fixes (lowercase value text → tag or None), applied across both kinds
VALUE_OVERRIDES = {
    "date night": "romantic",                # biggest single miss: 1,260 rows nulled
    "date nights": "romantic",
    "romantic date night": "romantic",
    "child-friendly dentist": "family_friendly",
    "pickup lunch": None,                    # misfiled under seniors proposal
    "elderly care": "seniors",               # was new:senior_friendly — merge target
}


def main() -> None:
    path = T1 / "tag_map_head.json"
    mapping = json.loads(path.read_text())
    tags = SEED + APPROVED_NEW

    def norm(tag: str | None) -> str | None:
        if tag is None:
            return None
        if tag.startswith("new:"):
            t = tag[4:]
            if t in APPROVED_NEW:
                return t
            return MERGES.get(t)  # None for rejected
        return tag if tag in tags else None

    n_over = 0
    for key, tag in mapping.items():
        value = key.split("|", 1)[1]
        if value.lower() in VALUE_OVERRIDES:
            new = VALUE_OVERRIDES[value.lower()]
            n_over += int(new != tag)
            mapping[key] = new
        else:
            mapping[key] = norm(tag)
    path.write_text(json.dumps(mapping, ensure_ascii=False, indent=1))

    cov = Counter(t for t in mapping.values() if t)
    print(f"overrides applied: {n_over}")
    print(f"tags: {len(tags)} | values mapped to a tag: {sum(cov.values())} / {len(mapping)}")
    for t, c in cov.most_common():
        print(f"  {t:twenty}" if False else f"  {t:<20} {c}")
    (T1 / "approved_tags.json").write_text(
        json.dumps({"tags": tags, "definitions": DEFINITIONS}, ensure_ascii=False, indent=1))
    print(f"wrote {T1 / 'approved_tags.json'}")


if __name__ == "__main__":
    main()

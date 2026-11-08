"""Shared prompt + JSON parsing/validation for amenity profile extraction.

Used by both the A/B test (extract_ab.py) and the full run (extract_all.py).
"""
from __future__ import annotations

import json
import re

MAX_BODY_CHARS = 12000  # covers 99.7% of pages; ~3k tokens

REQUIRED_KEYS = [
    "name", "type", "cuisine_or_specialty", "location", "short_description",
    "detailed_profile", "self_introduction", "intents", "features", "services",
    "audience", "price_level", "opening_hours", "keywords", "page_type",
    "is_useful", "confidence",
]
LIST_KEYS = {"intents", "features", "services", "keywords"}
ENUM_PRICE = {"budget", "moderate", "upscale", "luxury"}
ENUM_PAGE_TYPE = {
    "business", "organization", "chain_location", "directory_listing",
    "blog_or_news", "spam", "error", "other",
}

SYSTEM_PROMPT = """You build structured English search profiles for local amenities (restaurants, cafes, bars, churches, clinics, dentists, schools, shops, hotels, ...) in California, USA, from cleaned webpage text. Your output feeds a hybrid keyword + semantic search index.

Rules:
- Output JSON only. Ground every fact in the provided text; never invent details (menus, services, hours) that are not stated. If the body contains no concrete information about the amenity beyond its identity (e.g., only legal, privacy, or accessibility boilerplate), keep is_useful=true but return a MINIMAL profile: infer only name and type from the domain and title, write a short generic self_introduction (2 sentences, no specific claims about menu, services, or hours), set every other specific field to null/[], and set confidence to 0.3 or lower.
- Choose the most specific page_type: "business" (independent business), "organization" (non-profit, school, church, government), "chain_location" (branch/franchise of a chain), "directory_listing" (page listing many other businesses), "personal" (personal page/blog), "other".
1. Return ONLY a single JSON object. No markdown fences, no commentary before or after.
2. Ground every fact in the page text. If information is missing, use null (or [] for list fields). Never invent facts.
3. Write all generated text fields in natural English. If the page is in another language, translate.
4. IGNORE injected spam sections (gambling, betting, casino links, pharma, unrelated SEO articles). Extract only real amenity content. If the page has no real amenity content, set is_useful=false and page_type to "spam", "error" or "other" as appropriate.
5. self_introduction: the amenity introduces itself in first person ("We are ..."), 2-4 sentences, naturally including terms real users would search for. Informative, not salesy, no keyword stuffing.
6. intents: concrete search intents / use cases the place satisfies, e.g. "date night", "gluten-free bakery", "weekend brunch", "emergency dentist", "kid-friendly dinner", "catering for events".
7. keywords: lowercase search terms including synonyms and colloquialisms users might type ("taqueria", "bone broth ramen", "sourdough pizza").
8. price_level only if the text clearly signals it (menu prices, "$$", "fine dining"); else null.

JSON schema (all keys required, use null/[] when unknown):
{"name": str|null, "type": str|null, "cuisine_or_specialty": str|null, "location": str|null,
 "short_description": str|null, "detailed_profile": str|null, "self_introduction": str|null,
 "intents": [str], "features": [str], "services": [str], "audience": str|null,
 "price_level": "budget"|"moderate"|"upscale"|"luxury"|null, "opening_hours": str|null,
 "keywords": [str],
 "page_type": "business"|"organization"|"chain_location"|"directory_listing"|"blog_or_news"|"spam"|"error"|"other",
 "is_useful": bool, "confidence": float}"""


def build_user_message(domain: str, title: str, description: str, body: str) -> str:
    body = (body or "")[:MAX_BODY_CHARS]
    return (
        f"domain: {domain}\n"
        f"page title: {title or '(none)'}\n"
        f"meta description: {description or '(none)'}\n\n"
        f"page content:\n{body}"
    )


def parse_profile(raw: str) -> tuple[dict | None, str]:
    """Extract and validate the JSON profile from a model response.

    Returns (profile, error). profile is None when unusable; error is "" on success
    or a short reason code: invalid_json / missing_keys / bad_types.
    """
    if not raw or not raw.strip():
        return None, "invalid_json"
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\s*|\s*```$", "", text, flags=re.IGNORECASE)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None, "invalid_json"
    try:
        profile = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None, "invalid_json"
    if not isinstance(profile, dict):
        return None, "invalid_json"

    missing = [k for k in REQUIRED_KEYS if k not in profile]
    if missing:
        return profile, f"missing_keys:{','.join(missing[:3])}"

    # coerce/validate types (keep going after first fixable issue)
    issues = []
    for k in LIST_KEYS:
        v = profile.get(k)
        if v is None:
            profile[k] = []
        elif isinstance(v, str):
            profile[k] = [s.strip() for s in v.split(",") if s.strip()]
        elif not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            profile[k] = [str(x) for x in v] if isinstance(v, list) else []
            issues.append(k)
    for k in ("is_useful",):
        if not isinstance(profile.get(k), bool):
            profile[k] = str(profile.get(k)).lower() in ("true", "yes", "1")
            issues.append(k)
    if profile.get("price_level") not in ENUM_PRICE:
        profile["price_level"] = None if profile.get("price_level") in (None, "", "unknown") else profile["price_level"]
    if profile.get("page_type") not in ENUM_PAGE_TYPE:
        issues.append("page_type")
        profile["page_type"] = "other"
    if not isinstance(profile.get("confidence"), (int, float)):
        profile["confidence"] = 0.5
        issues.append("confidence")
    return profile, ("bad_types:" + ",".join(sorted(set(issues))) if issues else "")

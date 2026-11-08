#!/usr/bin/env python3
"""Stage 3: normalize free-text LLM `type` → controlled OSM-style vocabulary,
build facet dictionary table. Writes kb.db: profiles.osm_type + facets table,
and a QA report to the effort dir.

Mapping is rule-based (ordered, first match wins). Unmapped types are reported
so the rules can be extended; they get osm_type='other'.

Usage: python3 scripts/normalize_taxonomy.py
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "kb.db"
EFFORT = ROOT / "efforts" / "2026-11-07-amenity-knowledge-base"

# Phase 1 — high-precision rules applied to name + type + short_description only.
# Ordered, first match wins. Strong nouns only; weak tokens (coffee, dinner…)
# belong to phase 2 or nowhere.
NAME_RULES: list[tuple[str, str]] = [
    (r"animal hospital|veterinar|vet clinic|animal shelter", "veterinary"),
    (r"church|mosque|synagogue|parish|ministry|cathedral|diocese|gurdwara|temple|"
     r"masjid|chapel|tabernacle", "place_of_worship"),
    (r"assisted living|senior living|memory care|nursing home|skilled nursing|"
     r"rehabilitation (center|facility)|hospice|retirement community", "social_facility"),
    (r"hospital|medical center|urgent care|emergency room|trauma center|health system|"
     r"healthcare center", "hospital"),
    (r"dentist|orthodontist|endodontist|oral surgery|dental", "dentist"),
    (r"school|academy|preschool|pre.?school|kindergarten|day ?care|child ?care|"
     r"montessori|learning center|tutoring|education center", "school"),
    (r"college|university|institute of technology", "college"),
    (r"librar", "library"),
    (r"bank|credit.?union", "bank"),
    (r"gas station|\bfuel\b|petrol", "fuel"),
    (r"car wash|auto detail", "car_wash"),
    (r"pharmac|drug ?store", "pharmacy"),
    (r"hotel|motel|resort|bed (and|&) breakfast|hostel|guest house|lodge|inn\b|"
     r"vacation rental", "hotel"),
    (r"airport", "airport"),
    (r"funeral|cemetery|cremator", "funeral_home"),
    (r"self.?storage|storage unit", "storage"),
    (r"laundry|dry clean", "laundry"),
    (r"restaurant|bistro|diner|grill|eatery|steakhouse|seafood|sushi|ramen|noodle|"
     r"taquer|pizzer|bbq|barbe?cue", "restaurant"),
    (r"\bbar\b|\bpub\b|tavern|brewery|taproom|nightclub|cocktail|speakeasy|saloon", "bar"),
    (r"cafe|café|coffee|espresso|tea house|bubble tea|boba|juice|smoothie", "cafe"),
    (r"bakery|pastry|donut|doughnut|croissant|cake shop", "bakery"),
    (r"ice cream|gelato|frozen yogurt", "ice_cream"),
    (r"\bgym\b|fitness|crossfit|yoga|pilates|martial arts?|boxing|climbing|dance studio", "fitness_centre"),
    (r"theater|theatre|cinema|movie|performing arts|concert hall|opera|comedy club", "theatre"),
    (r"museum|gallery|aquarium|\bzoo\b|historic|landmark|heritage", "museum"),
]

# Phase 2 — full-haystack rules (type + cuisine + name + short_description +
# services + keywords). Ordered, first match wins. Worship before restaurant so
# church pages with "coffee hour"/"fellowship dinner" text stay worship.
RULES: list[tuple[str, str]] = [
    (r"assisted living|senior living|nursing|memory care|rehabilitation|skilled nursing|"
     r"retirement community|hospice", "social_facility"),
    (r"airport", "airport"),
    (r"funeral|cemetery|cremator", "funeral_home"),
    (r"self.?storage|storage unit", "storage"),
    (r"laundry|dry clean", "laundry"),
    (r"church|temple|mosque|synagogue|worship|parish|ministry|fellowship|chapel|"
     r"cathedral|buddhist|hindu|gurdwara|diocese|islamic", "place_of_worship"),
    (r"sushi|ramen|noodle|taquer|taco|burrito|pizzer|pizza|steakhouse|seafood|"
     r"bbq|barbe?cue|burger|hot ?pot|korean|thai|vietnamese|japanese|chinese|italian|"
     r"indian|mexican|greek|french|fusion|vegan|vegetarian|bistro|diner|grill|eatery|"
     r"restaurant|dining|catering|food truck", "restaurant"),
    (r"fast ?food|quick serve|drive.?thru|take ?out|takeaway|deli|sandwich", "fast_food"),
    (r"coffee|cafe|café|espresso|tea house|bubble tea|boba|juice|smoothie", "cafe"),
    (r"bakery|pastry|croissant|donut|doughnut|cake shop", "bakery"),
    (r"ice cream|gelato|frozen yogurt|yogurt", "ice_cream"),
    (r"brewery|taproom|tavern|cocktail|wine bar|speakeasy|\bpub\b|\bbar\b|lounge|"
     r"nightclub|karaoke|sports bar|drinks?\b", "bar"),
    (r"market|grocery|supermarket|butcher|seafood market|farmers market|marketplace", "marketplace"),
    (r"schoo|academy|education|montessori|preschool|pre.?school|daycare|child ?care|"
     r"kindergarten|learning center|tutoring|charter", "school"),
    (r"college|university|institute of higher", "college"),
    (r"librar", "library"),
    (r"dentist|orthodontist|endodontist|oral surgery", "dentist"),
    (r"animal hospital|veterinar|vet clinic|animal shelter|pet clinic", "veterinary"),
    (r"hospital|emergency room|health system|trauma center", "hospital"),
    (r"clinic|medical|health|urgent care|family practice|pediatric|physician|doctor|"
     r"chiropract|acupuncture|physical therapy|therapy|behavioral|mental health|"
     r"counsel|psycholog|psychiatr|dialysis|imaging|lab\b|surgeo|plastic", "clinic"),
    (r"pharmac|drug ?store", "pharmacy"),
    (r"bank|credit.?union", "bank"),
    (r"atm\b", "atm"),
    (r"gas station|fuel|petrol", "fuel"),
    (r"ev charging|charging station", "charging_station"),
    (r"car wash|auto detail", "car_wash"),
    (r"auto repair|mechanic|body shop|tire|oil change|smog", "car_repair"),
    (r"parking|garage|park ?structure", "parking"),
    (r"gym|fitness|crossfit|yoga|pilates|martial art|boxing|climbing|dance studio|"
     r"aerobics|training studio", "fitness_centre"),
    (r"pool|swim", "swimming_pool"),
    (r"spa|sauna|massage|salon|barber|hair|nail|beauty|waxing|eyelash|tattoo|estheti",
     "beauty_salon"),
    (r"theater|theatre|cinema|movie|performing arts|concert hall|opera|comedy club", "theatre"),
    (r"cowork|co.?working|office space", "coworking_space"),
    (r"community center|senior center|youth center|cultural center|event venue|"
     r"event space|banquet|meeting hall|recreation center", "community_centre"),
    (r"hotel|motel|inn\b|lodge|resort|bed & breakfast|bed and breakfast|hostel|"
     r"vacation rental|guest house", "hotel"),
    (r"park\b|garden|playground|beach|trail|recreation area|campground|camping|golf|"
     r"marina|lake|nature", "recreation_area"),
    (r"plumbing|electr(?:ic|ician)|roofing|landscap|construction|contractor|hvac|"
     r"handyman|pest control|moving|cleaning|locksmith|repair service|home service|"
     r"remodel|painting|solar|insulation|garage door|concrete|fence|flooring|"
     r"property management|real ?estate|real estate|insurance|law|legal|attorney|"
     r"accounting|tax service|financial|consulting|marketing|agency|notary", "service_business"),
    (r"shop|store|retail|boutique|thrift|book ?store|hardware|clothing|furniture|"
     r"electronics|pet store|florist|gift shop|jewel|sporting goods|toy|art supply|"
     r"music store|wine shop|liquor|smoke shop|dispensary|cannabis|cbd", "shop"),
    (r"nonprofit|non.?profit|charity|foundation|association|advocacy|ngo\b", "nonprofit"),
    (r"government|city hall|town ?hall|department of|courthouse|dmv\b|"
     r"library branch|civic|public utility|utility district|water district|"
     r"school district", "public_facility"),
    (r"youth (club|center|organization)|boys .?girls club", "community_centre"),
    (r"company|corporation|platform|software|saas|technolog|startup|b2b|holding", "company"),
    (r"museum|gallery|exhibit|aquarium|zoo|botanical|historic|landmark|heritage", "museum"),
    (r"directory|listing|store finder|locator|portal|review site|guide", "directory_listing"),
    (r"blog|news|magazine|media|podcast|radio", "media"),
]

# facet kinds derived from profile fields
FACET_FIELDS = {
    "cuisine": "cuisine_or_specialty",
    "feature": None,   # from features[] list
    "intent": None,    # from intents[] list
}


def osm_type_of(hay: str, name_hay: str = "") -> tuple[str, bool]:
    """Two-phase: NAME_RULES over name+type+short_description (high precision),
    then RULES over the full haystack (recall)."""
    if name_hay.strip():
        for pat, val in NAME_RULES:
            if re.search(pat, name_hay.lower()):
                return val, True
    hay = (hay or "").lower()
    if not hay.strip():
        return "unknown", False
    for pat, val in RULES:
        if re.search(pat, hay):
            return val, True
    return "other", False


CA_CITIES = [
    "Alameda", "Alhambra", "Aliso Viejo", "Anaheim", "Antioch", "Bakersfield",
    "Berkeley", "Beverly Hills", "Burbank", "Camarillo", "Carlsbad", "Chico",
    "Chula Vista", "Citrus Heights", "Clovis", "Concord", "Costa Mesa",
    "Culver City", "Daly City", "Davis", "Downey", "El Monte", "Elk Grove",
    "Escondido", "Folsom", "Fremont", "Fresno", "Fullerton", "Garden Grove",
    "Glendale", "Hayward", "Huntington Beach", "Inglewood", "Irvine", "Laguna Beach",
    "Lake Forest", "Lancaster", "Livermore", "Long Beach", "Los Angeles",
    "Madera", "Malibu", "Milpitas", "Modesto", "Monterey", "Moreno Valley",
    "Mountain View", "Napa", "Newport Beach", "Norwalk", "Novato", "Oakland",
    "Oceanside", "Ontario", "Orange", "Oxnard", "Palo Alto", "Palmdale",
    "Palm Springs", "Pasadena", "Petaluma", "Pleasanton", "Pomona", "Rancho Cucamonga",
    "Redding", "Redwood City", "Riverside", "Roseville", "Sacramento", "Salinas",
    "San Bernardino", "San Clemente", "San Diego", "San Francisco", "San Jose",
    "San Leandro", "San Mateo", "Santa Ana", "Santa Barbara", "Santa Clarita",
    "Santa Cruz", "Santa Maria", "Santa Monica", "Santa Rosa", "Santee",
    "Simi Valley", "South Gate", "Stockton", "Sunnyvale", "Thousand Oaks",
    "Torrance", "Tracy", "Vacaville", "Vallejo", "Victorville", "Vista",
    "Walnut Creek", "West Covina", "West Sacramento", "Whittier", "Woodland",
]
CA_CITIES = sorted({c.strip() for c in CA_CITIES})


def city_of(location: str) -> str:
    if not location:
        return ""
    for c in CA_CITIES:
        if re.search(rf"\b{re.escape(c)}\b", location, re.IGNORECASE):
            return c
    return ""


def main() -> None:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cols = {r[1] for r in con.execute("PRAGMA table_info(profiles)")}
    if "osm_type" not in cols:
        con.execute("ALTER TABLE profiles ADD COLUMN osm_type TEXT")
    con.executescript("""
        CREATE TABLE IF NOT EXISTS facets (
            domain TEXT, kind TEXT, value TEXT,
            PRIMARY KEY (domain, kind, value)
        ) WITHOUT ROWID;
        CREATE INDEX IF NOT EXISTS idx_facets_kind_value ON facets(kind, value);
    """)
    rows = con.execute("SELECT domain, type, cuisine_or_specialty, location, price_level,"
                       " intents, features, name, short_description, services, keywords"
                       " FROM profiles WHERE is_useful=1").fetchall()
    print(f"useful profiles: {len(rows)}")

    mapped: Counter = Counter()
    unmapped: Counter = Counter()
    facet_counts: Counter = Counter()
    con.execute("DELETE FROM facets")

    for r in rows:
        # richer haystack: LLM `type` is often generic ('business'/'organization');
        # the real signal sits in name / services / keywords / short_description
        def _txt(col: str) -> str:
            v = r[col] or ""
            if v.startswith("["):
                try:
                    v = " ".join(json.loads(v))
                except json.JSONDecodeError:
                    pass
            return v
        hay = " ".join(_txt(c) for c in
                       ("type", "cuisine_or_specialty", "name", "short_description",
                        "services", "keywords"))
        name_hay = " ".join(_txt(c) for c in ("name", "type", "short_description"))
        osm_t, hit = osm_type_of(hay, name_hay)
        mapped[osm_t] += 1
        if not hit and (r["type"] or "").strip():
            unmapped[(r["type"] or "").strip().lower()] += 1
        con.execute("UPDATE profiles SET osm_type=? WHERE domain=?", (osm_t, r["domain"]))

        fac = [("osm_type", osm_t)]
        if r["price_level"]:
            fac.append(("price", r["price_level"]))
        city = city_of(r["location"] or "")
        if city:
            fac.append(("city", city))
        if r["cuisine_or_specialty"]:
            for c in re.split(r"[/,]", r["cuisine_or_specialty"])[:3]:
                c = c.strip().lower()
                if 2 < len(c) < 40:
                    fac.append(("cuisine", c))
        for kind, col in (("feature", "features"), ("intent", "intents")):
            for v in json.loads(r[col] or "[]")[:15]:
                v = v.strip().lower()
                if 2 < len(v) < 60:
                    fac.append((kind, v))
        for kind, v in fac:
            con.execute("INSERT OR IGNORE INTO facets VALUES (?,?,?)", (r["domain"], kind, v))
            facet_counts[kind] += 1

    con.execute("CREATE INDEX IF NOT EXISTS idx_prof_osm_type ON profiles(osm_type)")
    con.commit()

    top_unmapped = unmapped.most_common(30)
    lines = [f"# Taxonomy normalization QA ({len(rows)} useful profiles)", "",
             "## osm_type distribution", "", "| osm_type | count |", "|---|---|"]
    lines += [f"| {t} | {n} |" for t, n in mapped.most_common()]
    lines += ["", "## facet rows by kind", ""]
    lines += [f"- {k}: {v}" for k, v in facet_counts.most_common()]
    lines += ["", f"## unmapped types ({sum(unmapped.values())} profiles → 'other')", ""]
    lines += [f"- `{t}` ×{n}" for t, n in top_unmapped]
    city_n = con.execute("SELECT COUNT(*) FROM facets WHERE kind='city'").fetchone()[0]
    lines += ["", "## sample city facet coverage", "",
              f"- city facet filled: {city_n}",
              f"- total useful: {len(rows)}"]
    out = EFFORT / "taxonomy_qa.md"
    out.write_text("\n".join(lines))
    con.close()
    print("\n".join(lines[:40]))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()

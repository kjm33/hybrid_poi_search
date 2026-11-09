# Audience-fit tag categories

The 17 locked tags from the Stage-1 gate (8 seed + 9 approved), with their
definitions from tier1/approved_tags.json and live counts from data/kb.db
(facets table, kind='audience_fit'). Total: 14,239 tag rows on 7,556 of
13,521 profiles (56% of places carry at least one tag).

| # | Tag | Places | Definition |
|---|-----|--------|------------|
| 1 | groups_events | 3,046 | A place that hosts groups, parties and events: private event space, group dining, banquet rooms, party hosting, event venues. |
| 2 | family_friendly | 2,865 | A place that welcomes families with children: kids menus, play areas, children's programs, activities for all ages, child care. |
| 3 | romantic | 2,363 | A romantic atmosphere for couples and date nights: candlelit dinner, intimate ambiance, romantic setting for two. |
| 4 | casual | 1,565 | A casual, relaxed place for everyday visits: casual dining, informal atmosphere, no dress code, everyday meals with friends. |
| 5 | community_focused | 784 | A community-oriented place serving local residents: community gatherings, neighborhood events, community atmosphere. |
| 6 | late_night | 587 | A place open late at night with nightlife: late-night hours, nightclub, dancing, bar atmosphere after dark. |
| 7 | cozy | 451 | A cozy, intimate, comfortable atmosphere: warm cozy ambiance, small intimate space, comfortable relaxed setting. |
| 8 | business_friendly | 447 | A place suited for business customers: meeting rooms, business lunches, corporate events, services for business travelers and colleagues. |
| 9 | lively | 361 | A lively, vibrant, energetic atmosphere: vibrant ambiance, bustling energy, sports-bar excitement, music-filled social scene. |
| 10 | pet_friendly | 359 | A place that welcomes pets and dogs: dogs allowed, pet-friendly patio, pet amenities, animal-friendly policy. |
| 11 | upscale | 322 | An upscale, elegant, fine-dining experience: fine dining, refined ambiance, luxury setting, upscale cuisine and service. |
| 12 | beginner_friendly | 264 | Classes and activities suitable for beginners: beginner-level instruction, newcomers without experience welcome. |
| 13 | seniors | 231 | A place serving seniors and elderly adults: senior living, assisted living, memory care, elder care, senior programs. |
| 14 | work_friendly | 183 | A place where people can work: wifi, laptop-friendly seating, quiet space to work, remote workers and students welcome. |
| 15 | adults_only | 170 | A venue restricted to adults: 21 and over, adults-only atmosphere, no children allowed. |
| 16 | accessible | 146 | A place accessible to people with disabilities: wheelchair-accessible entrance, ADA compliance, accessible restrooms and facilities. |
| 17 | lgbtq_friendly | 95 | A place that is LGBTQ-friendly and affirming: welcoming to LGBTQ customers, inclusive pride-friendly atmosphere. |

Notes:
- senior_friendly was merged into seniors at the gate; "date night" values
  map to romantic (override, 1,260 rows).
- Rejected candidates and merge history: see tier1/tier1_report.md.
- Value-to-tag mappings: tier1/tag_map_head.json, tier2/tag_map_tail.json.

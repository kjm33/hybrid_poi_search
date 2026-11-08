# Vector shrink eval — int8 / truncation / PCA

Model `arctic-s` · 60 questions · 13,199 docs · ranking math identical to on-device int8 scoring (per-vector absmax scale).

| variant | dim | B/vec (int8 storage) | total MB | vector R@10 | vector MRR | hybrid R@10 | hybrid MRR | Δ hybrid recall |
|---|---|---|---|---|---|---|---|---|
| float32 (baseline) | 384 | 384 | 5.1 | 95% | 0.82 | 95% | 0.87 | +0pp |
| int8 docs (float query) | 384 | 384 | 5.1 | 95% | 0.83 | 95% | 0.87 | +0pp |
| int8 docs + int8 query | 384 | 384 | 5.1 | 95% | 0.82 | 95% | 0.87 | +0pp |
| trunc-256 (naive MRL) | 256 | 256 | 3.4 | 95% | 0.78 | 95% | 0.87 | +0pp |
| trunc-128 (naive MRL) | 128 | 128 | 1.7 | 90% | 0.73 | 95% | 0.81 | +0pp |
| trunc-64 (naive MRL) | 64 | 64 | 0.8 | 77% | 0.68 | 97% | 0.77 | +2pp |
| pca-128 (evr 76%) | 128 | 128 | 1.7 | 93% | 0.78 | 97% | 0.85 | +2pp |
| pca-64 (evr 58%) | 64 | 64 | 0.8 | 92% | 0.61 | 95% | 0.83 | +0pp |

## float32 (baseline) — hybrid misses (3)
- best place for a date night dinner in San Francisco?
- fresh mexican tacos burritos
- college prep high school

## int8 docs (float query) — hybrid misses (3)
- best place for a date night dinner in San Francisco?
- fresh mexican tacos burritos
- college prep high school

## int8 docs + int8 query — hybrid misses (3)
- best place for a date night dinner in San Francisco?
- fresh mexican tacos burritos
- college prep high school

## trunc-256 (naive MRL) — hybrid misses (3)
- best place for a date night dinner in San Francisco?
- fresh mexican tacos burritos
- college prep high school

## trunc-128 (naive MRL) — hybrid misses (3)
- best place for a date night dinner in San Francisco?
- fresh mexican tacos burritos
- college prep high school

## trunc-64 (naive MRL) — hybrid misses (2)
- best place for a date night dinner in San Francisco?
- college prep high school

## pca-128 (evr 76%) — hybrid misses (2)
- fresh mexican tacos burritos
- college prep high school

## pca-64 (evr 58%) — hybrid misses (3)
- best place for a date night dinner in San Francisco?
- fresh mexican tacos burritos
- college prep high school
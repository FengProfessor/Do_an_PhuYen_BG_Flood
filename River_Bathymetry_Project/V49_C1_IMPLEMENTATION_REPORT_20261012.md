# V49-C.1 implementation report — fixed-water evidence audit

Date: 2026-10-12

## Outcome

V49-C.1 cross-checked every V49-C water object against current official Geofabrik/OpenStreetMap hydrography, JRC Global Surface Water evidence, and the V49-B/V49-D hydrographic topology before any V49-E terrain modification.

The gate is deliberately non-promoting: C.1 can keep or revoke a V49-D authorization, but it can never authorize a reach that V49-D rejected. C.1 modifies zero DEM pixels.

## Official source evidence

Downloaded source bundle: `D:\VTP\V49_C1_sources_20261012`

- JRC Global Surface Water v1.5 / 2024 tile `100E_20N`: occurrence, recurrence, seasonality, transitions.
- Geofabrik Vietnam OpenStreetMap PBF snapshot dated 2026-10-11 plus official MD5 sidecar.
- Geofabrik MD5 expected/actual: `b60a6365bffe82cd391e2b6a3bc94e78` / `b60a6365bffe82cd391e2b6a3bc94e78` — match.

JRC interpretation is intentionally conservative. Occurrence, recurrence and transitions are treated as the long-term 1984–2024 aggregate evidence. The downloaded `seasonality_..._2024` layer is recent-year context and is not described as a 1984–2024 aggregate. Lack of JRC detection alone never proves that a river does not exist; narrow or obscured channels require OSM/topology corroboration.

## Object-level audit

Water objects audited: **81**.

- `CONFIRMED_PERSISTENT`: **17**
- `SEASONAL_DYNAMIC`: **6**
- `CONFLICT_REVIEW_REQUIRED`: **16**
- `INSUFFICIENT_EVIDENCE`: **42**

Current Geofabrik evidence parsed inside the domain:

- waterway features: **284**
- water polygons: **82**

The explicit review queue contains **58** objects: every conflict or insufficient-evidence object. All queue rows block V49-E automatic carving until reviewed.

Priority distribution:

- Priority 1: **7** — V49-C `RIVER_STREAM` conflicts with a strongly overlapping current OSM lake/reservoir polygon.
- Priority 2: **9** — other evidence conflicts requiring manual classification/tidal treatment.
- Priority 3: **10** — insufficient evidence on a channel-class or graph-associated object.
- Priority 4: **32** — remaining classification/persistence evidence gaps.

## High-priority classification conflicts

Seven objects previously classified as `RIVER_STREAM` strongly overlap current OSM standing water and therefore stay out of automatic channel carving:

| Object | Current OSM evidence | Polygon overlap | Dam/weir evidence |
|---|---|---:|---:|
| `W20_0078` | Hồ Hoa Sơn — lake | 99.93% | 704.38 m |
| `W20_0020` | Hồ Suối Vực — reservoir | 99.71% | 0.00 m |
| `W20_0012` | Hồ Phú Xuân — reservoir | 99.46% | 456.37 m |
| `W20_0014` | Hồ Đồng Tròn — reservoir | 98.68% | 269.00 m |
| `W20_0064` | Hồ Hóc Răm — reservoir | 98.53% | 148.25 m |
| `W20_0028` | Hồ Sông Ba Hạ — reservoir | 94.66% | 0.00 m |
| `W20_0071` | Hồ Buôn Đức — reservoir | 92.84% | 0.00 m |

`W20_0009` is independently identified as Đầm Ô Loan with about 91.66% lagoon overlap and remains under tidal/lagoon treatment. `W20_0022` and `W20_0046` remain estuary/tidal objects and are excluded from fixed inland carving.

## V49-E reach authorization

V49-D had **3** candidate reaches. C.1 retains only **2**:

- `HR_41349822` — PASS. Associated objects `W20_0055` and `W20_0061` are both `CONFIRMED_PERSISTENT`; current OSM channel evidence supports Sông Hinh / Suối Ea Trol topology.
- `HR_41352752` — PASS. `W20_0079` has strong JRC recurrence/permanence plus HydroRIVERS/V49-B topology even though no current OSM channel line is present. JRC occurrence p50 = 40, recurrence p50 = 100, 2024 permanent fraction ≈ 0.7234, seasonal fraction ≈ 0.266.
- `HR_41349985` — BLOCKED. Associated `W20_0064` conflicts with current Hồ Hóc Răm reservoir evidence (~98.53% polygon overlap, ~148.25 m dam/weir evidence).

Therefore V49-E may automatically synthesize only `HR_41349822` and `HR_41352752` from the current evidence set. The other 368 graph reaches remain unchanged by automatic C.1 authorization, including the 92 reaches already held by V49-D.

## Provenance hashes

- JRC occurrence SHA-256: `ccaf03cafb1cb8e07ecd975515c715466352e0bac5f7887a0e96353147a9a813`
- JRC recurrence SHA-256: `6c5d201347b12968320dd323ca21d7bf662476d999adeae2a474fab77ac74f79`
- JRC seasonality SHA-256: `7392edea95eedce6e56b083dc52479d15a04da5b3b22bc21dd66bb93fcd57236`
- JRC transitions SHA-256: `da632c42618dd187ed927c8496395cc3e300b5fc78037f38d730a14dae737d41`
- Geofabrik PBF SHA-256: `d954e09b891079520bf13799377a9cf783cb1d9fe2745ef11864cb8d2a5b2048`

## DEM invariance

- DEM SHA-256 before C.1: `0c3c6ca6f299b00dd22a91a26c66e8c784f0e70c445412216f01efdd76504508`
- DEM SHA-256 after C.1: `0c3c6ca6f299b00dd22a91a26c66e8c784f0e70c445412216f01efdd76504508`
- Modified DEM pixels in C.1: **0**

## Outputs

Outputs are in `D:\VTP\River_Bathymetry_Project\V49_C1_20261012`:

- `V49_C1_fixed_water_evidence.gpkg`
- `V49_C1_fixed_water_audit.csv`
- `V49_C1_v49e_reach_gate.csv`
- `V49_C1_review_queue.csv`
- `V49_C1_audit.json`
- `V49_C1_validation_report.json`

Gate C.1 is accepted only when `v49_validate_fixed_water_evidence.py` reports `gate_c1_pass = true`. V49-E must consume the C.1 reach gate, not the older V49-D authorization list by itself.

# V49-C Implementation Report — Full-Domain Water-Body Classification

Date: 2026-10-12  
Phase: V49-C  
Result: **PASS**  
Scope: classify every V49-A water object and assign a safe downstream treatment. **No DEM elevation is modified in V49-C.**

## 1. What was implemented

V49-C adds a conservative, evidence-based classifier in `v49_classify_waterbodies.py` and an independent acceptance validator in `v49_validate_waterbody_classes.py`.

The classifier combines four evidence families:

1. V49-A persistent-water inventory from JRC Global Surface Water.
2. V49-B directed HydroRIVERS-based hydrographic graph.
3. Historical OpenStreetMap waterway snapshot at `2021-11-25T00:00:00Z`.
4. The aligned raw ESA WorldCover 2021 class raster, using class 80 as open water and class 90 as herbaceous wetland evidence.

No single source is treated as ground truth. The rules deliberately prefer `UNKNOWN_REVIEW_REQUIRED` over a destructive false-positive classification when evidence is incomplete or conflicting.

## 2. Historical OSM evidence

The preserved local snapshot under `D:\VTP\V46_inputs\osm_historical_20211125` is valid and non-empty. The classifier parsed and deduplicated:

- 99 unique waterways total;
- 59 `waterway=river`;
- 32 `waterway=stream`;
- 8 `waterway=canal`.

Named evidence includes Sông Kỷ Lộ, Sông Đà Rằng, Sông Bàn Thạch, Sông Bánh Lái, and historical river centerlines named Hồ Sông Hinh.

No fresh OSM download was required for Gate C. The local historical snapshot is explicitly recorded in the audit and copied by manifest provenance into the V49-C output directory.

## 3. Conservative decision rules

The implemented precedence is:

1. V49-A ocean-connected core -> `OCEAN`.
2. Coastal water with independent channel/graph support -> `ESTUARY_TIDAL_RIVER`.
3. Strong wetland land-cover with weak channel evidence -> `WETLAND_FLOODPLAIN_WATER`.
4. Broad inland persistent water with lake/reservoir semantics or sparse through-flow -> `LAKE_RESERVOIR`.
5. Direct dominant OSM canal evidence plus compatible linear/small geometry -> `CANAL`.
6. OSM-only low-confidence candidates without HydroRIVERS/V49-B support -> `UNKNOWN_REVIEW_REQUIRED`.
7. Mixed wetland/channel objects -> `UNKNOWN_REVIEW_REQUIRED`.
8. Strong natural line/graph support plus compatible morphology -> `RIVER_STREAM`.
9. All unresolved cases -> `UNKNOWN_REVIEW_REQUIRED`.

The safety rule is strict: `UNKNOWN_REVIEW_REQUIRED` always maps to `NO_AUTOMATIC_CARVING`.

## 4. Classification result

All **81/81** V49-A objects received a final class, confidence, evidence summary, review flag, treatment code and treatment rule.

| Final class | Objects | Area (km2) | V49 treatment |
|---|---:|---:|---|
| OCEAN | 1 | 764.3754 | External bathymetry / marine boundary |
| ESTUARY_TIDAL_RIVER | 3 | 49.5567 | Tidal river geometry + marine boundary |
| LAKE_RESERVOIR | 1 | 42.7806 | Stage-area-volume / available bathymetry |
| RIVER_STREAM | 33 | 12.2301 | Reach-scale bathymetry only |
| WETLAND_FLOODPLAIN_WATER | 1 | 0.0837 | Preserve storage; no river trench |
| UNKNOWN_REVIEW_REQUIRED | 42 | 9.2061 | No automatic carving |
| CANAL | 0 | 0.0000 | No object met the independent-evidence threshold |

The absence of an accepted `CANAL` object is intentional. Although the historical OSM snapshot contains eight canal ways, none corresponded strongly enough to a qualifying V49-A object to justify an automatic engineered-channel classification. Legacy canal candidates therefore remain unpromoted unless later evidence verifies geometry and hydraulic function.

## 5. Key case decisions

- `W20_0059` — **LAKE_RESERVOIR / HIGH**. Area 42.7806 km2, approximately 37.2 km inland, WorldCover open-water fraction 0.645, broad storage geometry, and historical name evidence `Hồ Sông Hinh`. River centerlines crossing the object are treated as through-flow evidence, not as proof that the full reservoir polygon is a river trench.
- `W20_0022` — **ESTUARY_TIDAL_RIVER / HIGH**. Area 21.1887 km2, 30 m from ocean, strong V49-B/HydroRIVERS graph support and Sông Đà Rằng historical OSM support.
- `W20_0009` — **ESTUARY_TIDAL_RIVER / MEDIUM**. Large coastal water 30 m from ocean with strong graph support; kept under tidal treatment even without a reliable historical name.
- `W20_0046` — **ESTUARY_TIDAL_RIVER / HIGH**. Coastal water with strong Sông Bàn Thạch support.
- `W20_0002` — **UNKNOWN_REVIEW_REQUIRED**. Broad near-coastal Sông Kỷ Lộ water has strong river evidence but remains ambiguous between lower-river/lagoon/estuarine storage roles; automatic carving is disabled.
- `W20_0080` — **UNKNOWN_REVIEW_REQUIRED**. 1.3293 km2 highly persistent coastal water with no HydroRIVERS/V49-B/OSM channel support; no tidal/lake type is invented.
- `W20_0070` — **WETLAND_FLOODPLAIN_WATER / MEDIUM**. WorldCover wetland fraction 0.269 with no mapped channel support.
- `W20_0072` — **UNKNOWN_REVIEW_REQUIRED**. Mixed wetland/open-water evidence coexists with a small river graph, so neither a wetland-only nor river-only treatment is accepted automatically.
- `W20_0011` and `W20_0062` — **UNKNOWN_REVIEW_REQUIRED**. Historical OSM-only waterway candidates lack independent HydroRIVERS/V49-B support; they are not promoted to rivers or canals by a single volunteered centerline.

## 6. Gate C validation

`v49_validate_waterbody_classes.py` independently verifies:

- exact 81-object identity match with V49-A;
- no duplicate/missing/extra object IDs;
- no blank class, subtype, treatment or evidence fields;
- every class maps to its registered treatment;
- only `RIVER_STREAM`, `CANAL`, and `ESTUARY_TIDAL_RIVER` are eligible for future channel geometry;
- every unknown object is review-required and `NO_AUTOMATIC_CARVING`;
- ocean, lake/reservoir and wetland treatment cannot fall through to river trenching;
- historical OSM provenance is present;
- V49-C modifies zero DEM pixels;
- source DEM hash remains unchanged.

Validation result: **`gate_c_pass = true`**.

## 7. DEM integrity

Source DEM:

`D:\VTP\05-Du-lieu-GIS\PhuYen_DEM_30m_V48_BASE_COPERNICUS.tif`

Expected SHA-256:

`0c3c6ca6f299b00dd22a91a26c66e8c784f0e70c445412216f01efdd76504508`

Hash before classifier: identical.  
Hash after classifier: identical.  
Independent validator current hash: identical.  
Modified water pixels in V49-C: **0**.

## 8. Tests and QA

Targeted V49 test suite after the final rules:

`22 passed`

The tests cover ocean precedence, estuary classification, broad lake/reservoir safety, wetland safety, canal evidence requirements, broad-water protection against canal crossings, OSM-only ambiguity, mixed wetland/channel ambiguity, unknown no-carve behavior, and treatment completeness, plus the existing V49-A and V49-B tests.

The generated full-domain map was visually inspected. It shows marine water, the Hồ Sông Hinh storage object, the three accepted estuarine objects, river objects, wetland and review-required objects as spatially distinct treatments.

## 9. Deliverables

Output directory: `D:\VTP\River_Bathymetry_Project\V49_C_20261012`

- `V49_waterbody_classification.gpkg`
  - `classified_objects`
  - `osm_historical_waterways`
- `V49_waterbody_classification.csv`
- `V49_C_classification_audit.json`
- `V49_C_validation_report.json`
- `V49_C_classification_map.png`
- `historical_osm_manifest_source.json`

Source modules:

- `v49_classify_waterbodies.py`
- `v49_validate_waterbody_classes.py`
- `test_v49_waterbody_classification.py`

## 10. Scientific limitation carried forward

Gate C is a **safe classification/treatment gate**, not proof that every water object has known bathymetry. The 42 review-required objects represent 9.2061 km2 and remain explicitly outside automatic destructive carving. The largest review priorities are `W20_0002` and `W20_0080`.

V49-D/E may proceed only on objects/reaches whose class allows channel geometry, while preserving the review-required, lake/reservoir, wetland and ocean safeguards established here.

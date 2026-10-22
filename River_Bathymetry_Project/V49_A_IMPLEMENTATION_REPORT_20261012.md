# V49-A — Full-domain surface-water inventory and coverage audit

Date: 2026-10-12  
Workspace: `D:\VTP\River_Bathymetry_Project`  
Status: **Gate A PASS**

## What was implemented

V49-A now performs a read-only inventory of persistent surface water across the full 2100 × 2100 BG_Flood domain. It does not carve or alter the Copernicus DEM.

Implemented modules:

- `v49_build_water_inventory.py`
- `v49_classify_water_objects.py`
- `v49_validate_coverage.py`
- `test_v49_inventory.py`

Generated artifacts are under `V49_A_20261012`:

- `V49_master_water_inventory.gpkg`
- `V49_water_object_table.csv`
- `V49_water_coverage_audit.json`
- `V49_water_coverage_map.png`
- `V49_master_water_evidence.tif`
- `V49_ocean_mask.tif`
- `V49_A_validation_report.json`

## Scientific safeguards encoded in V49-A

1. JRC Global Surface Water is treated as open-water evidence, not bathymetry.
2. HydroRIVERS and OSM are treated as hydrographic evidence, not proof that a water polygon is a river.
3. Large persistent water polygons with sparse river-line coverage remain `OPEN_WATER_REVIEW_REQUIRED`; they are not automatically converted to river candidates.
4. Coastal open ocean is separated from inland statistics using an eastern-boundary open-water core. The method deliberately avoids geodesically flooding back up narrow river mouths.
5. Water close to the marine mask with river evidence remains `ESTUARY_REVIEW_REQUIRED`.
6. The V48 five-branch corridor is used only as a coverage reference.
7. Coverage is measured by both object status and water pixels. A large object touched by one V48 corridor is not counted as fully represented.
8. The source DEM SHA-256 is recorded before and after the run and must remain identical.

## Main result at JRC occurrence ≥20%

Minimum mapped object size: 25 pixels = 0.0225 km².

- Raw JRC water area: **880.4979 km²**
- Open-ocean area separated from inland statistics: **764.3754 km²**
- Inland water area before minimum-size filtering: **116.1225 km²**
- Qualifying inland water area: **113.8572 km²**
- Qualifying inland objects: **80**
- HydroRIVERS features intersecting the model domain: **373**

Legacy V48 coverage of qualifying inland-water pixels:

- Covered by V48 corridor: **32.8752 km²**
- Outside V48 corridor: **80.9820 km²**
- Pixel coverage: **28.8741%**
- Pixel outside corridor: **71.1259%**

Object coverage status:

- Fully covered (≥80% of object pixels in V48 corridor): **14 objects**
- Partially covered (>0% and <80%): **9 objects**
- Zero overlap with V48 corridor: **57 objects**
- Not fully covered: **66 / 80 objects**

This is substantially more informative than the earlier “touched object” audit. A reservoir/lake/wetland crossed by one river corridor can now be recognized as only partially represented.

## Provisional classification

All inland objects remain in a candidate/review state until V49-C adds dedicated water-body evidence:

- `RIVER_CANDIDATE`: 37 objects, 17.6085 km²
- `OPEN_WATER_REVIEW_REQUIRED`: 36 objects, 46.5714 km²
- `ESTUARY_REVIEW_REQUIRED`: 3 objects, 49.5567 km²
- `OSM_WATERWAY_CANDIDATE`: 4 objects, 0.1206 km²

No object is automatically labeled as a lake, reservoir, wetland, or hydraulic river bed from JRC alone.

## Persistence sensitivity

After marine separation and the same 25-pixel minimum:

| JRC occurrence threshold | Qualifying inland area | Objects |
|---:|---:|---:|
| 5% | 135.9153 km² | 146 |
| 20% | 113.8572 km² | 80 |
| 50% | 79.5888 km² | 71 |
| 90% | 25.5393 km² | 34 |

This confirms that the inventory is sensitive to persistence threshold, so V49 should retain multi-threshold evidence rather than hard-code a single mask as hydraulic truth.

## Verification

`test_v49_inventory.py`: **5 passed**.

`v49_validate_coverage.py`: **PASS** for:

- CSV/GPKG row consistency;
- deterministic unique object IDs;
- expected object count;
- classification/review completeness;
- ocean exclusion;
- DEM SHA-256 integrity;
- coverage map, evidence raster and ocean mask existence.

The Copernicus source DEM SHA-256 before and after V49-A is identical:

`0c3c6ca6f299b00dd22a91a26c66e8c784f0e70c445412216f01efdd76504508`

## Gate A decision

**PASS.** Every persistent inland object above the 25-pixel mapping threshold is represented in the inventory and is either provisionally classified or explicitly in a review queue. Ocean is excluded from inland coverage statistics and the DEM is unchanged.

The next phase should be V49-B: construct a directed hydrographic graph from HydroRIVERS/OSM/JRC/terrain evidence. V49-B should not yet assign physical bathymetric depth.


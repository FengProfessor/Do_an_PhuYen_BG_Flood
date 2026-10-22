# V49-F implementation report — coverage/science QA/QC

Date: 2026-10-13

## Outcome

V49-F coverage/science QA/QC is implemented and independently validated. The phase is read-only with respect to terrain: it aggregates the accepted V49-A/B/C/C.1/D/E evidence and does not modify the source DEM or the V49-E hydraulic-bed raster.

**Gate F: PASS for QA/QC completeness. Hydraulic promotion remains blocked pending V49-G.**

This distinction is intentional. Gate F PASS means the requested science and coverage metrics are exposed and internally validated without using storage volume or self-reproduced assumed depths as evidence of physical correctness. It does not mean that the current V49-E hydraulic bed has full-domain bathymetric coverage or has been hydraulically validated.

## Coverage result

The full V49 inventory contains 80 qualifying inland-water objects covering 113.8572 km² after marine exclusion.

Current V49-E hydraulic synthesis represents only three inland objects associated with its two accepted reaches:

- represented inland objects: **3 / 80 = 3.75%**;
- represented object area: **0.1638 km² / 113.8572 km² = 0.143864%**;
- actual raster area modified by V49-E: **0.0648 km²**;
- V49-E still modifies only `HR_41349822` and `HR_41352752`.

For `RIVER_STREAM`, V49-C contains 33 objects (12.2301 km²). V49-E represents 3 of those objects, or **1.3393% of river-object area**, while the actual modified raster footprint is **0.52984% of total RIVER_STREAM object area**. Other water classes currently have zero V49-E hydraulic-bed modification, as expected from the conservative C.1 ∩ D gate.

The coverage audit deliberately reports both object association and actual modified footprint. Association alone must not be interpreted as complete bathymetric coverage of an object's polygon.

## Major persistent-water omissions

For V49-F, a major persistent inland object is defined explicitly as a C.1 `CONFIRMED_PERSISTENT` inland object that either has area >= 1.0 km² or contains at least one associated major graph reach.

Five such objects currently have no accepted V49-E hydraulic representation:

| Object | Final class | Area (km²) | Major graph reaches | Required treatment |
|---|---|---:|---:|---|
| `W20_0059` | `LAKE_RESERVOIR` | 42.7806 | 9 | stage-area-volume or defensible bathymetry |
| `W20_0026` | `RIVER_STREAM` | 0.2934 | 1 | reach-scale bathymetry |
| `W20_0068` | `RIVER_STREAM` | 0.0702 | 1 | reach-scale bathymetry |
| `W20_0066` | `RIVER_STREAM` | 0.0576 | 1 | reach-scale bathymetry |
| `W20_0041` | `RIVER_STREAM` | 0.0297 | 1 | reach-scale bathymetry |

These omissions are reported as promotion blockers, not silently converted into synthetic channels.

## Topology and confluence QA

- major reach orphan count: **0**;
- directed graph cycle count: **0**;
- V49-B linear-water objects lacking graph support: **2** (`W20_0011`, `W20_0062`), retained as a known coverage QA finding;
- V49-D confluences reviewed: **168**;
- unresolved authorized V49-D confluence inversions: **0**;
- V49-E confluence checks touching admitted scope: **2**;
- unresolved V49-E confluence inconsistencies: **0**.

## Geometry distribution and provenance

V49-F reports width/depth percentiles by Strahler order for all 95 V49-C-eligible reaches. Width coverage is intentionally incomplete where V49-D did not have adequate direct width evidence; the missing values remain missing rather than being filled to improve statistics.

Depth-source fractions in the 95-reach V49-C-eligible scope are:

- survey/observed bathymetry: **0 / 95 = 0.0%**;
- hydraulic inversion: **7 / 95 = 7.3684%**;
- empirical fallback/prior: **86 / 95 = 90.5263%**;
- unresolved: **2 / 95 = 2.1053%**.

The two reaches admitted by V49-E retain `HIGH` and `VERY_HIGH` uncertainty classes. This confirms that the current product is predominantly inferred geometry and must not be described as survey-grade bathymetry.

## Incision and added storage

Effective V49-E output remains:

- modified pixels: **72** after float32 quantization;
- maximum effective incision: **0.3742065 m**;
- added channel volume/storage proxy: **8,008.2092 m³**;
- forced longitudinal adjustments: **0**;
- global monotonic filter: **not used**.

V49-F additionally reconstructs per-reach pre-quantization incision percentiles using the same accepted V49-E synthesis rule. For `HR_41352752`, 50 cells receive a positive pre-quantization taper but one rounds back to the original float32 DEM, leaving the 49 effective modified cells reported by V49-E. This is expected numerical quantization and is kept explicit.

The added storage number is descriptive only. V49-F contains no minimum storage target and does not deepen channels to satisfy a volume threshold.

## Hydraulic sensitivity status

Matched hydraulic-model sensitivity metrics are **not yet available**. V49-F records this explicitly as:

`PENDING_V49_G_MATCHED_BG_FLOOD_RUNS`

V49-G must run the matched V48 BASE, legacy five-branch diagnostic, V49 CENTRAL, V49 LOW and V49 HIGH scenarios with identical forcing/configuration and compare flood extent, WSE, velocity, timing and mass balance against independent observations.

Therefore:

- `gate_f_pass = true`;
- `hydraulic_promotion_ready = false`.

## Source DEM integrity

The Copernicus/V48 source DEM still has SHA-256:

`0c3c6ca6f299b00dd22a91a26c66e8c784f0e70c445412216f01efdd76504508`

V49-F makes zero DEM edits.

## Outputs

Outputs are in `D:\VTP\River_Bathymetry_Project\V49_F_20261013`:

- `V49_F_science_qaqc.json`
- `V49_F_validation_report.json`
- `V49_F_coverage_by_class.csv`
- `V49_F_major_persistent_omissions.csv`
- `V49_F_geometry_by_strahler.csv`
- `V49_F_geometry_source_fractions.csv`
- `V49_F_incision_by_reach.csv`
- `V49_F_added_storage_by_reach.csv`
- `V49_F_coverage_by_class.png`
- `V49_F_depth_by_strahler.png`

Implementation: `v49_science_qaqc.py`.

Independent validator: `v49_validate_science_qaqc.py`.

Focused tests: `test_v49_science_qaqc.py`.

## Next executable phase

**V49-G — matched BG_Flood hydraulic validation and bathymetry sensitivity.**

V49-G must preserve the coverage blockers above in its interpretation. A successful model run cannot retroactively turn omitted or weakly supported bathymetry into observed geometry.

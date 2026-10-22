# V49-G implementation report — matched hydraulic validation preparation

Date: 2026-10-13

## Outcome

V49-G experiment preparation is complete and independently validated. The matched comparison is frozen as **BASE / CENTRAL / LOW / HIGH** under the unchanged V48 R1 BG_Flood forcing and configuration contract.

**V49-G preparation: PASS. Gate G: PENDING matched CENTRAL/LOW/HIGH BG_Flood runs. Hydraulic promotion: BLOCKED.**

This status is intentional. Preparation reproducibility is not hydraulic validation. Gate G is not promoted from terrain self-consistency, added storage volume, or the existence of input files.

## Comparable experiment

The canonical runtime lineage is `D:\VTP\V48_runs\20261004_runtime_fix_r1`.

The four comparable arms use the same 30 m grid, forcing, losses, Manning raster, boundary conditions, runtime settings, output variables and `minmask=-4.0`. Only the terrain and output path vary by arm.

- `BASE`: frozen V48 Copernicus terrain.
- `CENTRAL`: accepted V49-E hydraulic bed.
- `LOW`: V49-D `depth_low_m` applied through the exact V49-E authorization/carving rule.
- `HIGH`: V49-D `depth_high_m` applied through the exact V49-E authorization/carving rule.

The normalized BG_Flood configuration hash for all four arms is:

`0414cfd0c3baa7445a518a71814daafaf153439ef985764b722df78768c04229`

All four comparable rasters are 2100 × 2100 in EPSG:32649 and contain zero valid cells at or below the canonical `minmask=-4.0` threshold.

## Sensitivity terrains

Both sensitivity variants preserve the accepted V49-E spatial authorization. They modify only `HR_41349822` and `HR_41352752`, with zero edits outside the authorized mask, zero edits in the Đồng Cam protected mask, and zero raised cells.

| Arm | Modified pixels | Lowering volume | Max lowering |
|---|---:|---:|---:|
| LOW | 72 | 3,597.8577 m³ | 0.1871033 m |
| CENTRAL | 72 | 8,008.2092 m³ | 0.3742065 m |
| HIGH | 72 | 14,020.6696 m³ | 0.6361389 m |

Raster ordering is physically consistent with the defined uncertainty envelope: LOW never lowers more than CENTRAL, and CENTRAL never lowers more than HIGH. Both violation counts are zero.

The LOW and HIGH variants reuse V49-D uncertainty bounds directly; they do not introduce branch-specific fixed depths or a global monotonic filter.

## Legacy five-branch terrain

The historical five-branch bathymetry DEM is retained as **diagnostic-only / non-comparable** for Gate G.

Its valid terrain minimum is approximately -8.3903 m and **10,740 valid cells are <= -4.0 m**. Running that terrain under the canonical V48 R1 `minmask=-4.0` would mask real terrain cells and change the modeled domain. Changing `minmask` only for that arm would also break the matched-configuration requirement.

Therefore the legacy terrain must not be included in the formal BASE/CENTRAL/LOW/HIGH acceptance comparison under a falsely “matched” label.

## Sentinel-1 preregistered comparison

The frozen observation is:

`D:\VTP\05-Du-lieu-GIS\DakLak_PhuYen_FloodExtent_Otsu_S1RTC_20211130_05h36_V48.tif`

SHA-256:

`9c1ad68908c220456c82a2459380e14193242a3daa32c0001989c4ffd8292db6`

The acquisition midpoint is `2021-11-29T22:36:51.298763Z`. Evaluation uses simulated depth `h > 0.30 m`, excludes permanent-water density > 0.5, requires `HAND >= 0`, and chooses the nearest model frame with maximum allowed time offset 5,400 s.

This Sentinel-1 product was held out from the V48 conditioning pipeline and is useful as a retrospective confirmatory comparison. It is not described as fully independent external validation because the 2021 SAR event had been viewed in earlier project work.

The existing V48 BASE result contains the preregistered comparison frame. BASE frame 33 is at 367,200.125 s (~102 h) and gives:

- TP: 314,637;
- FP: 241,912;
- FN: 259,630;
- TN: 2,032,081;
- precision: 0.565336;
- recall: 0.547893;
- CSI / IoU: 0.385500;
- F1: 0.556478;
- observed area: 516.8403 km²;
- simulated area: 500.8941 km²;
- area bias: -3.0853%;
- modeled flood cells with HAND <= 3.5 m: 69.9231%.

The existing BASE NetCDF reaches about 105 h rather than the full 120 h contract, but it contains the preregistered Sentinel frame. This does not substitute for the new matched sensitivity runs.

## Evidence that is still unavailable

No verified local gauge/WSE time series with documented timestamp, datum and lineage was found for this Gate-G package. No frozen surveyed high-water-mark dataset and no preregistered wet/dry point set is currently available either.

Accordingly, V49-G does not fabricate WSE bias, WSE MAE/RMSE, arrival-time error or peak-timing error. Those metrics remain unavailable unless defensible observation data is added.

Velocity sanity and mass-balance assessment also remain pending the matched CENTRAL/LOW/HIGH simulations.

## Current run state

The CENTRAL, LOW and HIGH BG_Flood input terrains and parameter files are ready in `D:\VTP\River_Bathymetry_Project\V49_G_20261013`.

The matched CENTRAL/LOW/HIGH NetCDF results are not present yet. Historical runtime evidence shows the comparable BASE simulation required multiple days of wall-clock time to reach about 105 h, so this implementation does not claim synchronous completion of those long simulations.

The independent validator records the current state as:

`PREPARED_PENDING_MATCHED_BG_FLOOD_RUNS`

with:

- `preparation_pass = true`;
- `gate_g_pass = false`;
- `hydraulic_promotion_ready = false`.

## Source integrity

The source Copernicus/V48 DEM remains unchanged at SHA-256:

`0c3c6ca6f299b00dd22a91a26c66e8c784f0e70c445412216f01efdd76504508`

V49-G preparation creates new sensitivity products and configs; it does not overwrite the source DEM.

## Outputs

Primary outputs are in `D:\VTP\River_Bathymetry_Project\V49_G_20261013`:

- `V49_G_PREPARATION_MANIFEST.json`
- `V49_G_validation_report.json`
- `V49_G_LOW_hydraulic_bed.tif/.asc`
- `V49_G_HIGH_hydraulic_bed.tif/.asc`
- `V49_G_CENTRAL_hydraulic_bed.asc`
- `BG_param_V49_G_BASE.txt`
- `BG_param_V49_G_CENTRAL.txt`
- `BG_param_V49_G_LOW.txt`
- `BG_param_V49_G_HIGH.txt`
- `SAR_vs_V48_BASE_frame_33_metrics.json`
- `SAR_vs_V48_BASE_frame_33_contingency.png`

Implementation: `v49_prepare_hydraulic_validation.py`.

Independent validator: `v49_validate_hydraulic_validation.py`.

Focused sensitivity tests: `test_v49_hydraulic_validation.py`.

## Next executable action

Run the prepared CENTRAL, LOW and HIGH BG_Flood cases under the frozen V48 R1 runtime, evaluate each at the preregistered Sentinel-1 time using the same mask/threshold rules, and then assess velocity/mass balance plus any defensible hydraulic observations that become available.

Gate G can be decided only after those matched results exist and the comparison has been reviewed. Until then, the V49 hydraulic DEM is not promoted.

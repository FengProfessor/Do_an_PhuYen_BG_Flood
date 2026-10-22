# V48 formal SAR evaluation — remaining provenance blockers

**Date:** 2026-10-02  
**State:** `READY_FOR_FORMAL_EVALUATION`  
**Formal BG_Flood run:** not started  
**Formal Sentinel-1 evaluation:** not started

## Completed gate work

- The direct closed-loop terrain converged to zero remaining strict topology components.
- The converged terrain is frozen as `PhuYen_DEM_30m_V48_CONDITIONED_CLOSED_LOOP_FROZEN.tif`.
- The frozen terrain is byte-identical to the converged candidate and has SHA-256 `e75019ce5d0c02996bfab421623bda33ab3d56ff5bfd8a06e51f2ca2b3cd4feb`.
- The BG_Flood input contract was regenerated against the closed-loop frozen terrain and passes contract validation.
- A new formal V48 Sentinel-1 observation was reconstructed directly from the public Planetary Computer RTC VV asset and frozen as `DakLak_PhuYen_FloodExtent_Otsu_S1RTC_20211130_05h36_V48.tif`, SHA-256 `9c1ad68908c220456c82a2459380e14193242a3daa32c0001989c4ffd8292db6`.
- `V48_SAR_OBSERVATION_RELEASE_20261002.json` pins the source STAC item, exact VV asset, acquisition UTC, processing script, target grid, Otsu threshold, and class semantics. `v48_sar_observation_validate.py` passes with zero failures.

## Resolved Sentinel provenance blockers

The three former Sentinel blockers are closed for the newly reconstructed V48 observation:

- Product-to-local-observation lineage is verified by the frozen release manifest and source asset metadata.
- Acquisition start/stop UTC is tied to that exact release and local raster hash.
- Class `0`, class `1`, and NoData `255` semantics are pinned by the processing manifest and independently validated against the GeoTIFF.

The older historical Otsu TIFF still lacks those provenance links and is not used as the formal V48 observation.

## Resolved BG_Flood model epoch timezone

The retained generator command for the exact V23 rainfall requests `timezone=Asia/Ho_Chi_Minh` and maps the hourly sequence to elapsed seconds from `2021-11-26 00:00` local time. The later monotonicity repair is also retained and proves that only the erroneous trailing `432000` row was removed after `514800`; the time origin was not changed. V34 retains the complete V23 time axis while multiplying rainfall rates by 2.0.

The frozen epoch is `2021-11-26T00:00:00+07:00` = `2021-11-25T17:00:00Z`. Provenance is frozen in `V48_RUN_EPOCH_PROVENANCE_20261002.json` and the pre-run manifest in `V48_BG_Flood_RUN_MANIFEST_20261002.json`.

## Release rule

The release condition is now satisfied: `v48_sar_preregistration_validate.py` reports `READY_FOR_FORMAL_EVALUATION` with no integrity failures and no blockers. Formal BG_Flood and Sentinel-1 evaluation have not started yet.

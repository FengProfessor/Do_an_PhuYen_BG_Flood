# V48 Sentinel-1 preregistration — 2026-10-02

**Status: READY_FOR_FORMAL_EVALUATION.** The closed-loop terrain, BG_Flood input contract, Sentinel-1 observation, and run epoch are frozen and hash-pinned. No Sentinel-1 evaluation and no formal BG_Flood run has been executed yet.

## Interpretation

The 2021 Sentinel-1 observation is **held out from the V48 conditioning pipeline** and may be used only as a **retrospective confirmatory comparison**. It is not described as fully independent external validation because the same 2021 SAR event was viewed during earlier V39-V45 work.

## Observation reconstructed and provenance-verified

The formal V48 observation is newly reconstructed from Microsoft Planetary Computer Sentinel-1 RTC item `S1A_IW_GRDH_1SDV_20211129T223638_20211129T223703_040792_04D7A0_rtc`, Sentinel-1A IW VV, descending, relative orbit 120. The pinned acquisition is 2021-11-29 22:36:38.799806–22:37:03.797720 UTC, with midpoint `2021-11-29T22:36:51.298763Z`.

The frozen local raster is `DakLak_PhuYen_FloodExtent_Otsu_S1RTC_20211130_05h36_V48.tif`, SHA256 `9c1ad68908c220456c82a2459380e14193242a3daa32c0001989c4ffd8292db6`. The release manifest `V48_SAR_OBSERVATION_RELEASE_20261002.json` pins the exact public VV asset URL and HTTP identity metadata, source STAC/range-read probes, processing script hash, target-grid hash, 512-bin Otsu threshold `-8.834193476225742 dB`, and class semantics. `v48_sar_observation_validate.py` returns `PASS_V48_SAR_OBSERVATION_VALIDATION` with classes `{0,1,255}` and no failures.

The older `DakLak_PhuYen_FloodExtent_Otsu_20211130_05h36.tif` remains historical evidence only. The new V48 release does not claim to prove that older raster's missing lineage.

## Frozen evaluation rules

- Reproject the observation to the common 30 m EPSG:32649 grid with nearest-neighbour resampling.
- Simulated wet cell: `h > 0.30 m`. The threshold is fixed before formal V48 SAR evaluation and may not be tuned afterwards.
- Evaluation mask is identical for BASE and CONDITIONED: common valid model domain ∩ verified observation classes `{0,1}` ∩ `water_density <= 0.5` ∩ `HAND >= 0.0`.
- Frame rule: use the midpoint of the lineage-verified Sentinel acquisition in UTC; subtract the frozen BG_Flood run epoch; select the output frame minimizing absolute time offset, ties to the earlier frame. Maximum allowed offset is 5,400 s for the 10,800 s output interval.
- Metrics: TP, FP, FN, TN, precision, recall, CSI/IoU, F1, observed area, simulated area, and area bias `(A_sim - A_obs) / A_obs`.
- One-shot comparison uses the same engine, forcing, initial state, epoch, frame rule, mask, threshold, and metrics for `V48_BASE_COPERNICUS` and the eventual closed-loop conditioned V48 terrain. Report both arms and CONDITIONED-minus-BASE deltas.

The historical `>=9/11` terrain-selection rule is not a SAR pass/fail criterion. Its leverage is recorded only as upstream sensitivity provenance.

## Closed-loop terrain gate — resolved

The direct closed-loop conditioning converged with zero remaining strict topology components after 16 conditioning transitions. The formal CONDITIONED terrain is now frozen at `05-Du-lieu-GIS/PhuYen_DEM_30m_V48_CONDITIONED_CLOSED_LOOP_FROZEN.tif`, SHA256 `e75019ce5d0c02996bfab421623bda33ab3d56ff5bfd8a06e51f2ca2b3cd4feb`. It changes 66 valid cells relative to the V48 Copernicus base and the maximum cumulative lowering is `0.9959607571363449 m`.

The BG_Flood contract was regenerated against that exact terrain and passes `PASS_V48_BG_FLOOD_CONTRACT_VALIDATION`. This resolves the former closed-loop terrain blocker while preserving the pre-existing frozen terrain as historical provenance.

## Run epoch gate — resolved

The exact retained generator command for `rain_v23_era5_spatial.txt` requests `timezone=Asia/Ho_Chi_Minh`, starts on `2021-11-26`, and encodes the returned hourly sequence as `t_s = i * 3600`. Historical execution records also prove that the later 2026-09-04 edit removed only one backward duplicate terminal row (`432000 <= 514800`) without rebasing the time axis. `rain_v34_era5_x2.txt` has the same 144 hourly timestamps as V23 and only applies the frozen x2 rainfall-rate scaling.

The model epoch is therefore frozen as `2021-11-26T00:00:00+07:00` (`Asia/Ho_Chi_Minh`) = `2021-11-25T17:00:00Z`. The hash-backed evidence is in `V48_RUN_EPOCH_PROVENANCE_20261002.json`; the pre-run freeze is in `V48_BG_Flood_RUN_MANIFEST_20261002.json`.

`v48_sar_preregistration_validate.py` now returns `READY_FOR_FORMAL_EVALUATION` with zero blockers and zero integrity failures. `V48_REMEDIATION_GATE_STATUS_20261002.json` also reports `READY_FOR_FORMAL_EVALUATION`. Formal BG_Flood and Sentinel-1 evaluation remain unexecuted at this checkpoint.

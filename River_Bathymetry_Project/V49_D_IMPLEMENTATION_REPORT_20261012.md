# V49-D implementation report — reach-scale geometry estimation

Date: 2026-10-12

## Outcome

V49-D estimated traceable reach-scale hydraulic geometry without modifying the V48 Copernicus DEM.  The estimator uses V49-C final channel eligibility, repeated cross-sections through persistent-water polygons, robust longitudinal DEM surface-slope proxies, HydroRIVERS mean-discharge proxy, Manning inversion where its inputs are usable, and the HydroMT documented power-law fallback otherwise.

Legacy fixed depths 3.50 m / 2.25 m / 1.20 m are not used by the estimator.

## Scope and authorization

- Graph reaches: **370**
- Reaches associated with a V49-C eligible river/tidal object: **91**
- Reaches authorized as candidate V49-E fluvial geometry: **2**
- Reaches held in the explicit V49-D review queue: **89**
- Tidal/backwater reaches held for review: **71**
- Legacy canal candidates held for review: **2**
- Distribution outliers excluded pending review: **0**

Authorization is conservative: an authorized reach must be a V49-C `RIVER_STREAM`, have traceable positive width and depth, have no unresolved V49-B topology review, and not be tidal or an unverified legacy canal.

After physical review of the first-pass width distribution, indirect `object area / graph length` widths and widths derived only from broad/ambiguous water-object morphology were downgraded to review-only.  This prevents large lake/floodplain-like polygons from being silently converted into channel width.

## Depth evidence hierarchy actually available

No surveyed bathymetry/local cross-sections were present in the V49 bundle.  Therefore V49-D uses:

1. Manning rectangular inversion when JRC-derived width, positive DEM longitudinal slope proxy, HydroRIVERS discharge proxy and roughness prior are all usable.
2. HydroMT-style power law `h = 0.27 * Q^0.30` as the fallback.

`DIS_AV_CMS` remains explicitly labelled a **mean-discharge proxy, not bankfull discharge**.  The generic natural-channel Manning range 0.025–0.050 (central 0.035) is stored as a prior, not a calibration.  Inferred depth uncertainty is wider than the minimum ±30% envelope because the key discharge and roughness quantities are not locally calibrated.

## Preliminary bed QA

The preliminary bed fields are `Copernicus surface/WSE proxy - inferred depth` and are QA quantities only.  They are not surveyed bed elevations.  All **168** V49-B confluences have an explicit state.  Unexplained inversions among fully authorized incident reaches: **0**.

Dong Cam remains an explicit hydraulic control.  Its structure record states that later V49-E synthesis must preserve the control and must not erase it with a global monotonic filter.

## DEM invariance

- Expected SHA-256: `0c3c6ca6f299b00dd22a91a26c66e8c784f0e70c445412216f01efdd76504508`
- Before V49-D: `0c3c6ca6f299b00dd22a91a26c66e8c784f0e70c445412216f01efdd76504508`
- After V49-D: `0c3c6ca6f299b00dd22a91a26c66e8c784f0e70c445412216f01efdd76504508`
- Modified DEM pixels in V49-D: **0**

## Preliminary Gate D status

**PASS**.  Final Gate D is decided independently by `v49_validate_reach_geometry.py`.

Outputs are in `V49_R3_20261013\D`.  V49-E must consume only rows where `geometry_authorized_for_v49e = True`; tidal/review/excluded rows must remain unchanged until their missing hydraulic evidence is resolved.

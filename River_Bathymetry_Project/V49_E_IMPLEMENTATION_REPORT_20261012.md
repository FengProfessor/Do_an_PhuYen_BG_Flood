# V49-E implementation report — hydraulic-bed synthesis

Date: 2026-10-12

## Outcome

V49-E hydraulic-bed synthesis is implemented and independently validated.  The phase creates a new BG_Flood-ready elevation raster while leaving the V48/Copernicus source DEM unchanged.

Automatic synthesis is controlled by the strict intersection of V49-D geometry authorization and the V49-C.1 fixed-water gate.  The current evidence admits exactly two reaches:

- `HR_41349822`
- `HR_41352752`

`HR_41349985` remains blocked by C.1 because its associated `W20_0064` conflicts with current Hồ Hóc Răm reservoir/dam evidence.  V49-E does not promote any reach rejected by V49-D or C.1.

## Conservative synthesis rule

For each admitted reach, V49-E additionally restricts modification to cells that lie inside the reach's associated C.1 `CONFIRMED_PERSISTENT` water-object polygons.  This prevents a HydroRIVERS centerline from causing destructive carving through intervening terrain that lacks fixed-water evidence.

The 2-D bed uses:

- V49-D central reach width;
- V49-D inferred reach depth;
- local source-DEM/water-surface elevation as the longitudinal surface proxy;
- raised-cosine lateral taper from thalweg to estimated bank;
- no global monotonic lowering filter;
- the existing 187-cell Đồng Cam infrastructure protection mask with strict zero modification.

An earlier endpoint-grade-line trial was rejected before acceptance because it could demand about 11.53 m of lowering on a reach whose inferred depth was only about 0.37 m.  The accepted implementation bounds centerline lowering by the V49-D reach depth and requires overlap with C.1 persistent-water evidence.

## Raster modification result

- Authorized reaches: **2**
- Authorized reach/class mask cells: **73**
- Effective modified cells after float32 quantization: **72**
- Raised cells: **0**
- Modified cells outside independently reconstructable authorized mask: **0**
- Protected Đồng Cam cells: **187**
- Protected cells modified: **0**
- Maximum lowering: **0.3742065 m**
- Total lowering volume: **8,008.2092 m³**

Per reach:

| Reach | Class | Modified cells | Volume (m³) | Max lowering (m) | V49-D depth (m) |
|---|---|---:|---:|---:|---:|
| `HR_41349822` | `RIVER_STREAM` | 23 | 3,944.1193 | 0.3742065 | 0.3742013 |
| `HR_41352752` | `RIVER_STREAM` | 49 | 4,064.0900 | 0.1752930 | 0.1753026 |

The few-micrometre difference between the first reach's stored maximum lowering and its decimal V49-D depth is float32 raster quantization; the validator explicitly allows only this numerical tolerance.

## Junction and longitudinal controls

- V49-E confluence checks touching the admitted scope: **2**
- Unexplained bed inversions: **0**
- Forced longitudinal adjustments: **0**
- Global monotonic filter used: **false**
- Legacy named-branch fixed depths used: **false**

The phase therefore does not erase weir, reservoir, tidal/backwater, or other real controls merely to force a downhill profile.

## Source DEM integrity

- Expected SHA-256: `0c3c6ca6f299b00dd22a91a26c66e8c784f0e70c445412216f01efdd76504508`
- SHA-256 before V49-E: same
- SHA-256 after V49-E: same
- Source DEM edited in place: **no**

V49-E writes a separate hydraulic-bed DEM and delta raster.

## Outputs

Outputs are in `D:\VTP\River_Bathymetry_Project\V49_E_20261012`:

- `V49_E_hydraulic_bed.tif`
- `V49_E_delta_z.tif`
- `V49_E_authorized_mask.tif`
- `V49_E_hydraulic_bed.gpkg`
- `V49_E_modification_volume_by_reach.csv`
- `V49_E_longitudinal_adjustments.csv`
- `V49_E_confluence_checks.csv`
- `V49_E_delta_z_map.png`
- `V49_E_hydraulic_bed_audit.json`
- `V49_E_validation_report.json`

Implementation: `v49_synthesize_hydraulic_bed.py`.

Independent validator: `v49_validate_hydraulic_bed.py`.

Focused tests: `test_v49_hydraulic_bed.py`.

Gate E is accepted only when `V49_E_validation_report.json` reports `gate_e_pass = true`.

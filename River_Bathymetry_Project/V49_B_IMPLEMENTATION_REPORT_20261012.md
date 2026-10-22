# V49-B — Full Directed Hydrographic Graph

Date: 2026-10-12  
Workspace: `D:\VTP\River_Bathymetry_Project`

## Scope

V49-B replaces the five manually routed V48 branches with a full-domain directed graph built primarily from HydroRIVERS topology. It does **not** assign bathymetric depth and does **not** alter the Copernicus DEM.

HydroRIVERS `HYRIV_ID -> NEXT_DOWN` is the authoritative direction/topology source in this phase. Reach geometry is normalized using neighbouring graph reaches. DEM elevation is retained only as QA evidence, because Copernicus GLO-30 over water cannot be treated as measured channel-bed elevation.

## Implemented outputs

- `v49_build_hydrograph.py`
- `v49_validate_hydrograph.py`
- `test_v49_hydrograph.py`
- `V49_B_20261012/V49_hydrograph.gpkg`
  - `reaches`
  - `nodes`
  - `structures`
  - `issues`
- `V49_B_20261012/V49_reach_table.csv`
- `V49_B_20261012/V49_node_table.csv`
- `V49_B_20261012/V49_graph_audit.json`
- `V49_B_20261012/V49_hydrograph_map.png`
- `V49_B_20261012/V49_B_validation_report.json`

## Resulting graph

- HydroRIVERS reaches represented: 368 graph reaches from 367 native in-domain HydroRIVERS features. The extra reach is the Sông Ba feature split at Đồng Cam.
- Legacy canal candidates: 2 (`CANAL_DONG_CAM_NORTH`, `CANAL_DONG_CAM_SOUTH`).
- Total graph reaches: 370.
- Nodes: 396.
- Confluences: 168.
- Explicit structures: 1 (`STRUCT_DONG_CAM`).
- Major reaches: 53.
- Directed cycles: 0.
- Orphan major reaches: 0.
- Unresolved terminals: 0.
- Connected-edge endpoint gaps >120 m: 0.

Terminal types:

- `OCEAN_OUTLET`: 13
- `DOMAIN_EXIT`: 9
- `WATERBODY_TERMINAL_REVIEW`: 2
- `CANAL_TERMINUS`: 2

Two HydroRIVERS features (`41342672`, `41342884`) have native `NEXT_DOWN=0` while terminating inside the same persistent inland-water object (`W20_0002`). They are therefore represented explicitly as `WATERBODY_TERMINAL_REVIEW`, not silently forced to an invented downstream reach. V49-C must determine the receiving water-body type.

Two HydroRIVERS links leave the model boundary and their `NEXT_DOWN` features later re-enter the domain. V49-B represents these as `DOMAIN_EXIT` / `DOMAIN_ENTRY`; it does not connect them by a fictitious straight edge across space outside the BG_Flood domain.

## Đồng Cam

The verified V48 landmark `(row=1278, col=1217)` is converted to projected coordinates and snapped to the nearest HydroRIVERS Sông Ba reach. That reach is split into an upstream and downstream graph reach around `STRUCT_DONG_CAM`.

This replaces the old raster-only exception with an explicit hydraulic-control object while preserving the verified V48 structure evidence.

The two Đồng Cam irrigation canals are retained as `LEGACY_CANAL_CANDIDATE` reaches and marked review-required. They are not promoted to fully verified graph reaches because the three locally archived OSM waterway JSON files are 0-byte placeholders. Their present geometry ultimately comes from the V48 routed paths and therefore still needs independent OSM/engineering/vector verification.

## V49-A water-object coverage check

There are 44 V49-A objects currently classified as river/OSM-waterway/estuary candidates. The directed graph supports 42 of them. Two low-confidence OSM-only objects do not intersect the present graph:

- `W20_0011`: 0.0225 km², OSM distance 0 m, no HydroRIVERS feature within the object.
- `W20_0062`: 0.0342 km², OSM distance 0 m, no HydroRIVERS feature within the object.

These remain explicit V49-C review items. No synthetic graph reach is generated from a distance raster alone because a distance raster does not preserve waterway direction, connectivity, or feature identity.

## DEM invariance

Copernicus DEM SHA-256 before and after V49-B:

`0c3c6ca6f299b00dd22a91a26c66e8c784f0e70c445412216f01efdd76504508`

The DEM is unchanged.

## Validation

Automated tests:

- `test_v49_hydrograph.py`
- `test_v49_inventory.py`
- Result: **11 passed**.

Independent structural validator result:

- duplicate reach IDs: 0
- duplicate node IDs: 0
- missing from-nodes: 0
- missing to-nodes: 0
- directed cycles: 0
- terminal reaches without explicit terminal type: 0
- Đồng Cam structure count: 1
- topology validation: **PASS**

The QA map was visually inspected and shows the expected full-domain drainage network, the principal Sông Ba / lower-river axes, the explicit Đồng Cam structure, and the two legacy canal candidates.

## Gate B status

**Gate B PASS** as the directed hydrographic-topology gate:

- zero orphan major reaches;
- zero unexplained directed loops;
- every accepted graph reach has a downstream graph target or explicit terminal type;
- confluence topology is connected consistently;
- Đồng Cam is an explicit graph structure.

Bed-elevation ordering is intentionally outside Gate B and is deferred to V49-D/E, where defensible reach geometry and hydraulic-bed elevations exist. Copernicus water-surface pixels are not used as fabricated bed elevations.

The 26 `dem_downhill_qa_flag` reaches are QA flags only; they are not topology failures and are not corrected by forcing graph direction from DEM slope.

## Next step

Proceed to V49-C water-body classification before any terrain modification. Priority review items are:

1. classify `W20_0002`, which receives two HydroRIVERS source terminals;
2. independently recover/verify vector geometry and connectivity for the two Đồng Cam canals;
3. resolve OSM-only water objects `W20_0011` and `W20_0062`;
4. classify broad persistent-water objects so lake/reservoir/wetland/estuary pixels cannot be passed into a river-carving rule.


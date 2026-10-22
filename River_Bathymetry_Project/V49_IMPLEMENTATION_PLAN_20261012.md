# V49 — Full-Domain Hydro-Bathymetry Conditioning

**Current status, 2026-10-13:** remediation R3 is validated and the matched GPU runs are active. See section 11 and [V49_R3_UNPASSED_REMEDIATION_20261013.md](D:/VTP/River_Bathymetry_Project/V49_R3_UNPASSED_REMEDIATION_20261013.md). Earlier phase snapshots below are retained as history; their next-action statements and unresolved counts are superseded by section 11.

Date: 2026-10-12  
Workspace: `D:\VTP`  
Target model: BG_Flood 30 m Phú Yên domain

## 1. Why V49 is required

V48 and the current `River_Bathymetry_Project` solved an important but narrower problem: five manually selected river/canal branches can be carved into a continuous, numerically smooth channel surface. They do **not** establish that the full surface-water network of the model domain has been detected, classified, reconstructed, and validated for hydraulic use.

The current network extractor explicitly hard-codes five branches with fixed start/end grid coordinates and fixed design depths:

- Sông Ba / Đà Rằng
- Sông Bàn Thạch
- Sông Kỳ Lộ
- Kênh chính Bắc
- Kênh chính Nam

This means the existing 209/209 assertions and 24/24 micro-benchmarks demonstrate internal consistency of the selected carved corridors. They are not evidence that all rivers, tributaries, lakes, reservoirs, wetlands, estuarine waters, and other persistent surface-water areas in the full model domain have been represented correctly.

A first V49 gap audit against the local JRC occurrence raster confirms this limitation. At JRC occurrence >=20%, 76 connected water components have at least 25 pixels. Fifty-five of those components are not touched by the current bathymetry carving, representing about 9.57 km2 of thresholded water pixels. This is a screening result, not yet a final inland-water statistic, because JRC also contains coastal/marine water and the components still need hydrologic classification.

Audit artifact: `V49_surface_water_gap_audit_20261012.json`.

## 2. Scientific rule for V49

Hydro-conditioning and hydraulic bathymetry are separate products.

`DEM_HYDRO_CONDITIONED` is allowed to use aggressive drainage enforcement where necessary for watershed topology, flow direction, and accumulation.

`DEM_HYDRAULIC_BED` must represent physically defensible channel/storage geometry for BG_Flood. It must not inherit arbitrary AGREE/stream-burning drops as if they were measured bed elevation.

The V49 pipeline therefore creates two independent outputs and preserves their provenance.

## 3. V49 architecture

```text
Copernicus GLO-30 base DEM
        |
        +-- Copernicus/JRC surface-water evidence
        +-- HydroRIVERS / OSM hydrography
        +-- existing local hydraulic structures
        +-- survey / cross-section / gauge evidence when available
        |
        v
MASTER WATER INVENTORY
        |
        +-- river / stream / canal
        +-- lake / reservoir / pond
        +-- wetland / floodplain water
        +-- estuary / tidal river
        +-- marine / ocean
        +-- unknown / review-required
        |
        v
FULL HYDROGRAPHIC GRAPH
        |
        +-- connected reaches
        +-- confluences
        +-- structures
        +-- outlets
        +-- upstream area / stream order
        |
        v
REACH-SCALE GEOMETRY
        |
        +-- width
        +-- bank elevation
        +-- bed depth
        +-- longitudinal slope
        +-- uncertainty class
        |
        +---------------------+
        |                     |
        v                     v
DEM_HYDRO_CONDITIONED   DEM_HYDRAULIC_BED
        |                     |
        +----------+----------+
                   v
             QA + SENSITIVITY
                   |
                   v
             BG_Flood pair runs
```

## 4. Phase plan

### Phase V49-A — Inventory and coverage audit

Goal: establish what water exists in the whole raster domain before changing any elevation.

Tasks:

1. Build a `master_water_evidence` raster/table from all available local layers:
   - JRC Global Surface Water occurrence.
   - HydroRIVERS distance/vector data already present under `V46_inputs` / `V46_dryrun_20260930`.
   - OSM waterway-distance raster already used by V48.
   - Copernicus Water Body Mask if it can be obtained for the exact source tiles.
   - Existing project masks, reservoirs, canals, structure locations and coast boundary.
2. Detect connected water objects at multiple persistence thresholds rather than one global JRC threshold.
3. Distinguish ocean-connected water from inland water before calculating coverage percentages.
4. Produce a spatial inventory with one row per object/reach and explicit source evidence.
5. Flag every object not represented by the present five-branch network.

Required outputs:

- `V49_master_water_inventory.gpkg` or GeoJSON/Parquet equivalent.
- `V49_water_object_table.csv`.
- `V49_water_coverage_audit.json`.
- `V49_water_coverage_map.png`.

Acceptance gate A:

- 100% of persistent water objects above the agreed minimum mapping size are classified or explicitly marked `REVIEW_REQUIRED`.
- No object silently disappears because it is outside one of the five existing branch bounding boxes.
- Ocean area is excluded from inland coverage statistics.

### Phase V49-B — Full hydrographic graph

Goal: replace manual start/end routing with a domain-wide directed hydrographic graph.

Tasks:

1. Use HydroRIVERS/OSM plus DEM/JRC evidence to construct candidate river reaches.
2. Snap and split reaches at confluences, bifurcations, structures and model boundaries.
3. Assign stable `reach_id`, upstream/downstream node IDs, stream order and contributing area when available.
4. Preserve known hydraulic control structures such as Đồng Cam as first-class graph objects instead of rectangle-only raster exceptions.
5. Validate connectivity against observed persistent-water corridors and DEM valleys.

No reach is allowed to be accepted merely because Dijkstra found a path between two hard-coded points.

Acceptance gate B:

- zero orphan major reaches;
- zero unexplained loops in gravity-driven inland network;
- every mapped river/canal reach has a downstream target or explicit terminal type;
- all confluences are topologically consistent (incoming reaches terminate at the same explicit junction node used by the downstream reach);
- known structures are represented explicitly.

Scientific note: V49-B is a hydrographic-topology phase and does not yet have a defensible channel-bed elevation for every reach. Bed-elevation ordering at confluences is therefore intentionally not certified in Gate B. Copernicus water-surface DEM values must not be treated as river-bed bathymetry merely to satisfy a topology gate. Physical bed-elevation consistency is checked after V49-D reach geometry and V49-E hydraulic-bed synthesis exist.

### Phase V49-C — Water-body classification

Goal: prevent the river-carving algorithm from being applied indiscriminately to all surface water.

Required classes and treatment:

| Class | V49 treatment |
|---|---|
| River / stream | reach-scale channel bathymetry |
| Canal | engineered or constrained channel geometry |
| Lake / reservoir | stage-area-volume or available bathymetry; synthetic basin only with explicit uncertainty |
| Wetland | preserve storage/micro-topography; do not convert to a river trench |
| Estuary / tidal river | river geometry merged with tidal/marine boundary treatment |
| Ocean | external bathymetry/boundary treatment; never river-depth formula |
| Unknown | no automatic destructive carving; review queue |

Acceptance gate C: every modified water pixel is linked to a water class and a documented treatment rule.

### Phase V49-D — Reach-scale geometry estimation

Goal: remove fixed `d_max` values as the principal source of bathymetry.

For each river reach estimate and store:

- representative width;
- bank elevation or bankfull stage;
- longitudinal slope;
- bankfull/design discharge where evidence exists;
- Manning roughness range;
- depth estimate;
- source/provenance;
- uncertainty band.

Depth hierarchy:

1. surveyed cross-section / bathymetry;
2. verified local hydraulic studies;
3. observed stage/discharge constraints;
4. Manning/GVF inversion using width, slope and design/bankfull discharge;
5. regional hydraulic-geometry power law as fallback.

The existing constants `3.50 m`, `2.25 m`, and `1.20 m` become priors/test references, not unconditional truth.

Minimum sensitivity envelope for inferred river depth:

- LOW: `0.70 * D_est`
- CENTRAL: `1.00 * D_est`
- HIGH: `1.30 * D_est`

Wider bands are required where evidence quality is poor.

Acceptance gate D:

- every carved reach has a depth source and uncertainty class;
- no large reach receives a depth solely from its branch name;
- reported width/depth distributions are physically reviewed for outliers.
- every confluence has an explicit preliminary bed-elevation state and any apparent downstream bed inversion is either resolved or flagged with a documented hydraulic-control explanation (weir, reservoir, tidal/backwater, survey constraint, or other defensible evidence).

### Phase V49-C.1 — Fixed-water evidence audit

Goal: re-check V49-C water-object interpretation with independent current/long-term water evidence before any destructive V49-E synthesis.

Evidence groups:

- JRC Global Surface Water occurrence, recurrence and transitions as long-term 1984–2024 evidence;
- JRC 2024 seasonality as recent-year context;
- current Geofabrik/OpenStreetMap waterway, lake/reservoir/lagoon, intermittent, tidal and dam/weir evidence;
- HydroRIVERS/V49-B topology and the V49-D reach/object association.

Required object states are `CONFIRMED_PERSISTENT`, `SEASONAL_DYNAMIC`, `CONFLICT_REVIEW_REQUIRED`, and `INSUFFICIENT_EVIDENCE`.

Acceptance gate C.1:

- no DEM edits;
- C.1 may only retain or revoke V49-D authorization and may never promote a V49-D review row;
- every V49-E-authorized reach is associated only with `CONFIRMED_PERSISTENT` objects;
- standing-water conflicts such as reservoir/lake/lagoon overlap block automatic river carving;
- absence of JRC detection by itself is never used as proof that a mapped/topological river is absent;
- every conflict/insufficient object appears in the explicit C.1 review queue.

### Phase V49-E — Hydraulic-bed synthesis

Goal: create a continuous 2D bed for BG_Flood without inventing arbitrary sinks or cliffs.

Automatic input authorization requires both the V49-D geometry gate and the V49-C.1 fixed-water gate. V49-E must read `V49_C1_v49e_reach_gate.csv` / the `v49e_reach_gate` layer and modify only rows where `c1_authorized_for_v49e = True`.

Reuse from the current project where still valid:

- raised-cosine lateral blending concept;
- thalweg-to-2D coupling;
- infrastructure protection masks;
- confluence handling framework;
- raster export code;
- invariance checks outside authorized modification zones.

Replace or generalize:

- five hard-coded branches;
- branch bounding boxes;
- hard-coded route start/end cells;
- fixed depth per named branch;
- fixed artificial ocean outlet elevations;
- unconditional strict monotonic lowering over long reaches.

Longitudinal correction must preserve real hydraulic controls. Natural/engineered backwater controls, weirs, reservoirs and tidal reaches cannot be erased simply to satisfy `dz/ds < 0` everywhere.

Acceptance gate E:

- no unexplained bed discontinuity at reach junctions;
- all confluences pass final hydraulic bed-elevation ordering after applying explicit structure/tidal/reservoir exceptions; no global monotonic filter may erase a real hydraulic control merely to make the ordering check pass;
- no carving outside authorized class/reach masks;
- no protected structure is modified;
- modification volume is reported by reach and water class;
- every forced longitudinal adjustment is traceable.

### Phase V49-F — QA/QC that tests coverage and science, not only implementation

The current micro-benchmarks remain useful but are insufficient. Add these V49 checks:

1. Water-object coverage percentage by class.
2. Major persistent-water objects omitted from hydraulic representation.
3. Reach graph orphan count.
4. Reach graph loop count and explanation.
5. Confluence elevation inconsistency count.
6. Width and depth percentile distributions by Strahler/order class.
7. Maximum and percentile incision depth by reach.
8. Added storage by reach and class.
9. Bed adjustment caused by monotonic/conditioning correction versus initial estimated bed.
10. Fraction of geometry from survey / hydraulic inversion / empirical fallback.
11. Sensitivity of modeled flood extent, WSE, velocity and timing to bathymetry uncertainty.

Important: a large added channel-storage number is not an acceptance target. V49 must never deepen channels simply to meet a required storage volume.

Acceptance gate F:

- no target such as `DeltaV > 140M m3` may be used as proof of physical correctness;
- no test may certify an assumed depth by checking only that the raster contains that assumed depth;
- uncertainty and coverage metrics must be reported alongside geometry QA.

### Phase V49-G — Hydraulic validation

Goal: determine whether V49 actually improves the flood model.

Run matched BG_Flood experiments with identical forcing/configuration:

1. V48 BASE Copernicus DEM.
2. Current five-branch bathymetry DEM (diagnostic legacy comparison).
3. V49 CENTRAL hydraulic DEM.
4. V49 LOW depth sensitivity.
5. V49 HIGH depth sensitivity.

Compare against independent observations where available:

- Sentinel-1 flood extent;
- gauge water levels and timing;
- surveyed/high-water marks;
- known inundation/non-inundation locations;
- hydraulic behavior at Đồng Cam and river mouths.

Metrics:

- CSI / F1 / precision / recall for flood extent;
- WSE bias / MAE / RMSE at valid observation points;
- arrival time error;
- peak timing error;
- velocity sanity checks;
- mass-balance error.

Acceptance gate G: V49 is promoted only if central/sensitivity runs show physically plausible behavior and measurable improvement or at least no material degradation against independent observations.

## 5. Immediate code changes planned

Create new V49 modules rather than extending hard-coded branch logic inside `river_network_extractor.py`:

```text
v49_build_water_inventory.py
v49_classify_water_objects.py
v49_build_hydrograph.py
v49_estimate_reach_geometry.py
v49_build_hydraulic_dem.py
v49_build_hydro_conditioned_dem.py
v49_validate_coverage.py
v49_validate_geometry.py
v49_run_bathymetry_sensitivity.py
```

Keep the current V48/river-bathymetry files unchanged as a reproducible legacy baseline until V49 passes all gates.

## 6. Data still needed or worth obtaining

Highest priority:

1. Copernicus Water Body Mask matching the exact GLO-30 tiles used for the base DEM.
2. Local/official river centerlines and water-body polygons if available.
3. Cross-sections, longitudinal profiles or surveyed bathymetry from hydraulic studies.
4. Reliable discharge/stage information usable for Manning/GVF constraints.
5. Reservoir/lake level-area-volume information for major impoundments.
6. Coastal/estuarine bathymetry for the model boundary where river formulas are inappropriate.

V49 must record missing data explicitly instead of silently replacing it with a precise-looking synthetic value.

## 7. Stop conditions

Do not promote a V49 hydraulic DEM if any of the following remain true:

- substantial persistent inland-water objects are unclassified;
- major river reaches are missing from the graph;
- reach geometry has no documented source/uncertainty;
- an algorithm forces a river through implausible high terrain without independent hydrographic evidence;
- reservoirs/lakes are treated as ordinary river trenches;
- bathymetry quality is justified mainly by self-consistency tests;
- sensitivity to plausible bathymetry uncertainty is large but unreported;
- the new DEM has not been tested in matched BG_Flood runs against independent observations.

## 8. Recommended next executable milestone

Implement **V49-A only first**. It is read-only with respect to DEM elevation and answers the key question before any new carving:

> What persistent inland surface-water objects and hydrographic reaches exist in the 2100 x 2100 domain, which are already represented by the five-branch model, and which are missing?

Only after that inventory is reviewed should V49-B through V49-E modify terrain.

## 9. Implementation status — 2026-10-12

### V49-A — PASS

Inventory/coverage audit is implemented and independently validated.

- 80 qualifying inland-water objects plus one explicit ocean object;
- 113.8572 km2 qualifying inland-water area after marine separation;
- V48 five-branch corridor covers 32.8752 km2 (28.8741%);
- 80.9820 km2 (71.1259%) of qualifying inland-water pixels lies outside the V48 corridor;
- source Copernicus DEM SHA-256 unchanged.

Report: `V49_A_IMPLEMENTATION_REPORT_20261012.md`.

### V49-B — PASS (topology only)

The directed hydrographic graph is implemented and independently validated.

- 370 reaches;
- 396 nodes;
- 168 confluences;
- 53 major reaches;
- zero orphan major reaches;
- zero directed cycles;
- zero unresolved terminals;
- zero endpoint gaps over 120 m;
- Đồng Cam represented explicitly as a structure node;
- bed-elevation ordering remains intentionally deferred to V49-D/E.

Report: `V49_B_IMPLEMENTATION_REPORT_20261012.md`.

### V49-C — PASS

All 81 V49-A water objects now have a final class, confidence, evidence summary and documented treatment rule. V49-C makes no terrain edits.

- 33 `RIVER_STREAM`;
- 3 `ESTUARY_TIDAL_RIVER`;
- 1 `LAKE_RESERVOIR`;
- 1 `WETLAND_FLOODPLAIN_WATER`;
- 1 `OCEAN`;
- 42 `UNKNOWN_REVIEW_REQUIRED`, all mapped to `NO_AUTOMATIC_CARVING`;
- 0 automatically accepted `CANAL` objects because independent object-scale evidence was insufficient;
- source Copernicus DEM SHA-256 remains `0c3c6ca6f299b00dd22a91a26c66e8c784f0e70c445412216f01efdd76504508`.

Gate C validator: **PASS**. Report: `V49_C_IMPLEMENTATION_REPORT_20261012.md`.

### V49-D — PASS (conservative geometry gate)

Reach-scale hydraulic geometry is implemented and independently validated without editing the source DEM.

- 370 graph reaches retained in the geometry table;
- 95 reaches intersect/associate with V49-C channel-eligible objects;
- only 3 fluvial reaches currently meet the conservative direct-width evidence rule for candidate V49-E use;
- 28 additional fluvial reaches remain review-only because their width evidence is indirect or morphologically ambiguous;
- 64 tidal/backwater-associated reaches remain review-only pending GVF/marine-boundary evidence;
- 2 legacy canal candidates remain review-only because V49-C accepted no canal class;
- legacy fixed depths `3.50 / 2.25 / 1.20 m` are not used as the principal bathymetry source;
- all 168 confluences have an explicit preliminary bed state; no unexplained inversion exists among fully authorized incident reaches;
- Đồng Cam remains an explicit hydraulic-control exception;
- source Copernicus DEM SHA-256 remains `0c3c6ca6f299b00dd22a91a26c66e8c784f0e70c445412216f01efdd76504508` and V49-D modifies zero DEM pixels.

The pass is deliberately narrow: it certifies the traceability and uncertainty handling of the geometry candidates, not that all river/tidal reaches now have survey-grade bathymetry. Weak width evidence is kept in `V49_D_review_queue.csv` rather than forced green.

Gate D validator: **PASS**. Report: `V49_D_IMPLEMENTATION_REPORT_20261012.md`.

### V49-C.1 — PASS (fixed-water evidence gate)

All 81 V49-C water objects were cross-checked against JRC Global Surface Water, the 2026-10-11 Geofabrik Vietnam snapshot, and V49-B/V49-D topology without modifying the DEM.

- 17 `CONFIRMED_PERSISTENT`;
- 6 `SEASONAL_DYNAMIC`;
- 16 `CONFLICT_REVIEW_REQUIRED`;
- 42 `INSUFFICIENT_EVIDENCE`;
- 58 objects are in the explicit C.1 review queue;
- 7 Priority-1 objects previously classified `RIVER_STREAM` strongly overlap current OSM lake/reservoir polygons and are blocked from automatic river carving;
- V49-D authorized 3 candidate reaches; C.1 retains only `HR_41349822` and `HR_41352752`;
- `HR_41349985` is blocked because associated `W20_0064` is current Hồ Hóc Răm reservoir evidence (~98.53% overlap, ~148.25 m dam/weir evidence);
- C.1 promotes zero V49-D review rows;
- source Copernicus DEM SHA-256 remains `0c3c6ca6f299b00dd22a91a26c66e8c784f0e70c445412216f01efdd76504508` and C.1 modifies zero DEM pixels.

Gate C.1 validator: **PASS**. Report: `V49_C1_IMPLEMENTATION_REPORT_20261012.md`.

Next executable phase: **V49-E — hydraulic-bed synthesis**. With the current evidence, V49-E may automatically synthesize only `HR_41349822` and `HR_41352752`, and must consume the C.1 gate rather than the older V49-D authorization list alone. All other reaches remain excluded from automatic carving until their required evidence/control treatment is resolved.

### V49-E — PASS (conservative hydraulic-bed synthesis)

V49-E is implemented and independently validated.  Automatic synthesis consumes the strict V49-C.1 ∩ V49-D authorization set and currently modifies only `HR_41349822` and `HR_41352752`.

The accepted implementation is deliberately narrower than a full HydroRIVERS corridor carve: within each admitted reach it modifies only cells that also overlap the associated C.1 `CONFIRMED_PERSISTENT` water-object polygons.  This avoids unsupported carving through dry/intervening terrain.  The hydraulic lowering uses the V49-D reach depth with a raised-cosine lateral taper over the local DEM/water-surface proxy; no named-branch fixed depth, hard-coded route, artificial ocean outlet, or global monotonic filter is used.

- authorized reaches: 2;
- authorized mask cells: 73;
- effective modified cells: 72;
- total lowering volume: 8,008.2092 m3;
- maximum lowering: 0.3742065 m;
- modified cells outside authorized reach/class mask: 0;
- protected Đồng Cam cells modified: 0 / 187;
- unexplained confluence bed inversions in admitted scope: 0;
- forced longitudinal adjustments: 0;
- source Copernicus DEM SHA-256 remains `0c3c6ca6f299b00dd22a91a26c66e8c784f0e70c445412216f01efdd76504508`.

Gate E validator: **PASS**. Report: `V49_E_IMPLEMENTATION_REPORT_20261012.md`. Outputs: `V49_E_20261012`.

Next executable phase: **V49-F — coverage/science QA/QC**. V49-E PASS certifies only the currently evidence-authorized subset; it does not imply that the remaining review-only river, tidal, canal, reservoir, wetland, lagoon, or ocean objects now have complete bathymetry.

### V49-F — PASS (coverage/science QA/QC; hydraulic promotion still blocked)

V49-F is implemented and independently validated as a read-only science/coverage audit over the accepted A/B/C/C.1/D/E lineage.

- 80 qualifying inland-water objects cover 113.8572 km2;
- current V49-E represents 3 / 80 inland objects (3.75%);
- represented object area is 0.1638 km2, or 0.143864% of qualifying inland-water area;
- actual V49-E modified raster footprint is 0.0648 km2;
- 5 major `CONFIRMED_PERSISTENT` inland objects remain without accepted V49-E hydraulic representation;
- graph orphan major reaches: 0;
- directed cycles: 0;
- unresolved V49-E confluence inconsistencies: 0;
- V49-C-eligible geometry provenance is 0.0% survey/observed, 7.3684% hydraulic inversion, 90.5263% empirical fallback, and 2.1053% unresolved;
- V49-E admitted reaches retain `HIGH` / `VERY_HIGH` uncertainty;
- no minimum storage-volume target is used;
- no assumed depth is certified solely because the output raster reproduces it;
- source Copernicus DEM SHA-256 remains `0c3c6ca6f299b00dd22a91a26c66e8c784f0e70c445412216f01efdd76504508`.

Gate F PASS means the required QA/QC reporting is complete and exposes the unresolved science honestly. It does **not** mean the current hydraulic DEM is ready for promotion. Matched V49 LOW/CENTRAL/HIGH BG_Flood sensitivity metrics are explicitly `PENDING_V49_G_MATCHED_BG_FLOOD_RUNS`, and `hydraulic_promotion_ready = false`.

Report: `V49_F_IMPLEMENTATION_REPORT_20261013.md`. Outputs: `V49_F_20261013`.

### V49-G — PREPARED / PENDING MATCHED BG_Flood RUNS

V49-G experiment preparation is complete for the formal matched comparison **BASE / CENTRAL / LOW / HIGH** under the frozen V48 R1 runtime and `minmask=-4.0` contract.

- LOW/CENTRAL/HIGH preserve the same V49-E authorized spatial mask and satisfy LOW <= CENTRAL <= HIGH lowering everywhere within tolerance;
- comparable terrain grids are identical at 2100 × 2100, EPSG:32649, and contain zero valid cells <= -4.0 m;
- the four normalized BG_Flood configs are identical except terrain/output path;
- the historical five-branch DEM is retained as diagnostic-only because 10,740 valid cells are <= -4.0 m, so treating it as a canonical matched arm would change the modeled domain;
- the frozen Sentinel-1 comparison and BASE frame-33 metrics are recorded;
- no verified local gauge/WSE series with timestamp + datum + lineage is available, so WSE/timing metrics are not fabricated;
- CENTRAL/LOW/HIGH NetCDF results are not yet present;
- `preparation_pass = true`, `gate_g_pass = false`, `hydraulic_promotion_ready = false`.

Independent validator: `v49_validate_hydraulic_validation.py`.

Report: `V49_G_IMPLEMENTATION_REPORT_20261013.md`. Outputs: `V49_G_20261013`.

Next executable action: run the prepared **CENTRAL / LOW / HIGH** BG_Flood cases under the frozen V48 R1 runtime, apply the preregistered Sentinel-1 evaluation consistently, then review matched flood-extent, velocity, mass-balance and any defensible hydraulic-observation evidence before deciding Gate G.

## 10. R2 remediation snapshot — 2026-10-13, superseded by section 11

The current authoritative implementation audit is [V49_ALL_PHASE_AUDIT_20261013.json](D:/VTP/River_Bathymetry_Project/V49_ALL_PHASE_AUDIT_20261013.json). All 11 implementation/integrity checks pass; the complete V49 regression suite has **92 passed**. Scientific full-domain completion and hydraulic promotion remain false.

| Workstream | Current evidence and remaining work |
|---|---|
| A/B | Preserve 80 inland objects, 370 reaches and original topology; current 30/90 m QA identifies 4 channel/candidate objects lacking nearby graph plus 1 alignment review. Seven OSM edge candidates are review-only. |
| C/C.1 R2 | 18 class revisions; UNKNOWN 42→32, review queue 58→43. Standing-water tags alone do not authorize persistent-water carving. |
| D/E R2 | Reject unsupported uphill profiles before authorization. Only 2 reaches remain admitted; E R2 and original E have identical SHA-256, 72 modified cells and 8,008.2092 m³ lowering. Survey-derived geometry remains 0%. |
| F R2 | Report current coverage, provenance, actual raster confluences and 9 major persistent omissions. Preserve historical B counts separately from current object classifications/alignment. |
| HydroDEM | Separate drainage-only float64 product; saved D8/accumulation independently read back across 4,410,000 cells with no cycles or unresolved internal cells. Not a hydraulic bed. |
| Published evidence | Eight pinned source PDFs, six output tables: 2 ZFW curves, 6 capacity references, 8 relative map locations, 3 reported peaks and coarse flood marks. Source conflicts, datum, full footprint, event timing and survey limitations remain explicit. |
| G execution | Hidden supervisor already runs CENTRAL → LOW → HIGH → BASE, one CUDA job at a time. A new BASE completes the frozen 120 h window; historical BASE ends at 105 h. Completed arms are evaluated automatically; active NetCDF files are not read. |

The frozen G configs, runtime, forcing, SAR contract and terrain remain unchanged. Numerical observer budget and coarse high-water-mark diagnostics supplement the experiment without authorizing scientific promotion. Graph candidates and catalogue coordinates do not authorize terrain changes.

Outstanding scientific acceptance: resolve 32 unknown classes, 43 persistence reviews, graph gaps/alignment and geometry coverage; verify reservoir footprint/datum/dated operation, hydrometric/survey locations and event-window conflicts; finish and assess matched hydraulic runs. Only an explicit evidence-based acceptance decision can change Gate G or `hydraulic_promotion_ready`.

Read live state with `v49_run_hydraulic_validation.py status`; refresh all phase checks with `v49_audit_all_phases.py`. Both commands can run while the sequential supervisor remains active. The supervisor preserves partial failures but does not yet resume an interrupted run from checkpoint.

The GPU driver reports thermal throttling at approximately 93–94°C. A reversible 110 W power-cap attempt was rejected for insufficient host permissions; no hardware setting changed. See `V49_G_HARDWARE_HEALTH_20261013.json` for the operational snapshot and cooling/admin action still needed.

## 11. Current R3 remediation — 2026-10-13

[Current report](D:/VTP/River_Bathymetry_Project/V49_R3_UNPASSED_REMEDIATION_20261013.md) and [all-phase audit](D:/VTP/River_Bathymetry_Project/V49_ALL_PHASE_AUDIT_20261013.json): **15/15 implementation/integrity checks PASS, 102/102 tests PASS**. The default audit uses `V49_R3_20261013`; historical R2 products are preserved.

- Connected-parent geometry corroboration resolves three fragment types: W20_0034 as river, W20_0050/W20_0052 as coastal-channel review. UNKNOWN 32→29. Support from a disconnected OSM component cannot authorize reclassification.
- C/D/C.1/E/F rebuilt and validated in R3. C.1 remains 43 reviews (37 insufficient, 6 conflict), with 28 confirmed and 10 seasonal; no additional geometry authorization. E R3 remains byte-identical to original/R2.
- Twelve original JRC MonthlyHistory 2021 tiles are pinned and read back, yielding 972 object/month rows. FTP VER5-0 is the older GSW v1.4 archive; corrected v1.5 annual assets are not falsely claimed. No-observation remains distinct from observed dry cells. November has 24/80 inland objects with no usable observations.
- Seven new research sources are pinned: five PDFs, one archive, one official station-map HTML. Signed Phu Sen survey drawings support a seven-corner footprint and eleven collar-height records from January 2024. Paired VN-2000 3-degree/6-degree coordinates verify EPSG:9218/3406, with maximum residual 0.0061 m. The sandbar footprint does not overlap current inventory water polygons, and no vertical-datum tie or 2021 wetted-channel bathymetry is established.
- Current graph QA explicitly lists seven objects without support within 90 m and one alignment review; seven OSM edge candidates remain unaccepted. Nine major persistent geometry omissions remain.
- CENTRAL continues; LOW/HIGH/BASE 120 h remain queued. A snapshot at 18:43 UTC+7 showed 15.34% completion for CENTRAL; use live execution JSON for current progress.

Scientific full-domain completion and Gate G remain false/pending. Required raw 2021 station series with datum and surveyed/inverted geometry have not been obtained through the inspected public sources. Source retrieval, test PASS and reviewed bar drawings do not replace those observations or complete the hydraulic runs.


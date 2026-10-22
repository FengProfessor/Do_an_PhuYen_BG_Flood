# V46 — High-priority evidence gaps before thesis freeze (2026-10-01)

Scope: hydrological conditioning / vertical accuracy, pre-event OSM/JRC limits, D8 topology classes, corridor sensitivity and the 407-cell claim. Sentinel-1 2021 is excluded from edit selection.

## 1. Vertical accuracy/provenance is the highest-priority unresolved claim

- Local lineage proves that V41 is strongly processed: V39 Safe -> negative clipping -> Priority-Flood -> a global eastward epsilon slope of 0.001 m/cell. The existing audit reports 4,407,900/4,410,000 cells changed by >0.001 m, median +1.088 m, maximum +31.497 m, and an east-west gradient range of ~2.099 m.
- `PhuYen_DEM_30m_V46.prj` preserves only the horizontal WGS84/UTM 49N CRS; it does not encode a vertical CRS/datum. `PROJECT.md` describes Copernicus GLO-30 as the intended source, but the current artifact chain does not independently prove that V39/V41 is pixel-traceable to the official product.
- The official Copernicus DEM specification states that the product is a DSM, uses EGM2008 (EPSG:3855) vertically, and has absolute vertical accuracy <4 m LE90. Those specifications can only be inherited by the thesis after source lineage is demonstrated; they do not validate V41/V46 after Priority-Flood, epsilon slope, or V46 cuts.
- Therefore V46 can be defended as a conditioned routing surface, not as a DEM with improved physical vertical accuracy.

Follow-up with existing data: reconstruct hashes/pixel differences for `PhuYen_DEM_30m.tif -> V39 -> V41`; inspect original GeoTIFF vertical metadata; compare against archived Copernicus/ALOS/SRTM/FABDEM only as consistency checks. Without surveyed/GNSS/benchmark elevations, state physical vertical accuracy as unvalidated.

Sources: Copernicus DEM Product Handbook / Data Space (EGM2008, accuracy, DSM); Callow et al. (2007), DOI 10.1016/j.jhydrol.2006.06.020; Lindsay (2016), DOI 10.1002/esp.3888.

## 2. D8 evidence is not independent of the V41 conditioning

- `v46_build_hydro_evidence.py` derives filled elevation, D8, upstream area and HAND from V41. V41 already contains Priority-Flood and the imposed eastward epsilon slope. Thus D8/upstream-area/HAND are internally consistent routing diagnostics, not independent observations that prove a physical obstruction or culvert exists.
- `v46_topology_paths.py` searches anchors within four cells and picks a directly connected D8 pair; all 24/24 seed components obtaining `DIRECT_D8_TRACE` should therefore be interpreted as algorithmic consistency. Current selected anchor offsets reach two cells and D8 traces reach nine steps.
- D8 itself constrains flow to eight directions; Tarboton (1997) explicitly identifies grid bias from this restriction.
- The strict/bounded/reject classes are threshold classes. There is no separate manual-review artifact for the 15 `REVIEW_APPROVE_BOUNDED` components.

Existing-table sensitivity is material: holding other gates fixed, passing components increase from 1 at cut<=1.0 m / <=4 cells, to 7 at 1.25 m, 10 at 1.5 m / <=8 cells, 12 at 2.0 m / <=8, 13 at 2.5 m / <=8, and 16 at the current 3.0 m / <=8. The bounded set therefore depends strongly on the chosen cut cap.

Follow-up without Sentinel-1: regenerate routing evidence from V39 before the V41 epsilon slope, compare V39-vs-V41 anchor pairs/D8 paths/class transitions, and test an alternative routing direction method (D-infinity or MFD if available). Prefer edits that persist across these routing variants and predeclared cut caps.

Source: Tarboton (1997), DOI 10.1029/96WR03137.

## 3. The “407 stable cells” claim is mainly a nested-corridor boundary result

- Strict/base/wide Tier-A sets are nested (`strict_not_in_base=0`, `base_not_in_wide=0`), so their intersection is mathematically the strict set: 407 cells. This is corridor persistence only; it is not robustness to terrain thresholds, rasterization, flow algorithm, hydrography source, or topology rules.
- Among the 407 strict Tier-A cells, 316 (77.6%) are exactly 30 m from the rasterized OSM network, the inclusive strict boundary; 66 (16.2%) are exactly 60 m from HydroRIVERS, its strict boundary.
- `v46_conditioning_dryrun.py` rasterizes both networks with `all_touched=True`. Rasterio documents that this burns every pixel touched by a geometry, whereas the default uses centers/Bresenham selection. Thus the 407 count is sensitive to the vector-to-grid rule as well as to corridor width.
- Terrain thresholds were not varied: 174/407 cells have relief <1.5 m and 263/407 have relief <2 m, while the current gate is >=1 m. The 407 cells also form 151 components, including 76 singletons; they should not be described as 407 verified physical obstructions.

Follow-up without Sentinel-1: run a predeclared grid across OSM corridor (0/15/30/45/60 m), HydroRIVERS corridor (30/45/60/90 m), `all_touched` true/false, relief threshold (1/1.25/1.5/2 m), slope (3/4/5 deg) and max elevation (10/15/20 m). Report persistence by component as well as cell. A cleaner variant is direct vector-to-cell-center distance, avoiding distance to an already rasterized network.

Sources: Rasterio 1.4.4 official `rasterize` documentation; Lindsay (2016), DOI 10.1002/esp.3888.

## 4. Pre-event OSM timestamp is valid, but completeness/feature scope is not validated

- Overpass `[date:...]` does reconstruct the OSM database state at the requested historical time, so the 2021-11-25 snapshot timing claim is defensible.
- It does not prove that mapped waterways were complete or positionally correct in Phu Yen at that date. OSM itself documents that accuracy/completeness vary and may be difficult to measure.
- The V46 query includes `river|stream|canal|drain` but excludes `waterway=ditch`. OSM defines ditches as small artificial drainage waterways often found along roads/agricultural fields and potentially connected through culverts. This is relevant to a conditioning workflow seeking local drainage barriers.
- HydroRIVERS cannot close this gap: its official network is derived from 15-arc-second HydroSHEDS and starts streams at >=10 km2 catchment area or >=0.1 m3/s average flow; smaller channels are intentionally omitted because their spatial representation is less reliable.

Follow-up with existing files: audit connectivity, endpoints, names/tags and `tunnel=culvert`/crossing attributes in the saved historical OSM XML; quantify where 407/55 components depend on a single short/unnamed way. If new historical OSM retrieval is allowed, repeat the same cutoff query including `ditch`; otherwise state ditch/small-drain completeness as an unresolved limitation.

Sources: OpenStreetMap Overpass QL date docs; OSM Limitations and `waterway=ditch` docs; HydroRIVERS Technical Documentation v1.0.

## 5. JRC v1.3 should be weak auxiliary evidence, not a validation target

- JRC Surface Water Occurrence measures frequency of open surface-water detection, not bathymetry, channel-bed elevation or a required DEM cut.
- JRC states that the precision of occurrence depends on the number of valid observations, which varies by cloud/acquisition conditions; the metadata product provides water detections and valid-observation counts.
- JRC now documents that Occurrence versions v1.2-v1.4 processed the added years inconsistently with the v1.0 baseline; the corrected Occurrence is in v1.5. This materially limits the evidentiary strength of the local v1.3 raster.
- In V46, only 2/24 topology components meet JRC>=25%; 19/24 meet upstream-area>=0.5 km2. JRC therefore rarely drives the gate. Among the 38 applied cells, 34 have JRC buffer maximum 0% and four have 43%.

Follow-up without Sentinel-1: add/use the matching JRC v1.3 metadata layer if available and report valid-observation counts alongside occurrence; rerun the gate with JRC treated as a confidence-weighted auxiliary signal. Do not interpret `occurrence=0` as evidence that a cut is false without adequate observation support.

Sources: JRC Global Surface Water Data Access/FAQ and metadata documentation; Pekel et al. (2016), DOI 10.1038/nature20584.

## Recommended thesis freeze rule

Select edits using only pre-SAR evidence: historical OSM + HydroRIVERS + terrain threshold persistence + routing stability across V39/V41 and alternative flow directions + JRC as weak metadata-aware support. Freeze rules and the selected component list before any Sentinel-1 2021 score is computed. Keep strict/bounded/reject labels explicitly algorithmic unless a separate expert review record is created.

### Primary / official sources

- Copernicus DEM: https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM
- Copernicus DEM Product Handbook: https://dataspace.copernicus.eu/sites/default/files/media/files/2024-06/geo1988-copernicusdem-spe-002_producthandbook_i5.0.pdf
- JRC Global Surface Water Data Access: https://global-surface-water.appspot.com/download
- JRC Global Surface Water FAQ: https://global-surface-water.appspot.com/faq
- HydroRIVERS Technical Documentation v1.0: https://data.hydrosheds.org/file/technical-documentation/HydroRIVERS_TechDoc_v10.pdf
- OpenStreetMap Overpass QL date: https://wiki.openstreetmap.org/wiki/Overpass_API/Overpass_QL#Date
- OpenStreetMap limitations: https://wiki.openstreetmap.org/wiki/Limitations
- OpenStreetMap `waterway=ditch`: https://wiki.openstreetmap.org/wiki/Tag:waterway%3Dditch
- Rasterio rasterization: https://rasterio.readthedocs.io/en/stable/topics/features.html
- Tarboton (1997): https://doi.org/10.1029/96WR03137
- Lindsay (2016): https://doi.org/10.1002/esp.3888
- Callow et al. (2007): https://doi.org/10.1016/j.jhydrol.2006.06.020
- Pekel et al. (2016): https://doi.org/10.1038/nature20584

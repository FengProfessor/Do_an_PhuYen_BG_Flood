# V49 Hydro-Bathymetry Conditioning — Primary-source research synthesis

**Project:** `D:\VTP\River_Bathymetry_Project`  
**Date:** 2026-10-12  
**Scope:** independent research using only primary papers, official project documentation, and first-party product documentation. No production code was modified.

## Executive technical conclusions

1. **Arc Hydro DEM Reconditioning / AGREE is a hydrography-conditioning procedure, not a bathymetry reconstruction method.** It lowers raster elevations along a supplied stream network using a smooth buffered drop plus an optional additional sharp drop. The documented workflow then uses the reconditioned/filled DEM for flow direction and flow accumulation. HEC-GeoHMS explicitly instructs users to switch back to the original, unmodified DEM when extracting elevations for slope-related basin characteristics. This is incompatible with treating an AGREE-burned channel as a physically observed river bed. Sources: [HEC-GeoHMS User's Manual 10.1](https://www.hec.usace.army.mil/software/hec-geohms/documentation/HEC-GeoHMS_Users_Manual_10.1.pdf), [HEC-GeoHMS 1.1 User's Manual](https://www.hec.usace.army.mil/software/hec-geohms/documentation/HEC-GeoHMS11.pdf), [Esri Arc Hydro terrain-preprocessing workflow](https://content.esri.com/archydro/archydro/doc/arc%20hydro%20-%20overview%20of%20terrain%20preprocessing%20workflows.pdf).

2. **Copernicus GLO-30 must not be interpreted as river-bed terrain over water.** Copernicus describes the product as a Digital Surface Model (DSM). Its product-generation workflow edits water surfaces, and its Water Body Mask (WBM) explicitly marks Ocean, Lake and River pixels. WBM is therefore useful evidence of where the DEM has been treated as water, but it does not supply bottom elevation. Sources: [Copernicus DEM official collection page](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM), [Copernicus DEM Product Handbook v5.0](https://dataspace.copernicus.eu/sites/default/files/media/files/2024-06/geo1988-copernicusdem-spe-002_producthandbook_i5.0.pdf).

3. **Surface-water detection and river-network topology should be built as separate evidence layers.** JRC Global Surface Water (GSW) is a 30 m Landsat-derived record of open-water presence and persistence; MERIT Hydro and HydroRIVERS are hydrography/topology products. JRC GSW should help answer “where is open surface water and how persistent is it?”, while MERIT Hydro/HydroRIVERS should help answer “how are reaches connected and where is downstream?”. Neither by itself provides surveyed bathymetry. Sources: [Pekel et al. 2016](https://doi.org/10.1038/nature20584), [JRC Global Surface Water FAQ](https://www.global-surface-water.appspot.com/faq), [Yamazaki et al. 2019 MERIT Hydro](https://doi.org/10.1029/2019WR024873), [HydroRIVERS official product page](https://www.hydrosheds.org/products/hydrorivers).

4. **When survey bathymetry is absent, river depth can be estimated, but the method must match the hydraulic regime and the uncertainty must remain explicit.** HydroMT implements three first-party-supported options: discharge-depth power law, Manning-based depth for kinematic conditions, and gradually varying flow (GVF). Neal et al. (2021) show that uniform-flow-derived channel geometry can be strongly biased where backwater/nonuniform flow matters, whereas GVF-based inversion better reproduces target water-surface profiles. Sources: [HydroMT `river_depth` official docs](https://deltares.github.io/hydromt/dev/_generated/hydromt.model.processes.rivers.river_depth.html), [Neal et al. 2021](https://doi.org/10.1029/2020WR028301), [Leopold & Maddock 1953, USGS](https://doi.org/10.3133/pp252), [Andreadis et al. 2013](https://doi.org/10.1002/wrcr.20440).

5. **A 30 m hydraulic grid should not force all rivers to become 30 m-wide raster trenches.** HydroMT-SFINCS moved river bathymetry into subgrid tables specifically so rivers narrower than the model grid cell can be represented. This is directly relevant to V49. Source: [HydroMT-SFINCS changelog](https://deltares.github.io/hydromt_sfincs/latest/changelog.html), [HydroMT-SFINCS `setup_subgrid`](https://deltares.github.io/hydromt_sfincs/v1.2.1/_generated/hydromt_sfincs.SfincsModel.setup_subgrid.html).

6. **River, lake/reservoir, wetland and estuary must not share one “carve depth” rule.** Rivers require connected channel geometry; lakes/reservoirs are storage/water-level systems; wetlands are often floodplain/storage features whose open-water fraction may be incomplete in optical water masks; estuaries are backwater/tidal systems and require coastal topobathymetry plus consistent vertical datums and boundary water levels. The model architecture should therefore classify water type before any topographic modification.

7. **V49 should produce two conceptually distinct products:** (a) a hydrologically conditioned DEM/topology product for drainage extraction and routing logic; and (b) a hydraulic topobathymetry representation, preferably solver-native subgrid channel geometry where supported. Conflating the two would turn arbitrary stream-burning offsets into hydraulic cross sections.

---

## 1. Arc Hydro DEM Reconditioning / AGREE: what it actually does, and what it does not do

### 1.1 Documented operation

The official HEC-GeoHMS implementation of the AGREE concept asks for a raw DEM, a stream layer, a stream-buffer width in cells, a Smooth Drop and a Sharp Drop. The Smooth Drop lowers the stream and interpolates a smooth transition through the buffer; the Sharp Drop is an additional lowering applied at the stream itself. This is a terrain-conditioning operation designed to make the raster drainage structure conform more closely to a known stream network. [HEC-GeoHMS User's Manual 10.1](https://www.hec.usace.army.mil/software/hec-geohms/documentation/HEC-GeoHMS_Users_Manual_10.1.pdf)

Current HEC-HMS terrain-reconditioning documentation describes the same behavior: stream cells are gradually lowered through the buffer and can receive an additional sharp drop at the stream line. The tool is presented as a way to reproduce known stream locations and drainage patterns before hydrologic preprocessing. [HEC-HMS GIS Menu — Terrain Reconditioning](https://www.hec.usace.army.mil/confluence/hmsdocs/hmsum/4.10/geographic-information/gis-menu)

The decisive workflow evidence is in HEC-GeoHMS: after obtaining the reconditioned DEM, the user is instructed to fill sinks and use the resulting DEM for **flow direction and flow accumulation**; before extracting basin characteristics, the manual instructs the user to change the HydroDEM back to the **original DEM** so that correct elevations are used for slope calculations. [HEC-GeoHMS 1.1 User's Manual](https://www.hec.usace.army.mil/software/hec-geohms/documentation/HEC-GeoHMS11.pdf)

### 1.2 What AGREE does not provide

The documented inputs contain no observations of:

- channel-bottom elevation;
- cross-sectional shape or cross-sectional area;
- bankfull depth;
- thalweg survey;
- wetted perimeter;
- stage-area-volume relationship;
- bed material/roughness calibration;
- tidal/backwater controls.

Therefore, **AGREE cannot by itself infer physical bathymetry**. The amount lowered is a conditioning parameter chosen to impose drainage behavior, not a measurement of water depth. This conclusion follows directly from the documented algorithm and from the official HEC-GeoHMS instruction to return to the raw DEM for actual elevation-dependent characterization. [HEC-GeoHMS User's Manual 10.1](https://www.hec.usace.army.mil/software/hec-geohms/documentation/HEC-GeoHMS_Users_Manual_10.1.pdf), [HEC-GeoHMS 1.1 User's Manual](https://www.hec.usace.army.mil/software/hec-geohms/documentation/HEC-GeoHMS11.pdf)

HEC-RAS independently reinforces the distinction between general terrain and actual underwater channel terrain: its official guidance states that terrain datasets often do not contain the actual ground below the water surface, and describes creating channel terrain from cross-section data and merging it with the general surface terrain. [HEC-RAS — Using Cross Section Data to Modify/Improve the Terrain Model](https://www.hec.usace.army.mil/confluence/rasdocs/r2dum/6.0/developing-a-terrain-model-and-geospatial-layers/using-cross-section-data-to-modify-improve-the-terrain-model)

### 1.3 V49 design consequence

**Do not use an AGREE-style burned DEM as `DEM_HYDRAULIC_BED`.** AGREE-like conditioning remains useful for a separate `DEM_HYDRO_CONDITIONED` product used to enforce drainage topology, resolve road/bridge artefacts where justified, generate flow directions and support catchment/network preprocessing. Hydraulic bed geometry needs its own evidence and provenance.

---

## 2. Surface-water evidence and network topology

### 2.1 Copernicus DEM GLO-30 and Water Body Mask

Copernicus identifies the DEM as a **Digital Surface Model**, representing the Earth's surface including vegetation, buildings and infrastructure. GLO-30 is the approximately 30 m global instance. [Copernicus DEM documentation](https://documentation.dataspace.copernicus.eu/Data/Others/CCM.html)

The Copernicus DEM Product Handbook defines the Water Body Mask values as:

| WBM value | Meaning |
|---:|---|
| 0 | No water |
| 1 | Ocean |
| 2 | Lake |
| 3 | River |

The handbook states that the WBM shows DEM pixels classified as water and edited according to those categories. [Copernicus DEM Product Handbook v5.0](https://dataspace.copernicus.eu/sites/default/files/media/files/2024-06/geo1988-copernicusdem-spe-002_producthandbook_i5.0.pdf)

**Use in V49:** WBM should be treated as the most direct first-party indicator of which Copernicus DEM pixels belong to edited water classes. It is ideal for auditing where GLO-30 cannot be assumed to represent dry bare-earth terrain. It should not be interpreted as river-bottom elevation or a complete fine-scale hydrography network.

### 2.2 JRC Global Surface Water

Pekel et al. developed a global surface-water record from more than three million Landsat scenes at 30 m resolution. The products describe where and when water is observed and include metrics such as occurrence and seasonality. [Pekel et al. 2016, Nature](https://doi.org/10.1038/nature20584)

The JRC's official FAQ defines the mapped target as **open water visible from space/open to the sky**, including natural rivers, lakes, coastal margins and wetlands as well as artificial reservoirs and other flooded areas. Water Occurrence is the frequency with which a location is classified as water through the observation record. [JRC Global Surface Water FAQ](https://www.global-surface-water.appspot.com/faq)

**Use in V49:** JRC GSW is a strong complementary detector for observable surface water and persistence. It is particularly useful for finding water pixels beyond a hand-curated set of major rivers. However, water occurrence is not network topology and is not bathymetry. A JRC water pixel does not tell V49 how deep the water is, whether the pixel is a river thalweg or floodplain inundation, or what its downstream neighbor is.

### 2.3 MERIT DEM and MERIT Hydro

MERIT DEM was constructed by removing multiple error components from SRTM/AW3D-derived elevations, including absolute bias, stripe noise, speckle noise and vegetation-related biases. It is a 3 arc-second product (about 90 m at the equator), designed to improve large-scale terrain representation. [Yamazaki et al. 2017](https://doi.org/10.1002/2017GL072874)

MERIT Hydro builds a 3 arc-second global hydrography map from MERIT DEM together with water information including G1WBM, JRC Global Surface Water Occurrence and OpenStreetMap water layers. The paper explicitly uses water layers to mitigate remaining elevation errors and to represent channels that may be smaller than the DEM pixel size. It supplies flow direction, flow accumulation/upstream area, hydrologically adjusted elevation and river-width-related information. [Yamazaki et al. 2019](https://doi.org/10.1029/2019WR024873)

The official MERIT Hydro project page lists limitations that are directly relevant to V49: a single downstream direction per pixel cannot fully represent bifurcating channels; separation of rivers and lakes can require improvement; below-sea-level coastal areas are problematic; underground river/tunnel behavior is not explicitly represented. [MERIT Hydro official project page](https://global-hydrodynamics.github.io/MERIT_Hydro/)

**Use in V49:** MERIT Hydro is a very strong **topology prior**: downstream connectivity, upstream area, drainage direction, approximate centerline position and width support. For the Phú Yên/Vietnam-scale 30 m hydraulic surface, it should not be treated as authoritative local bed elevation because its native hydrography is coarser and hydrologically adjusted.

### 2.4 HydroSHEDS and HydroRIVERS

HydroSHEDS is a global/near-global hydrographic framework derived primarily from SRTM elevation data and provides conditioned elevation, flow direction, flow accumulation and derived hydrography. The original product and method were designed for large-scale hydrographic analysis. [Lehner, Verdin & Jarvis 2008](https://doi.org/10.1029/2008EO100001), [HydroSHEDS official product page](https://www.hydrosheds.org/products/hydrosheds)

HydroRIVERS is a vector river network extracted from HydroSHEDS. The official product includes rivers with catchment area of at least 10 km² or average river flow of at least 0.1 m³/s, and provides reach attributes useful for connectivity and routing. [HydroRIVERS official page](https://www.hydrosheds.org/products/hydrorivers)

The HydroRIVERS technical documentation defines graph attributes such as a unique reach ID and the ID of the next downstream reach (`NEXT_DOWN`), enabling explicit network traversal and topology QA. [HydroRIVERS Technical Documentation v1.0](https://data.hydrosheds.org/file/technical-documentation/HydroRIVERS_TechDoc_v10.pdf)

**Use in V49:** HydroRIVERS is an excellent independent topology/reference graph and can be used to audit confluences, upstream/downstream direction and missing major branches. Its explicit area/flow inclusion threshold means it cannot be a complete inventory of every small tributary or ditch, and it contains no measured river bathymetry.

### 2.5 Recommended V49 fusion logic

A defensible whole-domain workflow is:

1. Build a `SURFACE_WATER_EVIDENCE` layer from Copernicus WBM + JRC GSW occurrence/seasonality, keeping the source and confidence of every detected water pixel.
2. Build a separate `RIVER_NETWORK_TOPOLOGY` graph with MERIT Hydro as the primary global hydrography prior and HydroRIVERS as an independent reach/topology check.
3. Add any trusted local river/ditch/canal vectors where available and preserve their source metadata.
4. Reconcile water polygons with the graph. Surface-water pixels that do not intersect a river graph are **not automatically rivers**; classify them as lake/reservoir, wetland/floodplain/open water, coastal/estuarine water, or unresolved.
5. Only after classification should V49 assign a hydraulic treatment.

This fusion is an engineering synthesis from the primary sources above; it is not a pre-packaged algorithm supplied by a single dataset owner.

---

## 3. Open-source river bathymetry estimation when surveys are unavailable

### 3.1 HydroMT method set

HydroMT's official `river_depth` workflow estimates bankfull depth with three methods. [HydroMT `river_depth`](https://deltares.github.io/hydromt/dev/_generated/hydromt.model.processes.rivers.river_depth.html)

| Method | Main inputs | Physical assumption / best use |
|---|---|---|
| `powlaw` | bankfull discharge `Qbf` | Empirical downstream hydraulic geometry: depth is a power function of discharge. Lowest-data fallback. |
| `manning` | `Qbf`, river width, river slope, Manning n | Kinematic/uniform-flow-like condition. Suitable where backwater is small and slope is meaningful. |
| `gvf` | `Qbf`, width, river-surface elevation profile, Manning n, flow direction | Gradually varying flow. Appropriate when longitudinal water-surface controls/backwater matter and a reference/control profile is available. |

HydroMT documents the default power-law form as `h = hc * Qbf**hp`, with defaults `hc=0.27` and `hp=0.30`, and explicitly references Leopold & Maddock (1953), Andreadis et al. (2013), Sampson et al. (2015) and Neal et al. (2021) as the scientific foundations. [HydroMT `river_depth`](https://deltares.github.io/hydromt/dev/_generated/hydromt.model.processes.rivers.river_depth.html)

The original hydraulic-geometry work by Leopold & Maddock shows width, depth and velocity varying systematically with discharge as power functions. [USGS Professional Paper 252](https://doi.org/10.3133/pp252)

Andreadis et al. created a near-global bankfull width/depth database from hydraulic-geometry relationships. Their validation reported river-width errors of 8–62% across nine large-river reaches and a mean depth error of 24% at the available field-survey sites. The paper explicitly identifies significant uncertainty and recommends such estimates as model inputs/constraints rather than a substitute for detailed local measurement. [Andreadis et al. 2013](https://doi.org/10.1002/wrcr.20440)

### 3.2 Why GVF matters in V49

Neal et al. (2021) is particularly important for coastal/low-gradient Vietnam. The paper states that large-scale flood models often lack bathymetry because it cannot be directly observed remotely at the required global scale and shows that uniform-flow and downstream-hydraulic-geometry approaches can be biased in nonuniform/backwater reaches. Their GVF-based estimation reduced water-surface-profile error by 66% in their target experiment; in a Mozambique large-scale test, the changed channel bathymetry altered simulated flood extent by 40% and floodplain storage by 79% for the reported event. [Neal et al. 2021](https://doi.org/10.1029/2020WR028301)

The practical lesson is not that GVF produces “true bathymetry”; inverse bathymetry remains non-unique and depends on discharge, width, roughness and water-surface constraints. The lesson is that **backwater-sensitive reaches should not be forced through a pure uniform-flow depth estimator when better longitudinal water-surface information is available**.

### 3.3 SFINCS and subgrid bathymetry

HydroMT-SFINCS supports river bathymetry in its subgrid representation. The current `setup_subgrid` interface accepts centerlines and either river width plus river depth (`rivdph`) or river bed elevation (`rivbed`), with optional river mask and Manning roughness. [HydroMT-SFINCS `setup_subgrid`](https://deltares.github.io/hydromt_sfincs/v1.2.1/_generated/hydromt_sfincs.SfincsModel.setup_subgrid.html)

The SFINCS changelog documents a deliberate architectural change: the old direct `setup_river_bathymetry` path was removed because river bathymetry should ideally be burned into **subgrid data**, which allows representation of rivers narrower than the computational grid cell. [HydroMT-SFINCS changelog](https://deltares.github.io/hydromt_sfincs/latest/changelog.html)

**V49 implication:** if the downstream hydraulic engine supports subgrid channels, V49 should prefer solver-native subgrid width/depth/bed geometry over rasterizing every channel into one or more 30 m cells. A 6 m or 15 m channel should remain a 6 m or 15 m hydraulic feature rather than becoming an artificial 30 m trench simply because the DEM is 30 m.

### 3.4 Recommended method hierarchy and provenance

For each reach, store `BATHY_METHOD` and confidence/provenance:

1. **Observed survey / cross sections / sonar / local bathymetric DEM** — highest priority.
2. **Observed or independently constrained water-surface profile + Qbf + width + roughness → GVF inversion** — preferred for low-gradient/backwater reaches when sufficient constraints exist.
3. **Qbf + width + slope + Manning n → Manning estimate** — reasonable for reaches dominated by approximately kinematic behavior.
4. **Qbf only or limited geometry → calibrated/regional power-law** — fallback.
5. **No defensible hydraulic inputs → unresolved/low-confidence reach** — do not silently assign a universal fixed depth and label it as truth.

Regional coefficients should replace generic global coefficients when local gauge/cross-section information supports them, because Andreadis et al. show substantial variability and uncertainty in global hydraulic-geometry estimates. [Andreadis et al. 2013](https://doi.org/10.1002/wrcr.20440)

---

## 4. River, lake/reservoir, wetland and estuary require different treatment

### 4.1 Rivers

River representation requires a connected centerline/topology plus width, bed/depth, bank elevation and longitudinal profile. For sub-grid-width rivers, solver-native subgrid geometry is preferable when available. [HydroMT-Wflow `setup_rivers`](https://deltares.github.io/hydromt_wflow/stable/api/_generated/hydromt_wflow.WflowSbmModel.setup_rivers.html), [HydroMT-SFINCS `setup_subgrid`](https://deltares.github.io/hydromt_sfincs/v1.2.1/_generated/hydromt_sfincs.SfincsModel.setup_subgrid.html)

### 4.2 Lakes and reservoirs

Lakes/reservoirs should not be handled by applying a river depth law to every water pixel. HydroMT-Wflow provides separate reservoir setup methods, reflecting their role as storage and outlet-control systems rather than ordinary river reaches. [HydroMT-Wflow methods and components](https://deltares.github.io/hydromt_wflow/latest/user_guide/2_sbm_model/1_methods_components.html)

HydroLAKES provides globally consistent lake polygons and attributes including area, volume and estimated average depth. Its documentation distinguishes observed/reported quantities from estimates. These are useful priors or QA constraints, not detailed within-lake bathymetry. [HydroLAKES official product page](https://www.hydrosheds.org/products/hydrolakes), [HydroLAKES Technical Documentation](https://data.hydrosheds.org/file/technical-documentation/HydroLAKES_TechDoc_v10.pdf), [Messager et al. 2016](https://doi.org/10.1038/ncomms13603)

**V49 treatment:** prefer surveyed bathymetry if available. Otherwise represent the lake/reservoir through water-surface elevation and a documented storage relationship (stage-area-volume/rating relationship or another model-supported storage formulation). Any synthetic basin geometry should be explicitly marked synthetic and sensitivity-tested.

### 4.3 Wetlands and floodplain open water

JRC GSW targets **open water visible to the sky**. It can include wetland open water, but this definition means it is not a complete map of all saturated or vegetated wetland terrain. [JRC Global Surface Water FAQ](https://www.global-surface-water.appspot.com/faq)

Therefore, V49 must not convert every JRC water-occurrence pixel into a carved river channel. Many such pixels can be floodplain inundation, wetland ponds, rice/flood irrigation, episodic water, or other non-channel surfaces. For wetlands, preserving floodplain microtopography and storage is generally more defensible than imposing a channel-style trench unless an independent drainage feature is identified.

### 4.4 Estuaries and deltas

Estuaries combine river flow, backwater/tidal controls and coastal bathymetry. MERIT Hydro's own documentation warns that single-direction routing does not fully represent bifurcations and that below-sea-level coastal areas are problematic. [MERIT Hydro official project page](https://global-hydrodynamics.github.io/MERIT_Hydro/)

HydroMT-SFINCS explicitly separates topobathymetry, river inflow/outflow, water-level boundaries and subgrid geometry, which is the appropriate conceptual model for an estuary. [HydroMT-SFINCS model setup](https://deltares.github.io/hydromt_sfincs/stable/user_guide/sfincs_model_setup.html)

For marine/coastal bathymetry where no better local source exists, GEBCO provides an official global gridded bathymetry product; it should be treated as a coarse coastal prior and merged carefully with river/land elevations. [GEBCO gridded bathymetry](https://www.gebco.net/data-products/gridded-bathymetry-data)

**V49 treatment:** establish a transition zone between fluvial and coastal bathymetry; use consistent vertical datums; preserve distributary/bifurcation structure where it matters; apply water-level boundary conditions separately from river inflow. A downstream power-law or simple Manning carve alone is not adequate for a backwater/tidal reach.

---

## 5. QA and sensitivity requirements for a hydraulic DEM/topobathymetry product

HEC-RAS states that an accurate hydraulic terrain model requires representative main-channel bathymetry in addition to overbank terrain. [HEC-RAS Terrain Layer](https://www.hec.usace.army.mil/confluence/rasdocs/rmum/latest/terrain-layer)

Because V49 will infer some bathymetry rather than observe it, QA must test both **geometric consistency** and **hydraulic sensitivity**. The following checklist is an engineering synthesis based on the primary evidence above; it is intentionally stricter than a visual “DEM looks carved” inspection.

### 5.1 Coverage and classification QA

- Percentage of Copernicus WBM water pixels assigned a V49 class.
- JRC GSW persistent/seasonal water that remains unmatched to any class.
- River network reaches without a corresponding water/terrain representation, and water polygons incorrectly forced into the river graph.
- Explicit counts/areas for `river`, `lake`, `reservoir`, `wetland/floodplain`, `estuary/coastal`, and `unresolved`.
- Source/provenance retained for every class decision.

### 5.2 River topology QA

- Every non-terminal reach has a valid downstream connection.
- No directed cycles in the river graph.
- Confluences have consistent upstream/downstream IDs and elevations.
- Orphan/disconnected reaches are flagged.
- Cross-check major paths and outlets against MERIT Hydro and HydroRIVERS `NEXT_DOWN` topology. [HydroRIVERS Technical Documentation v1.0](https://data.hydrosheds.org/file/technical-documentation/HydroRIVERS_TechDoc_v10.pdf)

### 5.3 Longitudinal and cross-sectional geometry QA

- Plot thalweg/bed elevation and bank elevation against downstream distance for every major reach.
- Flag local upstream-facing bed steps that are not supported by known structures/geology.
- Flag abrupt depth/width changes at reach joins and confluences.
- Enforce positive depth and physically valid width/cross-sectional area.
- Audit bank elevation relative to surrounding terrain to avoid creating artificial levees or deep pits.
- Compare available real cross sections/known bridge or gauge elevations against the generated geometry.

Neal et al. show that an unconstrained inverse bathymetry solution can be non-unique and may require regularization to avoid physically implausible bed variability; this directly supports longitudinal-profile QA. [Neal et al. 2021](https://doi.org/10.1029/2020WR028301)

### 5.4 Raster/subgrid integration QA

- Check tile seams and raster/subgrid boundaries for elevation discontinuities.
- Quantify total terrain volume removed/added by class and by reach.
- Confirm that narrow rivers are not artificially widened to the parent grid resolution when subgrid geometry is available. [HydroMT-SFINCS changelog](https://deltares.github.io/hydromt_sfincs/latest/changelog.html)
- At river-to-lake and river-to-estuary transitions, verify continuity of bed, bank and water-level reference.

### 5.5 Vertical datum QA

All terrain, surveyed bathymetry, gauge stages, coastal bathymetry and water-level boundary conditions must be reconciled to a common vertical reference before merging. Vertical datum mismatch can be indistinguishable from false depth and is especially dangerous in estuaries/low-gradient reaches.

### 5.6 Hydraulic sensitivity ensemble

At minimum, perturb uncertain channel depth, width, Manning roughness, bankfull discharge and any inferred longitudinal water-surface/slope parameters within documented uncertainty ranges and compare:

- peak water-surface elevation;
- flood extent;
- inundation depth;
- velocity;
- floodplain storage;
- travel time and hydrograph timing;
- peak discharge at control points.

The need is not hypothetical: Neal et al. demonstrate large flood-extent and storage changes caused solely by the method used to infer bathymetry. [Neal et al. 2021](https://doi.org/10.1029/2020WR028301) Andreadis et al. quantify substantial uncertainty in global hydraulic-geometry estimates and provide confidence intervals, supporting an ensemble rather than a single deterministic “truth” where local survey is absent. [Andreadis et al. 2013](https://doi.org/10.1002/wrcr.20440)

V49 should store uncertainty/provenance fields such as `BATHY_METHOD`, `BATHY_SOURCE`, `QBF_SOURCE`, `WIDTH_SOURCE`, `ROUGHNESS_SOURCE`, `CONFIDENCE_CLASS` and any parameter interval used in sensitivity runs.

---

## 6. Scientific limits of using a 30 m DEM for hydraulic modeling

### 6.1 GLO-30 is a DSM, and water pixels have been edited

Copernicus GLO-30 represents the surface, not a surveyed bare-earth river bed. The WBM identifies Ocean/Lake/River pixels that are classified and edited as water. Therefore, the DEM elevation over water should not be interpreted as bottom elevation. [Copernicus DEM official collection page](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM), [Copernicus DEM Product Handbook v5.0](https://dataspace.copernicus.eu/sites/default/files/media/files/2024-06/geo1988-copernicusdem-spe-002_producthandbook_i5.0.pdf)

### 6.2 Horizontal grid spacing is not channel-geometry resolution

A river narrower than one 30 m cell cannot be faithfully represented as a full-width raster trench without changing its hydraulic geometry. HydroMT-SFINCS explicitly uses subgrid river bathymetry so rivers narrower than a computational cell remain representable. [HydroMT-SFINCS changelog](https://deltares.github.io/hydromt_sfincs/latest/changelog.html)

### 6.3 Open-water masks have their own detection limits

JRC GSW is a 30 m Landsat product of open water visible from space. It should be expected to perform differently for narrow channels, vegetated wetlands, turbid/obscured water and highly dynamic boundaries than for broad unobstructed water surfaces. [JRC Global Surface Water FAQ](https://www.global-surface-water.appspot.com/faq)

### 6.4 Global hydrography products are excellent priors, not local hydraulic truth

MERIT Hydro is about 90 m at the equator and uses hydrologically adjusted elevation; HydroRIVERS is derived from a coarser global hydrography framework and applies explicit inclusion thresholds. Both are valuable for topology and regional consistency, but neither supplies detailed 30 m river cross sections or measured beds. [Yamazaki et al. 2019](https://doi.org/10.1029/2019WR024873), [HydroRIVERS official page](https://www.hydrosheds.org/products/hydrorivers)

### 6.5 Empirical bathymetry remains uncertain

Global hydraulic geometry can supply useful first-order width/depth constraints, but the observed errors in Andreadis et al. and the backwater sensitivity in Neal et al. show that an inferred channel can materially change flood predictions. [Andreadis et al. 2013](https://doi.org/10.1002/wrcr.20440), [Neal et al. 2021](https://doi.org/10.1029/2020WR028301)

### 6.6 Proper claim for a V49 product

If V49 has no survey data, it should be described as a **hydraulically conditioned topobathymetry with inferred channel bathymetry and quantified provenance/uncertainty**, not as a surveyed or “true” bathymetric DEM.

For regional flood modeling, a 30 m overbank DEM can still be useful if the unresolved channel geometry is represented explicitly (preferably subgrid where supported), the water classes are handled correctly, and uncertainty is propagated through sensitivity testing. It should not be presented as survey-grade channel geometry.

---

## 7. Recommended V49 architecture derived from the evidence

```text
Copernicus GLO-30 DSM + WBM
            │
            ├─────────────── JRC GSW occurrence/seasonality
            │                         │
            └──────────────┬──────────┘
                           ▼
                SURFACE_WATER_EVIDENCE
                           │
                classify water object
                           │
       ┌───────────┬───────┼───────────┬────────────┐
       ▼           ▼       ▼           ▼            ▼
     River       Lake   Reservoir    Wetland    Estuary/coast
       │           │       │           │            │
MERIT Hydro +      │   storage/        │       coastal topo-
HydroRIVERS        │   outlet          │       bathymetry +
network graph      │   controls        │       tidal/backwater
       │           │       │           │            │
       ▼           ▼       ▼           ▼            ▼
river geometry   bathy / stage-area-volume      preserve/classify
       │
       ├─ survey/XS if available
       ├─ GVF where backwater/WSE constraints exist
       ├─ Manning for kinematic reaches
       └─ power-law fallback with explicit uncertainty
       │
       ▼
BATHYMETRY PROVENANCE + CONFIDENCE
       │
       ├───────────────┐
       ▼               ▼
DEM_HYDRO_        HYDRAULIC_TOPOBATHY /
CONDITIONED       solver-native SUBGRID
(flow topology)   (hydraulic geometry)
       │               │
       └────── QA + sensitivity ensemble ──────┘
```

### Minimal V49 deliverables

1. `surface_water_evidence` raster/vector with WBM/JRC source flags and persistence metrics.
2. `water_object_class` layer with river/lake/reservoir/wetland/estuary/coast/unresolved.
3. `river_network_topology` graph with reach IDs, downstream IDs, upstream area and outlet IDs.
4. `river_geometry` table/vector with width, depth/bed, bank elevation, slope/WSE constraint, Manning n, method and provenance.
5. `DEM_HYDRO_CONDITIONED` for drainage analysis only.
6. `HYDRAULIC_TOPOBATHY` and/or solver-native subgrid channel tables for hydraulics.
7. QA artifacts: water-coverage report, graph/topology checks, thalweg profiles, cross-section plots, confluence checks, volume-change report, seam checks and vertical-datum audit.
8. Sensitivity scenarios and a summary ranking the hydraulic outputs most sensitive to bathymetry uncertainty.

### Go/no-go criterion before returning to hydraulic simulation

V49 should not be accepted merely because the carved DEM visually shows river channels. It should be accepted only when:

- the whole-domain surface-water audit is accounted for by class;
- the river graph is topologically connected where expected;
- every hydraulic reach has a documented bathymetry method/provenance;
- longitudinal/channel geometry QA passes or flagged exceptions are justified;
- river/lake/wetland/estuary treatments are separated;
- sensitivity runs demonstrate how much inferred bathymetry controls flood outputs.

---

## Primary / official source index

### Arc Hydro / terrain conditioning

- Esri, **Arc Hydro: Overview of Terrain Preprocessing Workflows**: https://content.esri.com/archydro/archydro/doc/arc%20hydro%20-%20overview%20of%20terrain%20preprocessing%20workflows.pdf
- USACE HEC, **HEC-GeoHMS User's Manual 10.1**: https://www.hec.usace.army.mil/software/hec-geohms/documentation/HEC-GeoHMS_Users_Manual_10.1.pdf
- USACE HEC, **HEC-GeoHMS 1.1 User's Manual**: https://www.hec.usace.army.mil/software/hec-geohms/documentation/HEC-GeoHMS11.pdf
- USACE HEC, **HEC-HMS GIS Menu — Terrain Reconditioning**: https://www.hec.usace.army.mil/confluence/hmsdocs/hmsum/4.10/geographic-information/gis-menu

### Copernicus DEM / WBM

- Copernicus Data Space Ecosystem, **Copernicus DEM collection**: https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM
- Copernicus Data Space Ecosystem, **Copernicus DEM documentation**: https://documentation.dataspace.copernicus.eu/Data/Others/CCM.html
- Copernicus DEM, **Product Handbook v5.0**: https://dataspace.copernicus.eu/sites/default/files/media/files/2024-06/geo1988-copernicusdem-spe-002_producthandbook_i5.0.pdf

### JRC Global Surface Water

- Pekel, J.-F., Cottam, A., Gorelick, N. & Belward, A.S. (2016), **High-resolution mapping of global surface water and its long-term changes**, Nature 540, 418–422: https://doi.org/10.1038/nature20584
- JRC, **Global Surface Water FAQ**: https://www.global-surface-water.appspot.com/faq
- JRC, **Global Surface Water download/metadata**: https://global-surface-water.appspot.com/download

### MERIT DEM / MERIT Hydro

- Yamazaki, D. et al. (2017), **A high-accuracy map of global terrain elevations**, Geophysical Research Letters: https://doi.org/10.1002/2017GL072874
- Yamazaki, D. et al. (2019), **MERIT Hydro: A High-Resolution Global Hydrography Map Based on Latest Topography Dataset**, Water Resources Research: https://doi.org/10.1029/2019WR024873
- MERIT Hydro official project page: https://global-hydrodynamics.github.io/MERIT_Hydro/

### HydroSHEDS / HydroRIVERS / HydroLAKES

- Lehner, B., Verdin, K. & Jarvis, A. (2008), **New global hydrography derived from spaceborne elevation data**: https://doi.org/10.1029/2008EO100001
- HydroSHEDS official page: https://www.hydrosheds.org/products/hydrosheds
- HydroRIVERS official page: https://www.hydrosheds.org/products/hydrorivers
- HydroRIVERS Technical Documentation v1.0: https://data.hydrosheds.org/file/technical-documentation/HydroRIVERS_TechDoc_v10.pdf
- HydroLAKES official page: https://www.hydrosheds.org/products/hydrolakes
- HydroLAKES Technical Documentation v1.0: https://data.hydrosheds.org/file/technical-documentation/HydroLAKES_TechDoc_v10.pdf
- Messager, M.L. et al. (2016), **Estimating the volume and age of water stored in global lakes using a geo-statistical approach**: https://doi.org/10.1038/ncomms13603

### Open-source bathymetry / hydraulic geometry

- HydroMT, **`river_depth` API**: https://deltares.github.io/hydromt/dev/_generated/hydromt.model.processes.rivers.river_depth.html
- HydroMT-Wflow, **`setup_rivers` API**: https://deltares.github.io/hydromt_wflow/stable/api/_generated/hydromt_wflow.WflowSbmModel.setup_rivers.html
- HydroMT-SFINCS, **`setup_subgrid` API**: https://deltares.github.io/hydromt_sfincs/v1.2.1/_generated/hydromt_sfincs.SfincsModel.setup_subgrid.html
- HydroMT-SFINCS, **changelog**: https://deltares.github.io/hydromt_sfincs/latest/changelog.html
- Eilander, D. et al. (2023), **HydroMT: Automated and reproducible model building and analysis**, JOSS: https://doi.org/10.21105/joss.04897
- Leopold, L.B. & Maddock, T. (1953), **The hydraulic geometry of stream channels and some physiographic implications**, USGS Professional Paper 252: https://doi.org/10.3133/pp252
- Andreadis, K.M., Schumann, G.J.-P. & Pavelsky, T. (2013), **A simple global river bankfull width and depth database**: https://doi.org/10.1002/wrcr.20440
- Sampson, C.C. et al. (2015), **A high-resolution global flood hazard model**: https://doi.org/10.1002/2015WR016954
- Neal, J. et al. (2021), **Estimating River Channel Bathymetry in Large Scale Flood Inundation Models**: https://doi.org/10.1029/2020WR028301

### Hydraulic terrain / coastal bathymetry

- USACE HEC-RAS, **Using Cross Section Data to Modify/Improve the Terrain Model**: https://www.hec.usace.army.mil/confluence/rasdocs/r2dum/6.0/developing-a-terrain-model-and-geospatial-layers/using-cross-section-data-to-modify-improve-the-terrain-model
- USACE HEC-RAS, **Terrain Layer**: https://www.hec.usace.army.mil/confluence/rasdocs/rmum/latest/terrain-layer
- HydroMT-SFINCS, **model setup**: https://deltares.github.io/hydromt_sfincs/stable/user_guide/sfincs_model_setup.html
- GEBCO, **Gridded bathymetry data**: https://www.gebco.net/data-products/gridded-bathymetry-data

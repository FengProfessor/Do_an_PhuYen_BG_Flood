# V49-C primary-source research: water-body classification and conditioning constraints

Date: 2026-10-12  
Scope: classification evidence for river/stream, canal, lake/reservoir/pond/lagoon, wetland, estuary/tidal water, ocean; limits of OSM, JRC Global Surface Water, HydroRIVERS/HydroSHEDS; Arc Hydro implications for DEM conditioning; conservative treatment of uncertain objects.

## Executive conclusion

For V49-C, no single source should be treated as physical ground truth. OpenStreetMap (OSM) is strongest as **semantic evidence of mapper intent**; JRC Global Surface Water (GSW) occurrence is strongest as **evidence that open surface water was repeatedly observed**; HydroRIVERS/HydroSHEDS is strongest as **coarse, globally consistent river-network evidence**; Arc Hydro documentation is strongest for understanding that stream burning, sink handling, and waterbody flow-direction adjustment are **active terrain/hydrologic conditioning operations whose inputs must be correct**.

The defensible rule is therefore: assign an automatic class only when the geometry, OSM semantics, coastal context, and independent hydrologic evidence are mutually compatible. If an object is ambiguous, conflicting, underspecified, or below the effective resolution/coverage of the supporting datasets, assign **`UNKNOWN_REVIEW_REQUIRED`** and apply **no automatic destructive carving**. This state is intentionally conservative: uncertainty in class, geometry, connectivity, tidal influence, or source agreement is evidence that the project does not yet know enough to make an irreversible terrain edit safely. This follows directly from the different meanings and limitations of the sources and from Arc Hydro's own warnings that incorrect stream/waterbody interactions can produce erroneous conditioning results.

## 1. OSM semantics: what the tags do and do not establish

OSM's `waterway=*` key is explicitly used for natural and artificial flowing-water features. The OSM Wiki defines `waterway=river` as a wide natural watercourse, `waterway=stream` as a narrower naturally formed waterway, and `waterway=canal` as an artificial open waterway used to carry useful water. It also defines `waterway=tidal_channel` as a natural tidal waterway in the coastal marine environment with bidirectional saline flow controlled by tides. These tags are therefore useful for separating **natural channel**, **small natural channel**, **artificial conveyance**, and **tidal-channel** intent. ([OSM `Key:waterway`](https://wiki.openstreetmap.org/wiki/Key:waterway), [OSM Waterways](https://wiki.openstreetmap.org/wiki/Waterway), [OSM `waterway=tidal_channel`](https://wiki.openstreetmap.org/wiki/Tag:waterway%3Dtidal_channel))

For areal water, OSM's documented pattern is `natural=water` plus `water=*`. The Waterways documentation distinguishes river areas (`water=river`), canal areas (`water=canal`), lakes (`water=lake`), and reservoirs (`water=reservoir`). The `water=*` documentation also distinguishes ponds and lagoons; a lagoon is shallow sea or brackish water separated from the sea by a barrier. This gives a defensible semantic separation between **flowing channel area**, **artificial channel area**, **standing inland water**, and **coastal/brackish lagoon**. ([OSM Waterways](https://wiki.openstreetmap.org/wiki/Waterway), [OSM `Key:water`](https://wiki.openstreetmap.org/wiki/Key:water))

Wetlands are not simply another `natural=water` subtype. OSM uses `natural=wetland` for land that is water-saturated or inundated permanently or seasonally, with subtypes such as marsh, swamp, bog, and tidal flat. A wetland polygon therefore should not be assumed to represent a permanently open-water surface or a channel thalweg. ([OSM `natural=wetland`](https://wiki.openstreetmap.org/wiki/Tag:natural%3Dwetland))

Ocean/sea boundaries are represented through `natural=coastline`; this is a shoreline geometry convention separating land from the sea, not a river-centerline classification. Coastal polygons and coastline proximity must therefore be interpreted as marine-boundary context rather than as evidence for inland-channel carving. ([OSM `natural=coastline`](https://wiki.openstreetmap.org/wiki/Tag:natural%3Dcoastline))

### Classification implications from OSM

- `waterway=river` / `waterway=stream` is positive semantic evidence for a natural channel.
- `waterway=canal` is positive semantic evidence for an artificial conveyance channel and should remain distinct from a natural river even when both contain flowing water.
- `water=lake|reservoir|pond` is positive semantic evidence for standing/open inland water, not for a channel spanning the whole polygon.
- `water=lagoon` is coastal/brackish semantics and should not be collapsed into an inland lake without corroborating context.
- `natural=wetland` is evidence for saturated/inundated terrain; it is insufficient by itself to justify channel carving.
- `waterway=tidal_channel`, `tidal=yes`, coastline context, or lagoon/coastal geometry is evidence for tidal influence; tidal flow can be bidirectional, so a simple inland downstream-flow assumption is unsafe.

OSM remains a volunteered mapping database. The classification above is therefore an interpretation of **tag semantics**, not a guarantee that every mapped feature is complete, current, geometrically precise, or physically classified without mapper error. A particularly important warning is that OSM documentation itself contains multiple mapping patterns and legacy equivalents for water features. **Inference for V49-C:** OSM should be treated as a high-value semantic prior, but destructive terrain modification should not depend on an OSM tag alone.

## 2. JRC Global Surface Water: useful evidence, not a physical-type classifier

The EC Joint Research Centre Global Surface Water dataset maps the location and temporal behavior of surface water from the Landsat archive. The official data portal publishes occurrence, change, seasonality, recurrence, transitions, and maximum extent; the current portal states that the dataset has been updated through 2024. The foundational JRC-led paper describes global surface-water mapping at Landsat scale and long-term change analysis. ([JRC Global Surface Water data access](https://global-surface-water.appspot.com/download), [Pekel et al., 2016, *Nature*](https://doi.org/10.1038/nature20584))

For V49-C, occurrence is best interpreted as **temporal evidence of observed surface water**. It is not a categorical label for river versus canal versus lake versus reservoir versus estuary versus ocean. Two physically different objects can both have high occurrence, and a narrow or intermittently visible water feature can have weaker occurrence even when it is hydrologically important.

The Landsat basis also imposes a finite spatial support: small channels, narrow canal reaches, vegetated wetlands, mixed shoreline pixels, and rapidly changing tidal/intermittent features can be imperfectly represented. The product is therefore valuable for answering “is this location repeatedly observed as open surface water?” but is not sufficient to answer “what kind of waterbody is this?” or “what thalweg should be carved?” **Inference for V49-C:** GSW occurrence may strengthen or weaken confidence in the presence/persistence of open water, but it should never override contradictory morphology or semantics and should never be the sole trigger for destructive carving.

## 3. HydroRIVERS / HydroSHEDS: network corroboration with scale and derivation limits

HydroRIVERS is a globally consistent vector river network derived from HydroSHEDS at 15 arc-second resolution. The official product documentation states that HydroRIVERS includes rivers with catchment area at least 10 km² or long-term average discharge at least 0.1 m³/s, or both, and that its attributes are mainly geometric/network descriptors. This makes it useful for checking whether a candidate natural river aligns with an independently derived drainage network. ([HydroRIVERS product page](https://www.hydrosheds.org/products/hydrorivers), [HydroRIVERS Technical Documentation v1.0](https://data.hydrosheds.org/file/technical-documentation/HydroRIVERS_TechDoc_v10.pdf))

HydroRIVERS is not an exhaustive inventory of every stream, ditch, canal, or local drainage feature. Its inclusion thresholds inherently omit many small watercourses, and its geometry inherits the scale and assumptions of the HydroSHEDS terrain-derived drainage framework. Absence from HydroRIVERS therefore must not be interpreted as proof that an OSM stream or local channel is false.

HydroSHEDS itself is derived from elevation data and its technical documentation discusses source limitations of SRTM, including vegetation and other radar/surface effects and difficulties over open water and complex terrain. Those limitations can propagate into derived flow directions and river geometry. ([HydroSHEDS Technical Documentation v1.4](https://data.hydrosheds.org/file/technical-documentation/HydroSHEDS_TechDoc_v1_4.pdf))

**Inference for V49-C:** HydroRIVERS agreement is useful positive corroboration for a river-class candidate, especially for larger channels; disagreement is only a confidence penalty. It should not be used to erase small streams, classify artificial canals, distinguish lakes from reservoirs, identify wetlands, or resolve tidal/coastal water by itself.

## 4. Arc Hydro / Esri guidance: conditioning is an active intervention

Arc Hydro preprocessing explicitly uses DEM reconditioning (“burning” a stream representation into the DEM) to force terrain near mapped streams toward those streams. Its stormwater workflow also separates stream burning, sink treatment, filling, and later flow-direction adjustment. This confirms that a carve/burn operation is not a neutral label assignment; it changes the elevation surface and the resulting drainage behavior. ([Esri Arc Hydro Stormwater Processing](https://downloads.esri.com/archydro/archydro/Doc/Arc%20Hydro%20Stormwater%20v1%2010032017.pdf))

Arc Hydro quality-control guidance specifically checks waterbody/stream interactions and warns that stream placement near watershed boundaries can cause problems with burning. It also notes that non-sink waterbody polygons need streams through them to participate in “adjust flow direction in lakes.” This supports waterbody-aware routing rather than indiscriminately carving every wet polygon. ([Esri Arc Hydro preprocessing vector-data QC](https://downloads.esri.com/archydro/archydro/doc/ahpcs1%20qc%20for%20preprocessing%20vector%20data.pdf))

**Inference for V49-C:** because incorrect input geometry can alter the conditioned terrain and flow network, uncertainty should be resolved before carving. Review-required objects should remain geometrically intact until a human or higher-confidence rule establishes the correct hydrologic role.

## 5. Decision table for V49-C

| Final class | Strongest defensible evidence | Automatic treatment constraint | Conditions that force review |
|---|---|---|---|
| **River / stream** | OSM `waterway=river|stream`; linear valley/channel morphology; HydroRIVERS agreement for larger reaches; compatible GSW presence where width permits | May be eligible for **linear hydrologic conditioning/carving** only when continuity and downstream connectivity are coherent. Do not carve the full areal water polygon as a uniform trench. | Broken/implausible connectivity; strong coastal/tidal cues; polygon looks like standing water; OSM/HydroRIVERS conflict with terrain; narrow feature below supporting-data resolution |
| **Canal** | OSM `waterway=canal` / `water=canal`; artificial straight/engineered geometry; known control structures | Keep distinct from natural river. Carve/condition only if V49-C explicitly intends to model the canal as a drainage/conveyance path and direction/connectivity are known. | Unknown function; navigation/irrigation canal with uncertain hydraulic connection; disconnected segment; tag/geometry conflict |
| **Lake / reservoir / pond** | OSM `water=lake|reservoir|pond`; closed standing-water polygon; high GSW occurrence can corroborate open water | **No blanket destructive channel carve across the polygon.** Preserve waterbody footprint; if hydrologic conditioning is required, use inlet/outlet-aware routing or waterbody-specific flow adjustment/leveling consistent with the DEM workflow. | Multiple candidate outlets; seasonal/ephemeral basin; polygon intersects several channels ambiguously; reservoir/lake semantics conflict |
| **Lagoon** | OSM `water=lagoon`; coastal location; brackish/marine separation by barrier | Treat as coastal/tidal standing water. Preserve polygon; do not apply inland-lake or river-carve assumptions automatically. | Uncertain sea connection; mapped as lake/reservoir elsewhere; rapidly changing shoreline/tidal inlet |
| **Wetland** | OSM `natural=wetland`; marsh/swamp/bog/tidal-flat subtype; variable GSW occurrence consistent with inundation | **No automatic destructive carving of the wetland polygon.** Preserve terrain/wetland extent. Only condition an explicitly mapped and independently credible channel through it. | Any proposed carve based solely on GSW or wetland presence; unclear channel path; tidal wetland; conflicting open-water tag |
| **Estuary / tidal water** | `waterway=tidal_channel`, `tidal=yes`, lagoon/coastline context, downstream connection to sea; water geometry showing tidal widening | Preserve tidal/open-water area. Do not assume single-direction inland flow or apply a generic river burn across the area. Explicit channel conditioning requires confirmed channel geometry and intended flow treatment. | River-versus-tidal-channel ambiguity; estuary mouth geometry uncertain; multiple tidal branches; coastline/tag conflicts |
| **Ocean / sea** | `natural=coastline` and marine-side context; extensive connected marine water | Treat as boundary/receiver/mask according to project DEM domain. **No river-style carving of ocean polygons.** | Shoreline uncertainty, reclaimed land, tidal flats, estuarine transition, DEM domain boundary ambiguity |
| **`UNKNOWN_REVIEW_REQUIRED`** | Missing/ambiguous tags, contradictory sources, insufficient resolution, or geometry inconsistent with assigned semantics | **Review required. No automatic destructive carving, burning, flattening, or forced outlet modification.** Preserve source geometry and confidence/evidence fields for review. | By definition, any unresolved ambiguity or material source conflict |

## 6. Recommended evidence hierarchy and conservative rule

Use evidence by role rather than forcing a single ranking:

1. **OSM semantics** answer what the mapper intended the object to be.
2. **Geometry and local topographic context** test whether that semantic class is physically plausible.
3. **JRC GSW occurrence** corroborates persistence/presence of open surface water, not class identity.
4. **HydroRIVERS/HydroSHEDS** corroborates larger natural river-network connectivity, subject to scale/derivation limits.
5. **Coastline/tidal context** has priority when deciding whether inland-flow assumptions are valid.
6. **Arc Hydro conditioning constraints** govern what is safe to modify: stream burning and flow-direction adjustment should only operate on sufficiently trusted inputs.

Recommended V49-C gate for any destructive carve: **semantic class compatible + geometry plausible + connectivity coherent + no unresolved coastal/tidal conflict + no material source conflict**. If any of these conditions fails, assign `class = UNKNOWN_REVIEW_REQUIRED`, `review_required = true`, and `auto_carve = false`.

This is intentionally asymmetric: false negatives can be reviewed later, while a false positive carve changes the terrain model and can propagate downstream into flow direction, accumulation, drainage structure, and bathymetric interpretation.

## Primary sources used

- OpenStreetMap Wiki — Waterways: https://wiki.openstreetmap.org/wiki/Waterway
- OpenStreetMap Wiki — `Key:waterway`: https://wiki.openstreetmap.org/wiki/Key:waterway
- OpenStreetMap Wiki — `Key:water`: https://wiki.openstreetmap.org/wiki/Key:water
- OpenStreetMap Wiki — `waterway=tidal_channel`: https://wiki.openstreetmap.org/wiki/Tag:waterway%3Dtidal_channel
- OpenStreetMap Wiki — `natural=wetland`: https://wiki.openstreetmap.org/wiki/Tag:natural%3Dwetland
- OpenStreetMap Wiki — `natural=coastline`: https://wiki.openstreetmap.org/wiki/Tag:natural%3Dcoastline
- EC/JRC Global Surface Water — data access: https://global-surface-water.appspot.com/download
- Pekel et al. (JRC-led), 2016 — *High-resolution mapping of global surface water and its long-term changes*: https://doi.org/10.1038/nature20584
- HydroSHEDS — HydroRIVERS product page: https://www.hydrosheds.org/products/hydrorivers
- HydroRIVERS Technical Documentation v1.0: https://data.hydrosheds.org/file/technical-documentation/HydroRIVERS_TechDoc_v10.pdf
- HydroSHEDS Technical Documentation v1.4: https://data.hydrosheds.org/file/technical-documentation/HydroSHEDS_TechDoc_v1_4.pdf
- Esri Arc Hydro — preprocessing vector-data QC: https://downloads.esri.com/archydro/archydro/doc/ahpcs1%20qc%20for%20preprocessing%20vector%20data.pdf
- Esri Arc Hydro — Stormwater Processing: https://downloads.esri.com/archydro/archydro/Doc/Arc%20Hydro%20Stormwater%20v1%2010032017.pdf


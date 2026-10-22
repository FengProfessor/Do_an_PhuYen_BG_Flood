"""
Investigate JRC and OSM counts in Tuy Hoa plain.
"""

import numpy as np
import rasterio

jrc_path = r"D:\VTP\V48_research_20261002\hydro_evidence_raw\V46_JRC_GSW1_3_occurrence_1984_2020.tif"
osm_path = r"D:\VTP\V46_dryrun_20260930\V46_distance_to_osm_waterway_m.tif"
dem_path = r"D:\VTP\05-Du-lieu-GIS\PhuYen_DEM_30m_V48_BASE_COPERNICUS.tif"

with rasterio.open(jrc_path) as src_jrc, rasterio.open(osm_path) as src_osm, rasterio.open(dem_path) as src_dem:
    jrc = src_jrc.read(1)
    osm = src_osm.read(1)
    dem = src_dem.read(1)

# In eastern columns (col >= 1359)
# If we filter onshore: elevation > 0 or elevation >= 0
onshore_mask = (dem > 0)
east_mask = np.zeros_like(dem, dtype=bool)
east_mask[:, 1359:] = True

east_onshore = east_mask & onshore_mask
jrc_gt0_onshore = np.sum((jrc > 0) & east_onshore)
jrc_ge50_onshore = np.sum((jrc >= 50) & east_onshore)
osm_center_onshore = np.sum((osm == 0) & east_onshore)

print(f"Total eastern cells (col >= 1359): {np.sum(east_mask)}")
print(f"Eastern onshore cells (DEM > 0): {np.sum(east_onshore)}")
print(f"JRC > 0 in eastern onshore: {jrc_gt0_onshore}")
print(f"JRC >= 50 in eastern onshore: {jrc_ge50_onshore}")
print(f"OSM centerline in eastern onshore: {osm_center_onshore}")

# What if elevation >= 0?
east_elev_ge0 = east_mask & (dem >= 0)
print(f"JRC > 0 (DEM >= 0): {np.sum((jrc > 0) & east_elev_ge0)}")
print(f"JRC >= 50 (DEM >= 0): {np.sum((jrc >= 50) & east_elev_ge0)}")
print(f"OSM centerline (DEM >= 0): {np.sum((osm == 0) & east_elev_ge0)}")

# Check if there is another mask or basin boundary
# Let's inspect rows around Ba River: Y ~ 1440000 to 1455000
# row indices
r_min, c_min = src_dem.index(310740, 1455000)
r_max, c_max = src_dem.index(333000, 1435000)
print(f"Ba River corridor rows: {r_min} to {r_max}")
ba_corridor = np.zeros_like(dem, dtype=bool)
ba_corridor[min(r_min, r_max):max(r_min, r_max), 1359:] = True
print(f"OSM centerline in Ba corridor: {np.sum((osm == 0) & ba_corridor)}")
print(f"JRC > 0 in Ba corridor: {np.sum((jrc > 0) & ba_corridor)}")
print(f"JRC >= 50 in Ba corridor: {np.sum((jrc >= 50) & ba_corridor)}")

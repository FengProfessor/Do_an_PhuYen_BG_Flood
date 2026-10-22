import xarray as xr
import numpy as np

sim_nc = r"D:\VTP\BG_Flood_Project\BG_Flood\results\PhuYen_30m_V37_1.nc"
target_bounds = (310000, 1438000, 326000, 1453000)

ds = xr.open_dataset(sim_nc)
h_sim = ds.h.isel(time=8).values
zb = ds.zb.isel(time=0).values

sim_x = ds.x.values
sim_y = ds.y.values
sim_x_mask = (sim_x >= target_bounds[0]) & (sim_x <= target_bounds[2])
sim_y_mask = (sim_y >= target_bounds[1]) & (sim_y <= target_bounds[3])

sim_h_crop = h_sim[np.ix_(sim_y_mask, sim_x_mask)]
sim_zb_crop = zb[np.ix_(sim_y_mask, sim_x_mask)]
wl_crop = sim_h_crop + sim_zb_crop

mid_y_idx = np.argmin(np.abs(sim_y[sim_y_mask] - 1445000))
# Let's just find the max water level in the whole cropped river area
river_mask = sim_h_crop > 2.0
wl_river = wl_crop[river_mask]
print("Max WL in river:", np.max(wl_river) if len(wl_river)>0 else 0)

# Northern area
north_h = sim_h_crop[:mid_y_idx, :] if sim_y[0] > sim_y[-1] else sim_h_crop[mid_y_idx:, :]
north_zb = sim_zb_crop[:mid_y_idx, :] if sim_y[0] > sim_y[-1] else sim_zb_crop[mid_y_idx:, :]
river_north = north_h > 2.0
print("Max WL in North river:", np.max(north_h[river_north] + north_zb[river_north]) if np.sum(river_north)>0 else 0)

# Southern area
south_h = sim_h_crop[mid_y_idx:, :] if sim_y[0] > sim_y[-1] else sim_h_crop[:mid_y_idx, :]
south_zb = sim_zb_crop[mid_y_idx:, :] if sim_y[0] > sim_y[-1] else sim_zb_crop[:mid_y_idx, :]
river_south = south_h > 2.0
print("Max WL in South river:", np.max(south_h[river_south] + south_zb[river_south]) if np.sum(river_south)>0 else 0)

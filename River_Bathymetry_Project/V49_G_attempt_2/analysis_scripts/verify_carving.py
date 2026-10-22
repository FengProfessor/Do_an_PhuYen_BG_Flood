import netCDF4 as nc
import numpy as np
import rasterio

nc_path = r'D:\VTP\River_Bathymetry_Project\V49_G_attempt_2\results\V49_G_CENTRAL.nc'
base_tif_path = r'D:\VTP\05-Du-lieu-GIS\PhuYen_DEM_30m_V48_BASE_COPERNICUS.tif'

print("Reading zb from V49_G_CENTRAL.nc...")
ds = nc.Dataset(nc_path, 'r')
zb_nc = np.asarray(ds.variables['zb'][:, :], dtype=np.float32)
if zb_nc.ndim == 3:
    zb_nc = zb_nc[0, :, :]
ds.close()

print("Reading BASE Copernicus DEM from GeoTIFF...")
with rasterio.open(base_tif_path) as src:
    zb_base = src.read(1)
# GeoTIFF row 0 is top (North), NetCDF row 0 is bottom (South)
zb_base_aligned = np.flipud(zb_base)

# Difference: BASE minus CENTRAL (positive means CENTRAL is carved deeper)
diff = zb_base_aligned - zb_nc
carved_mask = diff > 0.001
carved_cells = int(carved_mask.sum())
max_carve = float(diff.max())
mean_carve = float(diff[carved_mask].mean()) if carved_cells > 0 else 0.0
total_volume_m3 = float(diff[carved_mask].sum()) * 30.0 * 30.0

print(f"Total cells: {zb_nc.size}")
print(f"Carved cells (diff > 1mm): {carved_cells} cells ({carved_cells * 30 * 30 / 1e6:.2f} km2)")
print(f"Max carving depth: {max_carve:.3f} m")
print(f"Mean carving depth in channel: {mean_carve:.3f} m")
print(f"Total excavated riverbed volume: {total_volume_m3:,.1f} m3")

raised_cells = int((diff < -0.001).sum())
print(f"Raised cells: {raised_cells}")

# Also compare against V49_E_hydraulic_bed.tif
central_tif_path = r'D:\VTP\River_Bathymetry_Project\V49_E_20261012\V49_E_hydraulic_bed.tif'
with rasterio.open(central_tif_path) as src:
    zb_central_tif = src.read(1)

diff_tif = zb_base - zb_central_tif
print(f"In GeoTIFF: Carved cells: {(diff_tif > 0.001).sum()}, Max carve: {diff_tif.max():.3f} m")

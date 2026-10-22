import xarray as xr
import rasterio

sim_nc = r"D:\VTP\BG_Flood_Project\BG_Flood\results\PhuYen_30m_V37_1.nc"
sar_tif = r"D:\VTP\05-Du-lieu-GIS\DakLak_PhuYen_FloodExtent_Otsu_20211130_05h36.tif"

ds = xr.open_dataset(sim_nc)
print("Data vars:", ds.data_vars)
print("Coords:", ds.coords)
print("Time len:", len(ds.time) if 'time' in ds.coords else 0)

with rasterio.open(sar_tif) as src:
    print("SAR bounds:", src.bounds)
    print("SAR crs:", src.crs)

"""Read-only extraction of the historical comparison classes for figure creation."""
from pathlib import Path
import importlib.util
import json
import netCDF4
import numpy as np
from rasterio.transform import from_bounds
from rasterio.warp import Resampling

root = Path(r"D:\VTP")
out = root / "Do_an_edit_20261005"
spec = importlib.util.spec_from_file_location("audit", root / "Do_an_research_20261005/audit_project_evidence.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
gis = root / "05-Du-lieu-GIS"
with netCDF4.Dataset(root / "BG_Flood_Project/BG_Flood/results/PhuYen_30m_V44.nc") as ds:
    x, y = np.asarray(ds["x"][:]), np.asarray(ds["y"][:])
    h = np.flipud(np.ma.filled(ds["h"][33], 0)).astype(np.float32)
    shape = h.shape
    transform = from_bounds(x[0]-15,y[0]-15,x[-1]+15,y[-1]+15,shape[1],shape[0])
sar = audit.align(gis / "DakLak_PhuYen_FloodExtent_Otsu_20211130_05h36.asc",shape,transform,Resampling.nearest,-9999,True)
water = audit.align(gis / "water_density_30m.tif",shape,transform,Resampling.bilinear)
hand = audit.align(root / "BG_Flood_Project/BG_Flood/Teamwork_Validation/PhuYen_HAND_30m.tif",shape,transform,Resampling.bilinear,-9999)
valid = (sar!=-9999)&(water<=.5)&(hand>=0)
wet, sarwet = (h>.3)&valid, (sar==1)&valid
classes = np.zeros(shape,dtype=np.uint8)
classes[valid] = 1
classes[wet & sarwet] = 2
classes[wet & ~sarwet] = 3
classes[~wet & sarwet] = 4
classes[water>.5] = 5
counts = {"tp":int(((classes==2)&valid).sum()),"fp":int(((classes==3)&valid).sum()),
          "fn":int(((classes==4)&valid).sum()),"tn":int(((classes==1)&valid).sum())}
assert counts == {"tp":72168,"fp":60698,"fn":216808,"tn":3130770}
np.save(out / "v44_comparison_classes.npy",classes)
(out / "figure_data_audit.json").write_text(json.dumps({"scope":"legacy evaluation classes at frame 33",
    "counts":counts,"shape":list(shape),"bounds":list(transform * (0,0))+list(transform * (shape[1],shape[0]))},indent=2),encoding="utf-8")
print(json.dumps(counts))

import sys
from pathlib import Path
import numpy as np
import rasterio

ROOT = Path("D:/VTP")
GIS_DIR = ROOT / "05-Du-lieu-GIS"
RUN_DIR = ROOT / "River_Bathymetry_Project" / "V49_Method1_Runs"
RUN_DIR.mkdir(parents=True, exist_ok=True)
(RUN_DIR / "results").mkdir(parents=True, exist_ok=True)

arms = {
    "CENTRAL": GIS_DIR / "PhuYen_DEM_30m_V48_66Cuts_Plus_V49_Method1_ScopeB1_41Reaches_CENTRAL.tif",
    "LOW": GIS_DIR / "PhuYen_DEM_30m_V48_66Cuts_Plus_V49_Method1_ScopeB1_41Reaches_LOW.tif",
    "HIGH": GIS_DIR / "PhuYen_DEM_30m_V48_66Cuts_Plus_V49_Method1_ScopeB1_41Reaches_HIGH.tif",
}

for arm, tif_path in arms.items():
    asc_path = RUN_DIR / f"V49_Method1_ScopeB1_{arm}.asc"
    prj_path = RUN_DIR / f"V49_Method1_ScopeB1_{arm}.prj"
    print(f"Materializing {arm} from {tif_path.name}...")
    
    with rasterio.open(tif_path) as src:
        data = src.read(1).astype(np.float32)
        profile = src.profile.copy()
        crs_wkt = src.crs.to_wkt()
        transform = src.transform
        
        with rasterio.open(
            asc_path,
            "w",
            driver="AAIGrid",
            width=src.width,
            height=src.height,
            count=1,
            dtype="float32",
            crs=src.crs,
            transform=transform,
            nodata=-9999.0,
            DECIMAL_PRECISION=9,
        ) as dst:
            dst.write(data, 1)
            
    prj_path.write_text(crs_wkt, encoding="utf-8")
    
    # Verify roundtrip
    with rasterio.open(asc_path) as check:
        roundtrip = check.read(1).astype(np.float32)
        assert check.width == profile["width"]
        assert check.height == profile["height"]
        diff = np.max(np.abs(roundtrip.astype(np.float64) - data.astype(np.float64)))
        valid = data != -9999.0
        le_minmask = int((valid & (data <= -4.0)).sum())
        print(f"  -> {arm} ASC generated: {asc_path.stat().st_size / (1024*1024):.1f} MB | max_diff = {diff:.2e} m | cells <= -4.0m: {le_minmask}")

print("ALL ARMS MATERIALIZED SUCCESSFULLY.")

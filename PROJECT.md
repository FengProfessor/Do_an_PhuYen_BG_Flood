# Project: BG_Flood 30m Phu Yen Simulation

## Architecture
The BG_Flood 30m Phu Yen simulation project upgrades the flood inundation model from the legacy 90m full-basin grid to a high-resolution 30m focused domain covering downstream Phu Yen province (from Song Ba Ha dam to the East Sea).

```
[Copernicus GLO-30 DEM] ──> [download_and_clip_dem30m.py] ──> [dem_30m.asc / .tif] (2100x2100, 30m, EPSG:32649)
                                                                       │
[ESA WorldCover 10m] ────> [generate_raw_parameters_30m.py] ──> [manning_30m.asc, il_30m.asc, cl_30m.asc]
                                                                       │
[ERA5 Precipitation] ────> [fetch_rain_era5_30m.py] ──────────> [rain_phuyen_30m.txt / rain map]
                                                                       │
[Song Ba Ha Hydrograph] ──> [setup_inflow_boundary.py] ────────> [Western Inflow river bnd: 11,000 m3/s]
                                                                       │
                                                                       ▼
                                                          [BG_param_PhuYen_30m.txt]
                                                                       │
                                                                       ▼
                                                       [BG_Flood.exe (CUDA GPU)]
                                                                       │
                                      ┌────────────────────────────────┴────────────────────────────────┐
                                      ▼                                                                 ▼
                             [V24_run.log (dt > 1.0s)]                                      [PhuYen_30m.nc (>= 24h)]
```

### Spatial Domain & Grid Specifications
- Coordinate Reference System: WGS 84 / UTM Zone 49N (EPSG:32649)
- Bounding Box:
  - Xmin = 270,000.0 m, Xmax = 333,000.0 m (Width: 63 km)
  - Ymin = 1,415,000.0 m, Ymax = 1,478,000.0 m (Height: 63 km)
- Grid Resolution: cellsize = 30.0 m (dx = 30.0 m, dy = 30.0 m)
- Grid Dimensions: ncols = 2,100, nrows = 2,100 (Total cells: 4,410,000 cells)
- Western Entrance (Song Ba Ha Dam): X ≈ 274,464 m, Y ≈ 1,438,000 m (located at western border X=270,000 m)

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| F1 | Automated 30m DEM Download | Script downloads Copernicus DEM GLO-30 from AWS S3, merges, reprojects to EPSG:32649, clips to [270000, 1415000, 333000, 1478000], saves dem_30m.asc / .tif to 05-Du-lieu-GIS | M1 | ORIGINAL_REQUEST §R1 |
| F2 | Raw Manning 30m Map | Reclassifies raw ESA WorldCover 2021 (10m) directly onto 2100x2100 30m grid into manning_30m.asc (no 90m interpolation) | M2 | ORIGINAL_REQUEST §R2 |
| F3 | Raw Infiltration 30m Maps | Reclassifies raw ESA WorldCover 2021 directly onto 30m grid into il_30m.asc, cl_30m.asc | M2 | ORIGINAL_REQUEST §R2 |
| F4 | ERA5 30m Rainfall Config | Formats ERA5 hourly rainfall for Nov 26 - Dec 01, 2021 for Phu Yen domain | M2 | ORIGINAL_REQUEST §R2 |
| F5 | Western Inflow Boundary Setup | Injects Song Ba Ha 11,000 m³/s discharge as an Inflow Boundary condition at the Western domain edge via BG_Flood river polygon | M3 | ORIGINAL_REQUEST §R3 |
| F6 | BG_Flood 30m Configuration | Configures BG_param_PhuYen_30m.txt with correct bathy, cfmap/roughness, infiltration, river inflow, and CFL parameters (CFL=0.5, dtmin=0.5) | M3 | ORIGINAL_REQUEST §R4 |
| F7 | 5-day Simulation Run & Monitoring | Launches BG_Flood for 120h, monitors V24_run.log, verifies average dt > 1.0s (no collapse to 0.2s) | M4 | ORIGINAL_REQUEST §R4 |
| F8 | NetCDF Output Verification (>=24h) | Verifies generation of PhuYen_30m.nc, size growth, and simulation progressing past 24h (t >= 86,400s) | M4 | ORIGINAL_REQUEST §R4 |
| F9 | Opaque-Box E2E Verification Suite | Independent automated test harness verifying data formats, resolutions, boundary configs, and log metrics | M_E2E | Dual Track E2E |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | DEM 30m Acquisition & Clipping | Download Copernicus DEM 30m COGs from AWS S3, merge, clip to 2100x2100 grid EPSG:32649, save to 05-Du-lieu-GIS | none | PLANNED |
| M2 | Raw Parameter Maps Generation | Generate manning_30m.asc, il_30m.asc, cl_30m.asc from raw ESA WorldCover 10m; generate ERA5 rainfall config | M1 | PLANNED |
| M3 | Western Inflow Boundary & Model Config | Formulate 11,000 m³/s river inflow at western border, assemble BG_param_PhuYen_30m.txt, setup bathy.nc/asc | M1, M2 | PLANNED |
| M4 | Model Run & 24h+ Monitoring | Execute BG_Flood, monitor V24_run.log for dt > 1.0s, confirm PhuYen_30m.nc passes >= 24h milestone | M3 | PLANNED |
| M_E2E | E2E Testing Track | Independent opaque-box test suite verifying all acceptance criteria (Tiers 1-4) | none (parallel) | IN_PROGRESS |

## Interface Contracts

### M1 ↔ M2, M3 (Grid Definition)
- Projection: EPSG:32649 (WGS 84 / UTM zone 49N)
- Header specifications for all ASCII grids (.asc):
  ```
  ncols         2100
  nrows         2100
  xllcorner     270000.000000
  yllcorner     1415000.000000
  cellsize      30.000000
  NODATA_value  -9999
  ```
- File outputs:
  - `D:\VTP\05-Du-lieu-GIS\dem_30m.asc`
  - `D:\VTP\05-Du-lieu-GIS\dem_30m.tif`

### M2 ↔ M3 (Parameter Grids)
- Friction grid: `D:\VTP\05-Du-lieu-GIS\manning_30m.asc` (Values in [0.025, 0.120])
- Initial loss: `D:\VTP\05-Du-lieu-GIS\il_30m.asc` (Values in [0, 50] mm)
- Continuing loss: `D:\VTP\05-Du-lieu-GIS\cl_30m.asc` (Values in [0, 10] mm/h)
- Rainfall file: `D:\VTP\05-Du-lieu-GIS\rain_phuyen_30m.txt` (or hourly uniform precipitation)

### M3 ↔ M4 (Simulation Inputs)
- Working directory: `D:\VTP\BG_Flood_Project\BG_Flood`
- Executable: `D:\VTP\BG_Flood_Project\BG_Flood_Latest\BG_Flood.exe`
- Parameter file: `D:\VTP\BG_Flood_Project\BG_Flood\BG_param_PhuYen_30m.txt` (or `BG_param_DakLak_v24.txt`)
- Inflow Boundary: `river = xa_lu_BaHa_Nov2021.txt, 270000, 272000, 1437000, 1439000;` (exact coordinates on western river channel)
- Output files:
  - Log: `D:\VTP\BG_Flood_Project\BG_Flood\V24_run.log`
  - NetCDF: `D:\VTP\BG_Flood_Project\BG_Flood\PhuYen_30m.nc`

## Code Layout
- Scripts: `D:\VTP\scripts\`
  - `download_and_clip_dem30m.py`: Copernicus DEM 30m download & clipping script
  - `generate_raw_parameters_30m.py`: ESA WorldCover 10m to Manning/IL/CL 30m rasterizer
  - `setup_inflow_boundary.py`: Western boundary river cross-section inflow builder
- GIS outputs: `D:\VTP\05-Du-lieu-GIS\`
  - `dem_30m.asc`, `dem_30m.tif`
  - `manning_30m.asc`, `il_30m.asc`, `cl_30m.asc`
- Model execution: `D:\VTP\BG_Flood_Project\BG_Flood\`
  - `BG_param_PhuYen_30m.txt`
  - `xa_lu_BaHa_Nov2021.txt`
  - `V24_run.log`
  - `PhuYen_30m.nc`
- E2E Tests: `D:\VTP\tests\e2e\`
  - `test_dem_30m.py`
  - `test_parameters_30m.py`
  - `test_boundary_config.py`
  - `test_simulation_progress.py`
  - `run_e2e_tests.py`

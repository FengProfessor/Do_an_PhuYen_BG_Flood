# V49-G Hydraulic Simulation Suite: Final Execution & Evaluation Summary Report

**Generated at (UTC):** 2026-10-19T05:31:36.835659+00:00
**Execution Directory:** `D:\VTP\River_Bathymetry_Project\V49_G_attempt_2`
**Overall Status:** `RUNNING`
**Execution Policy:** `One CUDA run at a time on GPU Device 0; CENTRAL -> LOW -> HIGH -> BASE (120h each)`

---

## 1. Simulation Queue & Arm Execution Record

| Arm | Status | Simulated Time | Wall Duration | NetCDF Valid | Mass Residual (m³) | Relative Residual |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **CENTRAL** | `RUNNING` | 2.3h / 120.0h | 1h 22m 47s (in-progress) | N/A | N/A | N/A |
| **LOW** | `QUEUED` | 0.0h / 120.0h | N/A | N/A | N/A | N/A |
| **HIGH** | `QUEUED` | 0.0h / 120.0h | N/A | N/A | N/A | N/A |
| **BASE** | `QUEUED` | 0.0h / 120.0h | N/A | N/A | N/A | N/A |

---

## 2. Sentinel-1 SAR Evaluation Metrics (t = 101.61h)

Preregistered observation: `DakLak_PhuYen_FloodExtent_Otsu_S1RTC_20211130_05h36_V48.tif`

| Arm | CSI / IoU | F1 Score | Precision | Recall | Simulated Area (km²) | Area Bias | Frame Offset |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **CENTRAL** | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING |
| **LOW** | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING |
| **HIGH** | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING |
| **BASE** | 0.3855 | 0.5565 | 0.5653 | 0.5479 | 500.89 | -0.0309 | 1388.8s |

---

## 3. Post-Run Verification & Preregistered Criteria Assessment

- **Gate-G Pass:** `False`
- **Hydraulic Promotion Ready:** `False`
- **Interpretation:** Matching an observed extent does not resolve missing bathymetry coverage or replace field evidence


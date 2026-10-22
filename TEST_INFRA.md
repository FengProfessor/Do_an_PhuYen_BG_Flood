# E2E Test Infra: BG_Flood 30m Simulation

## Test Philosophy
- Opaque-box, requirement-driven. No dependency on implementation design.
- Derives directly from ORIGINAL_REQUEST.md acceptance criteria and PROJECT.md feature inventory.
- Progressive testability: Each milestone's artifacts are verified with strict, independent validators.

## Feature Inventory & Test Mapping
| # | Feature | Requirement | Tier 1 (Feature) | Tier 2 (Boundary) | Tier 3 (Cross) | Tier 4 (Scenario) |
|---|---------|-------------|:----------------:|:-----------------:|:--------------:|:-----------------:|
| F1 | Automated 30m DEM Download | §R1 | test_dem_exists, test_dem_format | test_dem_bounds, test_dem_cellsize | test_dem_header_alignment | test_full_pipeline |
| F2 | Raw Manning 30m Map | §R2 | test_manning_exists, test_manning_format | test_manning_range, test_manning_cellsize | test_manning_dem_alignment | test_full_pipeline |
| F3 | Raw Infiltration 30m Maps | §R2 | test_il_cl_exists, test_il_cl_format | test_il_cl_values, test_il_cl_cellsize | test_il_manning_alignment | test_full_pipeline |
| F4 | ERA5 30m Rainfall Config | §R2 | test_rain_exists, test_rain_format | test_rain_temporal_coverage | test_rain_simulation_duration | test_full_pipeline |
| F5 | Western Inflow Boundary Setup | §R3 | test_inflow_boundary_syntax | test_inflow_coordinates, test_inflow_discharge | test_inflow_bathy_overlap | test_full_pipeline |
| F6 | BG_Flood 30m Configuration | §R4 | test_param_file_validity | test_cfl_settings, test_friction_aliases | test_param_all_inputs_linked | test_full_pipeline |
| F7 | 5-day Simulation Run & Monitoring | §R4 | test_log_exists, test_no_crash | test_dt_greater_than_1s | test_simulation_progress | test_full_pipeline |
| F8 | NetCDF Output Verification (>=24h) | §R4 | test_nc_file_exists, test_nc_valid | test_nc_growth, test_nc_time_ge_24h | test_nc_variables_structure | test_full_pipeline |

## Test Architecture
- Test runner: `python D:\VTP\tests\e2e\run_e2e_tests.py`
- Test suite directory: `D:\VTP\tests\e2e\`
- Exit code semantics: Exit code 0 if all tests pass; non-zero on failure.
- Output: Structured summary report with pass/fail counts and diagnostic messages.

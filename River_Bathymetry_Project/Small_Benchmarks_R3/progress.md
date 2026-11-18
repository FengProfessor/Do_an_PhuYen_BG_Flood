# R3 small-benchmark package progress

2026-11-18:

- Forked the small package and29-file Python runtime from frozen R2; preserved previous packages/results.
- Corrected gradient halo reconstruction in both vectorized stages; scope wall0/outflow2,uniform grid,halo1. Saved source hashes and focused patch.
- Added read-only per-edge mass-flux observer, two always-wet closed moving-water cases, and three DEM controls (equal volume,rectangle protected,V49 unprotected).
- Added CPU/CUDA operator gate, smoke/closed gates, per-case stop-on-failure, input/runtime/device/output/auxiliary hashes and bounded subprocess execution. Small-only guard caps8192cells/128cells per axis/3600s.
- One PowerShell command runs20 unique cases serially and bundles reports on success/failure. Generated rasters/NC/logs/ZIP remain ignored.
- Verified27benchmark tests +7boundary tests;12R3operator configurations;actual20-case CPU run PASS;185ZIP members verified. CUDA validation remains for simulation machine.
- No field simulation, no ML, no claim of global optimality. See LOCAL_VALIDATION.md and source manifest.

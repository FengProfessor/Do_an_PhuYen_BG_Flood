# Teamwork Project Prompt — Draft

> Status: Launched
> Goal: Craft prompt → get user approval → delegate to teamwork_preview
> Requested team: Small, focused team

This is a single self-contained task; keep it small and focused.

Execute and supervise the V49-G hydraulic simulation suite (CENTRAL, LOW, HIGH, BASE) in a dedicated, isolated attempt directory with active on-screen simulation % progress logging and post-run evaluation.

Working directory: `d:\VTP\River_Bathymetry_Project`
Integrity mode: demo

## Requirements

### R1. Non-Destructive Isolated Execution
Set up a fresh execution directory (e.g. `V49_G_attempt_2`) configured with the frozen V48 R1 runtime and inputs. Ensure the historical 2026-10-14 interrupted run files and recovery artifacts (`V49_G_20261013`, `V49_G_POWERLOSS_RECOVERY_20261014`) remain strictly untouched and preserved.

### R2. Sequential GPU Simulation Queue
Supervise the sequential execution of the 4 simulation arms on CUDA GPU Device 0: CENTRAL → LOW → HIGH → BASE (120 hours simulation time each). Ensure only one CUDA worker runs at any given time to avoid VRAM exhaustion and thermal throttling.

### R3. Real-Time On-Screen Progress Logging
Provide an active monitor/logger that outputs simulation status directly to the console/terminal at regular intervals (every 30–60 seconds). Each log line must display:
- Active Arm name
- Simulated time (hours/seconds) vs. total time (120h / 432,000s)
- Completion percentage (`progress_pct %`)
- Current numerical time step (`dt`)
- Elapsed wall-clock time and estimated time to completion (ETA)

### R4. Automated Post-Run Verification & Preregistered Evaluation
After each arm finishes:
- Verify that the NetCDF output file is structurally valid and non-empty.
- Verify discrete mass budget preservation and closure residual.
- Trigger `v49_evaluate_hydraulic_validation.py` against the preregistered Sentinel-1 observation window (t = 101.61h) and update the attempt execution state.

## Acceptance Criteria

### Preflight & Safety
- [ ] Preflight validation passes with all checks verified before the first worker is launched.
- [ ] No file in `V49_G_20261013` or `V49_G_POWERLOSS_RECOVERY_20261014` is modified or deleted.

### Progress Monitoring
- [ ] Console displays live % progress updates readable on the user's terminal while the engine is running.
- [ ] Log lines format percentage with at least 1 decimal precision (e.g. `[CENTRAL] 35.4h / 120.0h (29.5%) | dt = 0.48s`).

### Execution & Deliverables
- [ ] Supervisor manages worker process lifecycle and logs errors gracefully if interrupted.
- [ ] Completed simulation arms produce valid NetCDF outputs in the results directory.
- [ ] Final summary report summarizes completed runs, simulation durations, and SAR evaluation metrics.

---
*Next: when approved → delegate via invoke_subagent (see Delegation Protocol)*

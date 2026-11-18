# R3 — isolated runtime for small synthetic tests

Derived from `20261118_runtime_fix_r2/python` at commit `6c21583`. R1/R2 remain unchanged. Only `python/bg_flood/flow_gpu.py` differs from R2 in this runtime.

The correction fills the eight h/zs/u/v gradient halos between internal blocks and applies reflection parity to wall gradients before both Kurganov stages. At a wall the normal velocity is odd; h, zs and tangential velocity are even. A normal derivative reverses that parity. Momentum pressure flux is retained. For free outflow, normal gradients are zero and tangential gradients are copied.

**Scope: fixed uniform grid, one halo cell, wall `type=0` and free outflow `type=2` only.** Other physical boundary types raise `NotImplementedError`. This deliberately isolated runtime is not a replacement for the full Phu Yen production run and is not a patch to official upstream BG_Flood C++/CUDA.

Use `River_Bathymetry_Project/Small_Benchmarks_R3/Run-Small-R3.ps1`. Its fixtures and runtime guards prevent provincial-size runs. `operator_checks.py` checks both x/y directions, signs, depth variation, one/four blocks, wall mass flux, internal cancellation, and retained pressure momentum. Full-time closed moving-water cases are checked separately.

Neither passing these cases nor this patch proves general hydraulic validity or accuracy against field measurements. Read the small-test package validation note for actual execution status.

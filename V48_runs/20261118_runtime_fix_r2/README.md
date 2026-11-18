# V48 runtime fix R2 (`20261118_runtime_fix_r2`)

Derived from frozen R1 (`D:\VTP\V48_runs\20261004_runtime_fix_r1`, which remains unmodified) with three verified boundary/flux-halo fixes for `Small_Benchmarks` Option C:
1. `bg_flood/block_index.py`, `bg_flood/flow_gpu.py`, `bg_flood/halo.py`: Inter-block-only flux halo (`flux_halo_*` excludes physical outer domain edges `LB == ib`, `RB == ib`, `BL == ib`, `TL == ib`).
2. `bg_flood/flow_gpu.py`: Apply Predictor `update_bnd(..., evolv=model.evolv)` after `fill_halo_all` (matching Corrector order) while keeping `mainloop.update_bnd` compatible with `v49_runtime_observer.py`.
3. `bg_flood/boundary.py`: Reflective closed wall (`un_new = -un_in` for `side.type == 0`).

This directory is NOT frozen R1; R1 release manifests/launchers were removed from this copy.

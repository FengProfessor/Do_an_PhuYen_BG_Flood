"""Build the separate drainage DEM, D8 directions and accumulation.

Depression filling and flat resolution change elevations for drainage analysis.
These outputs are never hydraulic bathymetry or BG_Flood experiment inputs.
"""
from __future__ import annotations

import os
os.environ.setdefault("NUMBA_NUM_THREADS", "4")
import json
import heapq
from importlib.metadata import version
from pathlib import Path

import numpy as np
import rasterio
from numba import njit
from pysheds.grid import Grid
from pysheds.sview import Raster, ViewFinder
from scipy.ndimage import binary_erosion

from v49_estimate_reach_geometry import DEFAULT_DEM, EXPECTED_DEM_SHA256
from v49_synthesize_hydraulic_bed import sha256_file

OUTPUT = Path(__file__).resolve().parent / "V49_HYDRO_20261013"
D8 = (64, 128, 1, 2, 4, 8, 16, 32)
DR = (-1, -1, 0, 1, 1, 1, 0, -1)
DC = (0, 1, 1, 1, 0, -1, -1, -1)


@njit(cache=False)
def priority_flood(data, valid, boundary):
    """Eight-neighbor boundary flood; no dependency on Numba generator caching."""
    result = data.copy()
    seen = ~valid.copy()
    height, width = data.shape
    heap = [(0., np.int64(0))]
    heap.pop()
    for row in range(height):
        for col in range(width):
            if boundary[row, col]:
                heapq.heappush(heap, (data[row, col], np.int64(row * width + col)))
                seen[row, col] = True
    while heap:
        level, index = heapq.heappop(heap)
        row, col = index // width, index % width
        for k in range(8):
            rr, cc = row + DR[k], col + DC[k]
            if 0 <= rr < height and 0 <= cc < width and not seen[rr, cc]:
                seen[rr, cc] = True
                # A single representable float step gives every interior flat
                # a strictly descending route to its already visited parent.
                elevation = result[rr, cc]
                if elevation <= level:
                    # At zero, nextafter is subnormal and its D8 slope
                    # underflows after division by the 30 m grid spacing.
                    elevation = max(np.nextafter(level, np.inf), level + 1e-9)
                result[rr, cc] = elevation
                heapq.heappush(heap, (elevation, np.int64(rr * width + cc)))
    return result


@njit(cache=False)
def drainage_graph(direction, valid):
    """Independent D8 graph audit and cell accumulation by topological removal."""
    height, width = valid.shape
    size = height * width
    downstream = np.full(size, -1, dtype=np.int64)
    indegree = np.zeros(size, dtype=np.int32)
    accumulation = np.zeros(size, dtype=np.float64)
    queue = np.empty(size, dtype=np.int64)
    tail = 0
    count = 0
    outlets = 0
    for row in range(height):
        for col in range(width):
            if not valid[row, col]:
                continue
            index = row * width + col
            count += 1
            accumulation[index] = 1.
            for k in range(8):
                if direction[row, col] != D8[k]:
                    continue
                rr, cc = row + DR[k], col + DC[k]
                if 0 <= rr < height and 0 <= cc < width and valid[rr, cc]:
                    target = rr * width + cc
                    downstream[index] = target
                    indegree[target] += 1
                break
            if downstream[index] == -1:
                outlets += 1
    for index in range(size):
        if valid[index // width, index % width] and indegree[index] == 0:
            queue[tail] = index
            tail += 1
    head = 0
    while head < tail:
        index = queue[head]
        head += 1
        target = downstream[index]
        if target >= 0:
            accumulation[target] += accumulation[index]
            indegree[target] -= 1
            if indegree[target] == 0:
                queue[tail] = target
                tail += 1
    terminal_sum = 0.
    for index in range(size):
        if valid[index // width, index % width] and downstream[index] == -1:
            terminal_sum += accumulation[index]
    return accumulation.reshape(valid.shape), count - head, outlets, terminal_sum


def condition_array(data, valid, transform, crs):
    view = ViewFinder(affine=transform, shape=data.shape, nodata=-9999., mask=valid, crs=crs)
    dem = Raster(np.where(valid, data, -9999.).astype(np.float64), viewfinder=view)
    grid = Grid(viewfinder=view)
    boundary = valid & ~binary_erosion(valid, structure=np.ones((3, 3)), border_value=0)
    conditioned = Raster(priority_flood(np.asarray(dem), valid, boundary), viewfinder=view)
    directions = np.asarray(grid.flowdir(conditioned, dirmap=D8, nodata_out=0), dtype=np.int16)
    # An unresolved exterior cell is an explicit outlet. An interior pit is a failure.
    unresolved = valid & ~np.isin(directions, D8)
    internal_unresolved = int((unresolved & ~boundary).sum())
    directions[~valid | (unresolved & boundary)] = 0
    accumulation, cycles, outlets, terminal_sum = drainage_graph(directions, valid)
    result = np.where(valid, np.asarray(conditioned, dtype=np.float64), -9999.)
    checks = {"internal_unresolved_cells": internal_unresolved, "cyclic_or_cycle_dependent_cells": int(cycles),
              "outlet_cells": int(outlets), "outlet_accumulation_sum_cells": float(terminal_sum),
              "every_valid_cell_drains_to_an_explicit_outlet": internal_unresolved == 0 and cycles == 0 and terminal_sum == int(valid.sum())}
    return result, directions, accumulation, checks


def build(output_dir=OUTPUT):
    if sha256_file(DEFAULT_DEM) != EXPECTED_DEM_SHA256:
        raise RuntimeError("Frozen source DEM checksum mismatch")
    output_dir.mkdir(parents=True, exist_ok=True)
    with rasterio.open(DEFAULT_DEM) as source:
        data = source.read(1).astype(np.float64)
        valid = (source.read_masks(1) > 0) & np.isfinite(data)
        profile = source.profile.copy()
        conditioned, direction, accumulation, checks = condition_array(data, valid, source.transform, source.crs)
    if not checks["every_valid_cell_drains_to_an_explicit_outlet"]:
        raise RuntimeError(f"Drainage topology failed: {checks}")
    products = {"V49_DEM_HYDRO_CONDITIONED.tif": (conditioned, "float64", -9999.),
                "V49_HYDRO_D8.tif": (direction, "int16", 0),
                "V49_HYDRO_ACCUMULATION_CELLS.tif": (np.where(valid, accumulation, -9999.), "float64", -9999.),
                "V49_HYDRO_DELTA_Z.tif": (np.where(valid, conditioned - data, -9999.), "float64", -9999.)}
    hashes = {}
    for name, (array, dtype, nodata) in products.items():
        path = output_dir / name
        if path.exists():
            raise FileExistsError(path)
        settings = dict(profile, dtype=dtype, nodata=nodata, compress="deflate")
        with rasterio.open(path, "w", **settings) as dataset:
            dataset.write(array.astype(dtype), 1)
            dataset.update_tags(purpose="DRAINAGE_ANALYSIS_ONLY", hydraulic_bed="false", source_sha256=EXPECTED_DEM_SHA256)
        hashes[name] = sha256_file(path)
    delta = conditioned[valid] - data[valid]
    audit = {"schema_version": "V49-hydro-conditioned-1", "status": "PASS_DRAINAGE_TOPOLOGY",
             "purpose": "DRAINAGE_ANALYSIS_ONLY", "usable_as_hydraulic_bed": False,
             "method": "Eight-neighbor priority flood with nextafter flat resolution; pysheds D8; independent cycle/accumulation audit",
             "pysheds_version": version("pysheds"), "flat_resolution": "max(nextafter(parent, +inf), parent + 1e-9 m), stored as float64",
             "source_dem": str(DEFAULT_DEM), "source_sha256": EXPECTED_DEM_SHA256,
             "source_unchanged": sha256_file(DEFAULT_DEM) == EXPECTED_DEM_SHA256,
             "valid_cells": int(valid.sum()), "changed_cells": int((np.abs(delta) > 1e-9).sum()),
             "raised_cells": int((delta > 1e-9).sum()), "lowered_cells": int((delta < -1e-9).sum()),
             "maximum_raise_m": float(delta.max()), "minimum_delta_m": float(delta.min()),
             "outputs_sha256": hashes, "drainage_checks": checks,
             "limitations": "Drainage topology is algorithmic; no surveyed channel bed, reservoir storage, or agreement with all mapped reaches is certified.",
             "method_sources": ["https://arxiv.org/abs/1511.04463", "https://github.com/pysheds/pysheds"],
             "runtime_note": "Local priority-flood implementation avoids the installed pysheds/Numba generator compilation failure; dependency installations are unchanged."}
    (output_dir / "V49_HYDRO_validation_report.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps(audit, indent=2))
    return audit


if __name__ == "__main__":
    build()

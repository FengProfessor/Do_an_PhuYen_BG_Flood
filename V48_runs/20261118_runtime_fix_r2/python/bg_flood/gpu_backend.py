"""
GPU Backend — Tự động chọn CuPy (GPU) hoặc NumPy (CPU).

Sử dụng:
    from .gpu_backend import xp, is_gpu, to_numpy

- xp: module giống numpy (cupy nếu GPU, numpy nếu CPU)
- is_gpu: True nếu đang dùng CuPy
- to_numpy(arr): chuyển array về numpy (cần khi ghi file)
"""

import numpy as np

try:
    import cupy as cp
    # Kiểm tra GPU thực sự khả dụng
    cp.cuda.Device(0).compute_capability
    xp = cp
    is_gpu = True
    print("  [GPU] CuPy detected — using NVIDIA GPU acceleration")
except Exception:
    xp = np
    is_gpu = False
    print("  [CPU] CuPy not available — using NumPy (CPU)")


def to_numpy(arr):
    """Chuyển CuPy array về NumPy (nếu cần). Dùng khi ghi NetCDF."""
    if is_gpu:
        return cp.asnumpy(arr)
    return arr


def to_device(arr):
    """Chuyển NumPy array lên GPU (nếu có CuPy)."""
    if is_gpu:
        return cp.asarray(arr)
    return arr

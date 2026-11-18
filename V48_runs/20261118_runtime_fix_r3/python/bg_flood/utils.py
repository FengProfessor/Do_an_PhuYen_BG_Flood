"""
Hàm tiện ích (Utility functions).
"""

import numpy as np
import math


def sq(a):
    """Bình phương."""
    return a * a


def distance(x1: float, y1: float, x2: float, y2: float) -> float:
    """
    Tính khoảng cách Euclid giữa hai điểm (x1, y1) và (x2, y2).
    """
    return math.sqrt(sq(x1 - x2) + sq(y1 - y2))


def calcres(dx: float, level: int) -> float:
    """
    Tính độ phân giải lưới tại một mức (level).
    level < 0: dx * 2^|level| (lưới thô hơn)
    level >= 0: dx / 2^level (lưới mịn hơn)
    """
    if level < 0:
        return dx * (1 << abs(level))
    else:
        return dx / (1 << level)


def raster_cell_valid(x, y, val, nx, ny, xo, yo, dx, mask):
    """Check source footprint and nearest source-cell validity.

    NoData is categorical: interpolating it with valid elevations invents
    terrain. The half-cell extent allows finer model cells inside the raster
    footprint, but never extends data into padding outside that footprint.
    """
    tolerance = dx * 1e-9
    if (not math.isfinite(x) or not math.isfinite(y)
            or x < xo - 0.5 * dx - tolerance
            or x > xo + (nx - 0.5) * dx + tolerance
            or y < yo - 0.5 * dx - tolerance
            or y > yo + (ny - 0.5) * dx + tolerance):
        return False
    i = max(0, min(nx - 1, math.floor((x - xo) / dx + 0.5)))
    j = max(0, min(ny - 1, math.floor((y - yo) / dx + 0.5)))
    v = val[i + j * nx]
    return math.isfinite(v) and v < mask


def minmod2(theta: float, s0: float, s1: float, s2: float) -> float:
    """
    Hàm giới hạn minmod (minmod limiter).
    theta=1 cho minmod (phổ quát nhất), theta=2 cho superbee (ít tiêu tán nhất).
    """
    if s0 < s1 < s2:
        d1 = theta * (s1 - s0)
        d2 = (s2 - s0) / 2.0
        d3 = theta * (s2 - s1)
        d1 = min(d1, d2)
        return min(d1, d3)
    if s0 > s1 > s2:
        d1 = theta * (s1 - s0)
        d2 = (s2 - s0) / 2.0
        d3 = theta * (s2 - s1)
        d1 = max(d1, d2)
        return max(d1, d3)
    return 0.0


def minmod2_array(theta: float, s0: np.ndarray, s1: np.ndarray, s2: np.ndarray) -> np.ndarray:
    """
    Phiên bản vector hóa của minmod2 cho mảng NumPy.
    """
    result = np.zeros_like(s1)

    # Trường hợp tăng: s0 < s1 < s2
    mask_inc = (s0 < s1) & (s1 < s2)
    if np.any(mask_inc):
        d1 = theta * (s1[mask_inc] - s0[mask_inc])
        d2 = (s2[mask_inc] - s0[mask_inc]) / 2.0
        d3 = theta * (s2[mask_inc] - s1[mask_inc])
        d1 = np.minimum(d1, d2)
        result[mask_inc] = np.minimum(d1, d3)

    # Trường hợp giảm: s0 > s1 > s2
    mask_dec = (s0 > s1) & (s1 > s2)
    if np.any(mask_dec):
        d1 = theta * (s1[mask_dec] - s0[mask_dec])
        d2 = (s2[mask_dec] - s0[mask_dec]) / 2.0
        d3 = theta * (s2[mask_dec] - s1[mask_dec])
        d1 = np.maximum(d1, d2)
        result[mask_dec] = np.maximum(d1, d3)

    return result


def bilinear_interpolation(q11, q12, q21, q22, x1, x2, y1, y2, x, y):
    """Nội suy song tuyến (bilinear interpolation)."""
    x2x1 = x2 - x1
    y2y1 = y2 - y1
    x2x = x2 - x
    y2y = y2 - y
    yy1 = y - y1
    xx1 = x - x1
    return (1.0 / (x2x1 * y2y1)) * (
        q11 * x2x * y2y +
        q21 * xx1 * y2y +
        q12 * x2x * yy1 +
        q22 * xx1 * yy1
    )


def interptime(next_val: float, prev_val: float, timenext: float, time: float) -> float:
    """Nội suy tuyến tính theo thời gian."""
    if timenext == 0.0:
        return prev_val
    return prev_val + (time / timenext) * (next_val - prev_val)


def memloc(halowidth: int, blkmemwidth: int, ix: int, iy: int, ib: int) -> int:
    """
    Tính chỉ số bộ nhớ cho một ô trong block.
    """
    return (ix + halowidth) + (iy + halowidth) * blkmemwidth + ib * (blkmemwidth * blkmemwidth)

"""
Cấu trúc dữ liệu cho các tác động ngoại lực (Forcing)
và điều kiện biên (Boundary Conditions).

Các cấu trúc này phục vụ cho việc:
- Bổ sung mưa, gió, áp suất khí quyển
- Biến dạng đáy (ví dụ: động đất, sóng thần)
- Điều kiện biên động theo thời gian
- Dòng chảy sông
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional
from .input import InputMap, SLTS, River


# ============================================================
# LỰC TĨNH (STATIC FORCING)
# ============================================================

@dataclass
class StaticForcingP:
    """
    Lực tĩnh (không thay đổi theo thời gian).
    Ví dụ:
        - Địa hình đáy (Bathymetry)
        - Hệ số ma sát đáy (cf)
        - Bản đồ thích nghi lưới (AMR target)
    """

    nx: int = 0
    ny: int = 0

    xo: float = 0.0
    yo: float = 0.0
    xmax: float = 0.0
    ymax: float = 0.0
    dx: float = 0.0

    grdalpha: float = 0.0  # Góc quay lưới (nếu có)

    inputfile: str = ""
    extension: str = ""
    varname: str = ""

    val: Optional[np.ndarray] = None  # Mảng giá trị trên lưới


# ============================================================
# LỰC ĐỘNG (DYNAMIC FORCING)
# ============================================================

@dataclass
class DynForcingP:
    """
    Lực động thay đổi theo thời gian.
    Ví dụ:
        - Gió (UWind, VWind)
        - Mưa (Rain)
        - Áp suất khí quyển (Atmp)
    """

    nx: int = 0
    ny: int = 0

    xo: float = 0.0
    yo: float = 0.0
    xmax: float = 0.0
    ymax: float = 0.0
    dx: float = 0.0

    inputfile: str = ""
    extension: str = ""

    nt: int = 0          # Số bước thời gian trong file forcing
    units: str = ""      # Rainfall source units; normalized to m/s by the loader.
    uniform: bool = False  # True nếu forcing đồng nhất toàn miền

    to: float = 0.0      # Thời điểm bắt đầu
    tmax: float = 0.0    # Thời điểm kết thúc
    dt: float = 0.0      # Bước thời gian của forcing

    instep: int = 0      # Chỉ số bước thời gian hiện tại
    nowvalue: float = 0.0  # Giá trị hiện tại (trường hợp uniform)

    val: Optional[np.ndarray] = None  # Mảng dữ liệu gốc
    
    # --- Mở rộng cho Grid-based Rain ---
    station_coords: List[List[float]] = field(default_factory=list) # [[lon1, lat1], [lon2, lat2], ...]
    multi_val: Optional[np.ndarray] = None # Mảng 2D: [time_step, station_index]
    istation: Optional[np.ndarray] = None # Mảng 1D: [cell_index] trỏ tới index của trạm gần nhất
    
    # Grid metadata
    is_grid: bool = False
    lat_range: List[float] = field(default_factory=list)
    lon_range: List[float] = field(default_factory=list)
    nlat: int = 0
    nlon: int = 0


# ============================================================
# BẢN ĐỒ BIẾN DẠNG (DEFORMATION MAP)
# ============================================================

@dataclass
class DeformMap:
    """
    Bản đồ biến dạng địa hình theo thời gian.

    Thường dùng trong:
        - Mô phỏng sóng thần
        - Biến dạng do động đất
        - Thay đổi địa hình đáy theo thời gian
    """

    nx: int = 0
    ny: int = 0

    xo: float = 0.0
    yo: float = 0.0
    xmax: float = 0.0
    ymax: float = 0.0
    dx: float = 0.0

    inputfile: str = ""

    startime: float = 0.0  # Thời điểm bắt đầu biến dạng
    duration: float = 0.0  # Khoảng thời gian biến dạng diễn ra

    val: Optional[np.ndarray] = None


# ============================================================
# THAM SỐ ĐIỀU KIỆN BIÊN
# ============================================================

@dataclass
class BndParam:
    """
    Tham số điều kiện biên theo cạnh miền tính.

    Các loại biên:
        0: Tường cứng (Wall - no slip)
        1: Neumann (gradient bằng 0) [Mặc định]
        2: Dirichlet (áp đặt mực nước)
        3: Biên hấp thụ 1D (Absorbing boundary)
        4: Biên hấp thụ 2D
    """

    data: List[SLTS] = field(default_factory=list)
    on: bool = False

    type: int = 1

    inputfile: str = ""

    nbnd: int = 0  # Số điểm forcing dọc theo cạnh
    nblk: int = 0  # Số block chịu ảnh hưởng

    side: int = 0  # 0:Top, 1:Right, 2:Bottom, 3:Left

    isright: int = 0  # Xác định hướng pháp tuyến theo trục X
    istop: int = 0    # Xác định hướng pháp tuyến theo trục Y

    blks: Optional[np.ndarray] = None  # Danh sách block áp dụng


# ============================================================
# CẤU TRÚC TỔNG HỢP FORCING
# ============================================================

@dataclass
class Forcing:
    """
    Cấu trúc tổng hợp toàn bộ tác động ngoại lực lên mô hình.

    """

    # --- Lực động ---
    UWind: DynForcingP = field(default_factory=DynForcingP)
    VWind: DynForcingP = field(default_factory=DynForcingP)
    Rain: DynForcingP = field(default_factory=DynForcingP)
    Atmp: DynForcingP = field(default_factory=DynForcingP)

    # --- Lực tĩnh ---
    Bathy: List[StaticForcingP] = field(default_factory=list)
    cf: StaticForcingP = field(default_factory=StaticForcingP)

    # --- Biến dạng ---
    deform: List[DeformMap] = field(default_factory=list)

    # --- Dòng chảy sông ---
    rivers: List[River] = field(default_factory=list)

    # --- Điều kiện biên 4 cạnh ---
    right: BndParam = field(default_factory=lambda: BndParam(side=1, isright=1))
    left: BndParam = field(default_factory=lambda: BndParam(side=3, isright=-1))
    top: BndParam = field(default_factory=lambda: BndParam(side=0, istop=1))
    bot: BndParam = field(default_factory=lambda: BndParam(side=2, istop=-1))

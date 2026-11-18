"""
Cấu trúc dữ liệu cho tham số mô hình (Param).
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional

from .input import (                 # tương đương #include "Input.h"
    TSOutNode, FlowIn, River,
    InputMap, SLTS, Windin, PointOut,
)


@dataclass
class Param:
    """
    Lớp chứa tất cả tham số mô hình.
    """
    # Kiểm thử
    test: int = -1  # -1: không test; 0: một số test; 1: test mở rộng

    # Hằng số vật lý
    g: float = 9.81        # Gia tốc trọng trường
    rho: float = 1000.0    # Mật độ chất lỏng
    eps: float = 0.0001    # Độ cao khô (drying height) [m]
    dt: float = 0.0        # Bước thời gian [s]
    CFL: float = 0.5       # Số CFL (Courant-Friedrichs-Lewy)
    theta: float = 1.3     # Hệ số giới hạn minmod (1=minmod, 2=superbee)

    # Ma sát
    frictionmodel: int = 0  # 0: cf thường, 1: Smart, -1: Manning
    cf: float = 0.0001     # Hệ số ma sát đáy
    cfmap: str = ""        # Đường dẫn bản đồ ma sát
    Cd: float = 0.002      # Hệ số kéo gió

    # Lực tác động
    windforcing: bool = False
    atmpforcing: bool = False
    rainforcing: bool = False
    conserve_elevation: bool = False

    # Biên
    leftbnd: bool = False
    rightbnd: bool = False
    topbnd: bool = False
    botbnd: bool = False

    # Áp suất khí quyển
    Pa2m: float = 0.00009916
    Paref: float = 101300.0
    lat: float = 0.0

    # Thấm (Infiltration)
    il: float = 0.0        # Initial Loss [mm]
    cl: float = 0.0        # Continuous Loss [mm/h]
    ilfile: str = ""       # Bản đồ thấm ban đầu
    clfile: str = ""       # Bản đồ thấm liên tục
    infiltration_map: bool = False

    # GPU (trong Python dùng CPU)
    GPUDEVICE: int = -1  # Mặc định CPU trong phiên bản Python

    doubleprecision: int = 0

    # Tham số lưới
    dx: float = float('nan')
    delta: float = 0.0
    nx: int = 0
    ny: int = 0
    nblk: int = 0
    blkwidth: int = 16
    blkmemwidth: int = 0
    blksize: int = 0
    halowidth: int = 1

    xo: float = float('nan')
    yo: float = float('nan')
    ymax: float = float('nan')
    xmax: float = float('nan')
    grdalpha: float = float('nan')
    posdown: int = 0
    spherical: int = 0
    Radius: float = 6371220.0

    # Lưới thích ứng (Adaptation)
    initlevel: int = 0
    maxlevel: int = 0
    minlevel: int = 0
    nblkmem: int = 0
    navailblk: int = 0
    membuffer: float = 1.05

    mask: float = 9999.0
    minmask: float = -1.0

    # File xuất
    outfile: str = "Output.nc"

    # Thời gian
    outputtimestep: float = 0.0
    endtime: float = 0.0
    totaltime: float = 0.0

    # Chuỗi thời gian xuất
    TSnodesout: List[TSOutNode] = field(default_factory=list)
    maxTSstorage: int = 16384

    outvars: List[str] = field(default_factory=list)

    # Sông
    nrivers: int = 0

    # Biên - số lượng block
    nbndblkleft: int = 0
    nbndblkright: int = 0
    nbndblktop: int = 0
    nbndblkbot: int = 0
    nmaskblk: int = 0

    # Khởi tạo nóng/lạnh
    zsinit: float = float('nan')
    zsoffset: float = float('nan')
    hotstartfile: str = ""
    hotstep: int = 0

    # Tham số NetCDF
    smallnc: int = 1
    scalefactor: float = 0.01
    addoffset: float = 0.0

    # Điều khiển xuất
    resetmax: bool = False
    outmax: bool = False
    outmean: bool = False
    outvort: bool = False

    # Biến dạng (deformation)
    deformmaxtime: float = 0.0

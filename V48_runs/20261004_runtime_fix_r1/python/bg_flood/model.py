"""
Cấu trúc dữ liệu cho Model, Block, Evolving, Gradient, Flux, Advance.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, Optional, List
from .input import PointOut


@dataclass
class EvolvingP:
    """
    Biến tiến hóa theo thời gian: mực nước (zs), độ sâu (h),
    vận tốc theo x (u) và y (v).
    """
    zs: Optional[np.ndarray] = None  # Mực nước mặt
    h: Optional[np.ndarray] = None   # Độ sâu nước
    u: Optional[np.ndarray] = None   # Vận tốc theo x
    v: Optional[np.ndarray] = None   # Vận tốc theo y
    cum_infilt: Optional[np.ndarray] = None  # Thấm lũy kế [m]

    def allocate(self, total_size: int):
        self.zs = np.zeros(total_size, dtype=np.float64)
        self.h = np.zeros(total_size, dtype=np.float64)
        self.u = np.zeros(total_size, dtype=np.float64)
        self.v = np.zeros(total_size, dtype=np.float64)
        self.cum_infilt = np.zeros(total_size, dtype=np.float64)


@dataclass
class GradientsP:
    """Gradient của các biến tiến hóa."""
    dzsdx: Optional[np.ndarray] = None
    dhdx: Optional[np.ndarray] = None
    dudx: Optional[np.ndarray] = None
    dvdx: Optional[np.ndarray] = None

    dzsdy: Optional[np.ndarray] = None
    dhdy: Optional[np.ndarray] = None
    dudy: Optional[np.ndarray] = None
    dvdy: Optional[np.ndarray] = None

    def allocate(self, total_size: int):
        self.dzsdx = np.zeros(total_size, dtype=np.float64)
        self.dhdx = np.zeros(total_size, dtype=np.float64)
        self.dudx = np.zeros(total_size, dtype=np.float64)
        self.dvdx = np.zeros(total_size, dtype=np.float64)
        self.dzsdy = np.zeros(total_size, dtype=np.float64)
        self.dhdy = np.zeros(total_size, dtype=np.float64)
        self.dudy = np.zeros(total_size, dtype=np.float64)
        self.dvdy = np.zeros(total_size, dtype=np.float64)


@dataclass
class FluxP:
    """Thông lượng (flux) cho phương trình bảo toàn."""
    Su: Optional[np.ndarray] = None
    Sv: Optional[np.ndarray] = None
    Fqux: Optional[np.ndarray] = None
    Fquy: Optional[np.ndarray] = None
    Fqvx: Optional[np.ndarray] = None
    Fqvy: Optional[np.ndarray] = None
    Fhu: Optional[np.ndarray] = None
    Fhv: Optional[np.ndarray] = None

    def allocate(self, total_size: int):
        self.Su = np.zeros(total_size, dtype=np.float64)
        self.Sv = np.zeros(total_size, dtype=np.float64)
        self.Fqux = np.zeros(total_size, dtype=np.float64)
        self.Fquy = np.zeros(total_size, dtype=np.float64)
        self.Fqvx = np.zeros(total_size, dtype=np.float64)
        self.Fqvy = np.zeros(total_size, dtype=np.float64)
        self.Fhu = np.zeros(total_size, dtype=np.float64)
        self.Fhv = np.zeros(total_size, dtype=np.float64)


@dataclass
class AdvanceP:
    """Giá trị gia tăng (advance) cho dh, dhu, dhv."""
    dh: Optional[np.ndarray] = None
    dhu: Optional[np.ndarray] = None
    dhv: Optional[np.ndarray] = None

    def allocate(self, total_size: int):
        self.dh = np.zeros(total_size, dtype=np.float64)
        self.dhu = np.zeros(total_size, dtype=np.float64)
        self.dhv = np.zeros(total_size, dtype=np.float64)


@dataclass
class BlockP:
    """
    Thông tin block: tọa độ gốc, mức (level),
    và các block lân cận.
    """
    xo: Optional[np.ndarray] = None
    yo: Optional[np.ndarray] = None
    level: Optional[np.ndarray] = None
    active: Optional[np.ndarray] = None

    # Các hàng xóm: BotLeft, BotRight, TopLeft, TopRight,
    # LeftBot, LeftTop, RightBot, RightTop
    BotLeft: Optional[np.ndarray] = None
    BotRight: Optional[np.ndarray] = None
    TopLeft: Optional[np.ndarray] = None
    TopRight: Optional[np.ndarray] = None
    LeftBot: Optional[np.ndarray] = None
    LeftTop: Optional[np.ndarray] = None
    RightBot: Optional[np.ndarray] = None
    RightTop: Optional[np.ndarray] = None

    def allocate(self, nblkmem: int):
        self.xo = np.zeros(nblkmem, dtype=np.float64)
        self.yo = np.zeros(nblkmem, dtype=np.float64)
        self.level = np.zeros(nblkmem, dtype=np.int32)
        self.active = np.full(nblkmem, -1, dtype=np.int32)
        self.BotLeft = np.zeros(nblkmem, dtype=np.int32)
        self.BotRight = np.zeros(nblkmem, dtype=np.int32)
        self.TopLeft = np.zeros(nblkmem, dtype=np.int32)
        self.TopRight = np.zeros(nblkmem, dtype=np.int32)
        self.LeftBot = np.zeros(nblkmem, dtype=np.int32)
        self.LeftTop = np.zeros(nblkmem, dtype=np.int32)
        self.RightBot = np.zeros(nblkmem, dtype=np.int32)
        self.RightTop = np.zeros(nblkmem, dtype=np.int32)


@dataclass
class TimeP:
    """Tham số thời gian."""
    totaltime: float = 0.0
    dt: float = 0.0
    dtmax: Optional[np.ndarray] = None

    def allocate(self, total_size: int):
        self.dtmax = np.full(total_size, np.finfo(np.float64).max, dtype=np.float64)


@dataclass
class Loop:
    """Biến trạng thái cho vòng lặp chính."""
    nextoutputtime: float = 0.0
    dt: float = 0.0
    dtmax: float = 0.0
    totaltime: float = 0.0
    nstep: int = 0
    nstepout: int = 0
    nTSsteps: int = 0
    TSAllout: List[List[PointOut]] = field(default_factory=list)

    windstep: int = 1
    atmpstep: int = 1
    rainstep: int = 1

    uwinduni: float = 0.0
    vwinduni: float = 0.0
    atmpuni: float = 101300.0
    rainuni: float = 0.0

    hugeposval: float = np.finfo(np.float64).max
    hugenegval: float = -np.finfo(np.float64).max
    epsilon: float = np.finfo(np.float64).eps


class Model:
    """
    Lớp chứa toàn bộ dữ liệu mô hình.
    """

    def __init__(self):
        self.evolv = EvolvingP()
        self.evolv_o = EvolvingP()
        self.grad = GradientsP()
        self.flux = FluxP()
        self.adv = AdvanceP()
        self.time = TimeP()
        self.blocks = BlockP()
        self.loop = Loop()

        # Địa hình đáy và ma sát
        self.zb: Optional[np.ndarray] = None
        self.cf: Optional[np.ndarray] = None
        self.il: Optional[np.ndarray] = None
        self.cl: Optional[np.ndarray] = None

        # Áp suất khí quyển
        self.Patm: Optional[np.ndarray] = None

        # Xuất
        self.OutputVarMap: Dict[str, np.ndarray] = {}

        # Chuỗi thời gian
        self.TSstore: Optional[np.ndarray] = None
        self.vort: Optional[np.ndarray] = None

        # Mean/Max
        self.evmean = EvolvingP()
        self.evmax = EvolvingP()

    def allocate(self, nblkmem: int, blksize: int):
        """Cấp phát bộ nhớ cho tất cả mảng."""
        total_size = nblkmem * blksize

        self.evolv.allocate(total_size)
        self.evolv_o.allocate(total_size)
        self.grad.allocate(total_size)
        self.flux.allocate(total_size)
        self.adv.allocate(total_size)
        self.time.allocate(total_size)
        self.blocks.allocate(nblkmem)

        self.zb = np.zeros(total_size, dtype=np.float64)
        self.cf = np.full(total_size, 0.0001, dtype=np.float64)
        self.il = np.full(total_size, 0.0, dtype=np.float64)
        self.cl = np.full(total_size, 0.0, dtype=np.float64)

        # Mean/Max arrays
        self.evmean.allocate(total_size)
        self.evmax.allocate(total_size)

        # Thiết lập bản đồ xuất
        self.OutputVarMap = {
            'zs': self.evolv.zs,
            'h': self.evolv.h,
            'u': self.evolv.u,
            'v': self.evolv.v,
            'zb': self.zb,
            'cum_infilt': self.evolv.cum_infilt,
        }

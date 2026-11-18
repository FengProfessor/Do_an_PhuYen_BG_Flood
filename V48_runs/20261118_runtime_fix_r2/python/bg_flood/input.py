"""
Cấu trúc dữ liệu đầu vào (Input Data Structures).

Chứa các class dữ liệu nhỏ: TSOutNode, FlowIn, River,
InputMap, SLTS, Windin, PointOut.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class TSOutNode:
    """
    Điểm xuất chuỗi thời gian.
    """
    i: int = 0
    j: int = 0
    block: int = 0
    x: float = 0.0
    y: float = 0.0
    outname: str = ""


@dataclass
class FlowIn:
    """
    Dữ liệu lưu lượng đầu vào theo thời gian.
    """
    time: float = 0.0
    q: float = 0.0


@dataclass
class River:
    """
    Thông tin sông.
    Tương đương River trong C++.
    """
    i: List[int] = field(default_factory=list)
    j: List[int] = field(default_factory=list)
    block: List[int] = field(default_factory=list)
    disarea: float = 0.0
    xstart: float = 0.0
    xend: float = 0.0
    ystart: float = 0.0
    yend: float = 0.0
    river_flow_file: str = ""
    flow_input: List[FlowIn] = field(default_factory=list)


@dataclass
class InputMap:
    """
    Thông tin bản đồ đầu vào.
    """
    nx: int = 0
    ny: int = 0
    xo: float = 0.0
    yo: float = 0.0
    xmax: float = 0.0
    ymax: float = 0.0
    dx: float = 0.0
    grdalpha: float = 0.0
    inputfile: str = ""
    extension: str = ""
    varname: str = ""


@dataclass
class SLTS:
    """
    Dữ liệu chuỗi thời gian mực nước biên.

    """
    time: float = 0.0
    wlevs: List[float] = field(default_factory=list)
    uuvel: List[float] = field(default_factory=list)
    vvvel: List[float] = field(default_factory=list)


@dataclass
class Windin:
    """
    Dữ liệu gió đầu vào.
    """
    time: float = 0.0
    wspeed: float = 0.0
    wdirection: float = 0.0
    uwind: float = 0.0
    vwind: float = 0.0


@dataclass
class PointOut:
    """
    Xuất dữ liệu điểm.
    """
    time: float = 0.0
    zs: float = 0.0
    h: float = 0.0
    u: float = 0.0
    v: float = 0.0

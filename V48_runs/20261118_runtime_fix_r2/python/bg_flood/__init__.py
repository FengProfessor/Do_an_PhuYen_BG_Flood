"""
BG_Flood - Block-structured Godunov-type Flood Model
=====================================================

Mô hình giải phương trình nước nông (Shallow Water Equations)
sử dụng phương pháp Kurganov-Petrova (2007) trên lưới khối (block-structured grid).
"""

from .input import TSOutNode, FlowIn, River, InputMap, SLTS, Windin, PointOut
from .param import Param
from .model import Model, EvolvingP, GradientsP, FluxP, AdvanceP, BlockP
from .forcing import Forcing, BndParam
from .read_input import read_param_file
from .mesh import init_mesh
from .flow_cpu import flow_cpu
from .mainloop import main_loop
from .write_output import save_to_netcdf

__version__ = "1.0.0"

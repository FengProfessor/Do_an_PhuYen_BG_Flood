
"""
BG_Flood - Block-structured Godunov-type Flood Model
=====================================================
Mô hình giải phương trình nước nông 2D (Shallow Water Equations)
sử dụng thuật toán Kurganov-Petrova (2007) trên lưới khối (block-structured grid).
"""

import sys
import os
import time

# Thêm đường dẫn
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')


from bg_flood.param import Param
from bg_flood.model import Model
from bg_flood.forcing import Forcing
from bg_flood.read_input import read_param_file, read_bathy_data
from bg_flood.read_forcing import prepare_forcing
from bg_flood.mesh import init_mesh, transfer_to_gpu
from bg_flood.initial_conditions import init_evolv
from bg_flood.mainloop import main_loop
from bg_flood.write_txtlog import create_logfile, save_param_to_log, log


def print_banner():
    """In banner chào mừng."""
    print("=" * 60)
    print("  BG_Flood - Mô hình lũ lụt Godunov khối-cấu trúc")
    print("  (Block-structured Godunov-type Flood Model)")
    print("=" * 60)
    print(f"  Giải phương trình nước nông 2D (SWE)")
    print(f"  Thuật toán: Kurganov-Petrova (2007)")
    print(f"  Lưới: Block-structured adaptive mesh")
    print("=" * 60)


def run_model(param_file: str = "BG_param_hue_quickcheck.txt"):
    """
    Chạy toàn bộ mô hình BG_Flood.
    
    Tham số:
        param_file: Đường dẫn đến file tham số BG_param.txt
    """
    total_start = time.time()

    print_banner()

    # Tạo file log
    create_logfile()

    # ========================================
    # 1. Đọc tham số
    # ========================================
    param, forcing = read_param_file(param_file)

    # ========================================
    # 2. Đọc dữ liệu đầu vào (địa hình, biên, v.v.)
    # ========================================
    log("Đọc dữ liệu đầu vào...")
    param, forcing = read_bathy_data(forcing, param)

    # 2b. Đọc dữ liệu forcing (mưa, gió, v.v.)
    prepare_forcing(param, forcing)

    # ========================================
    # 3. Ghi tham số ra log + in tổng kết
    # ========================================
    save_param_to_log(param, forcing)
    print("\n--- Tổng kết tham số ---")
    print(f"  Lưới: {param.nx} x {param.ny}")
    print(f"  dx = {param.dx}")
    print(f"  Miền: x=[{param.xo}, {param.xmax}], y=[{param.yo}, {param.ymax}]")
    print(f"  Thời gian kết thúc: {param.endtime} s")
    print(f"  Bước xuất: {param.outputtimestep} s")
    print(f"  CFL = {param.CFL}")
    print(f"  eps = {param.eps}")
    
    # Hiển thị Ma sát (thông minh hơn)
    if param.cfmap:
        print(f"  Ma sát (cf) = Bản đồ: {param.cfmap} (Manning model={param.frictionmodel})")
    else:
        print(f"  Ma sát (cf) = {param.cf} (Constant)")

    # Hiển thị Thấm (Infiltration)
    if param.ilfile or param.clfile:
        il_str = f"Bản đồ: {param.ilfile}" if param.ilfile else f"{param.il}"
        cl_str = f"Bản đồ: {param.clfile}" if param.clfile else f"{param.cl}"
        print(f"  Thấm: IL={il_str}, CL={cl_str}")
    else:
        print(f"  Thấm: IL={param.il}, CL={param.cl} (Constant)")
    print(f"  Block width = {param.blkwidth}")
    print(f"  Halo width = {param.halowidth}")
    print(f"  Block mem width = {param.blkmemwidth}")
    print(f"  Block size = {param.blksize}")
    print(f"  File xuất: {param.outfile}")
    print(f"  Biến xuất: {param.outvars}")
    print(f"  Biên trái: {'Có' if param.leftbnd else 'Không'}")
    print(f"  Biên phải: {'Có' if param.rightbnd else 'Không'}")
    print(f"  Biên trên: {'Có' if param.topbnd else 'Không'}")
    print(f"  Biên dưới: {'Có' if param.botbnd else 'Không'}")
    print("---")

    # ========================================
    # 4. Khởi tạo mô hình
    # ========================================
    model = Model()

    # 4a. Khởi tạo lưới
    init_mesh(param, forcing, model)

    # 4b. Khởi tạo điều kiện ban đầu
    init_evolv(param, forcing, model)

    # 4c. Chuyển dữ liệu lên GPU (nếu có CuPy)
    transfer_to_gpu(model)

    setup_time = time.time() - total_start
    print(f"\nThời gian khởi tạo: {setup_time:.2f} giây")

    # ========================================
    # 5. Chạy vòng lặp chính
    # ========================================
    loop = main_loop(param, forcing, model)

    # ========================================
    # 6. Tổng kết
    # ========================================
    total_time = time.time() - total_start
    print(f"\nTổng thời gian chạy: {total_time:.2f} giây")
    print("BG_Flood hoàn tất thành công!")

    return param, forcing, model, loop


if __name__ == "__main__":
    if len(sys.argv) > 1:
        param_file = sys.argv[1]
    else:
        param_file = "BG_param.txt"

    run_model(param_file)

"""
Ghi log ra file text và console.
"""

import math
import os
from datetime import datetime
from .param import Param
from .forcing import Forcing

# Tên file log
_LOG_FILE = "BG_log.txt"


def create_logfile():
    """
    Tạo (reset) file log và ghi header.
    Tương đương create_logfile() trong C++.
    """
    with open(_LOG_FILE, 'w', encoding='utf-8') as f:
        f.write("")  # truncate

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Đã tắt ghi log file BG_log.txt
    pass


def log(text: str):
    """
    In ra console và ghi vào file log.
    Tương đương log() trong C++.
    """
    print(text)
    # Đã tắt ghi log file BG_log.txt
    pass


def write_text_to_log_file(text: str):
    """
    Ghi một dòng vào file log (append).
    Tương đương write_text_to_log_file() trong C++.
    """
    # Đã tắt ghi log file BG_log.txt
    pass


def save_param_to_log(param: Param, forcing: Forcing = None):
    """
    Ghi tóm tắt tham số mô hình ra file log.
    """
    pi = math.pi

    write_text_to_log_file("")
    write_text_to_log_file("###################################")
    write_text_to_log_file("### Summary of model parameters ###")
    write_text_to_log_file("###################################")

    # Bathymetry
    write_text_to_log_file("# Bathymetry file")
    write_text_to_log_file(f"posdown = {param.posdown};")
    write_text_to_log_file(f"dx = {param.dx};")
    grdalpha_deg = param.grdalpha * 180.0 / pi if not math.isnan(param.grdalpha) else 0.0
    write_text_to_log_file(f"grdalpha = {grdalpha_deg};")
    write_text_to_log_file(f"xo = {param.xo};")
    write_text_to_log_file(f"yo = {param.yo};")
    write_text_to_log_file(f"xmax = {param.xmax};")
    write_text_to_log_file(f"ymax = {param.ymax};")
    write_text_to_log_file("")

    # GPU/CPU
    write_text_to_log_file(f"gpudevice = {param.GPUDEVICE};")
    write_text_to_log_file("")

    # Flow parameters
    write_text_to_log_file("# Flow parameters")
    write_text_to_log_file(f"eps = {param.eps};")
    write_text_to_log_file(f"cf = {param.cf};")
    write_text_to_log_file(f"theta = {param.theta};")
    write_text_to_log_file(f"Cd = {param.Cd};")
    write_text_to_log_file("")

    # Timekeeping
    write_text_to_log_file("# Timekeeping parameters")
    write_text_to_log_file(f"CFL = {param.CFL};")
    write_text_to_log_file(f"totaltime = {param.totaltime}; # Start time")
    write_text_to_log_file(f"endtime = {param.endtime};")
    write_text_to_log_file(f"outputtimestep = {param.outputtimestep};")

    # Output vars
    alloutvars = ", ".join(param.outvars)
    write_text_to_log_file(f"outvars = {alloutvars};")
    write_text_to_log_file("")

    # Files
    write_text_to_log_file("# Files")
    write_text_to_log_file(f"outfile = {param.outfile};")
    write_text_to_log_file(f"smallnc = {param.smallnc}; #if smallnc==1 all Output are scaled and saved as a short int")
    if param.smallnc == 1:
        write_text_to_log_file(f"scalefactor = {param.scalefactor};")
        write_text_to_log_file(f"addoffset = {param.addoffset};")

    # TS output nodes
    if param.TSnodesout:
        for o in range(len(param.TSnodesout)):
            nd = param.TSnodesout[o]
            write_text_to_log_file(f"TSOfile = {nd.outname},{nd.x},{nd.y};")
    write_text_to_log_file("")

    # Boundaries
    write_text_to_log_file("# Boundaries")
    write_text_to_log_file("# 0:wall; 1: Neumann (Default); 2:Dirichlet (zs); 3: abs1d")
    if forcing is not None:
        if forcing.right.inputfile:
            write_text_to_log_file(f"rightbndfile = {forcing.right.inputfile};")
        if forcing.left.inputfile:
            write_text_to_log_file(f"leftbndfile = {forcing.left.inputfile};")
        if forcing.top.inputfile:
            write_text_to_log_file(f"topbndfile = {forcing.top.inputfile};")
        if forcing.bot.inputfile:
            write_text_to_log_file(f"botbndfile = {forcing.bot.inputfile};")

    # Hot start
    if param.hotstartfile:
        write_text_to_log_file(f"hotstartfile = {param.hotstartfile};")
        write_text_to_log_file(f"hotstep = {param.hotstep};")

    write_text_to_log_file("")
    write_text_to_log_file("# Others")
    write_text_to_log_file(f"g = {param.g};")
    write_text_to_log_file(f"rho = {param.rho};")
    write_text_to_log_file("")

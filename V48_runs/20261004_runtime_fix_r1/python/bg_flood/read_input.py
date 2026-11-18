"""
Đọc file tham số và dữ liệu đầu vào.
"""

import os
import math
import numpy as np
from typing import Optional

from .param import Param
from .input import TSOutNode, SLTS
from .forcing import Forcing, StaticForcingP, BndParam


def is_number(s: str) -> bool:
    """Kiểm tra xem chuỗi có phải là số không."""
    try:
        float(s)
        return True
    except ValueError:
        return False


def find_parameter(param_names, line: str) -> Optional[str]:
    """
    Tìm tham số trong một dòng của file BG_param.txt.
    Hỗ trợ cả chuỗi đơn và danh sách chuỗi.
    """
    if isinstance(param_names, str):
        param_names = [param_names]

    for param_name in param_names:
        # Tìm dạng: param_name = value
        line_stripped = line.strip()
        if line_stripped.lower().startswith(param_name.lower()):
            parts = line_stripped.split('=', 1)
            if len(parts) == 2:
                # Kiểm tra tên tham số
                key = parts[0].strip()
                if key.lower() == param_name.lower():
                    value = parts[1].strip()
                    # Loại bỏ comment sau dấu #
                    if '#' in value:
                        value = value[:value.index('#')].strip()
                    # Loại bỏ comment sau //
                    if '//' in value:
                        value = value[:value.index('//')].strip()
                    # Loại bỏ dấu ; ở cuối (C-style)
                    value = value.rstrip(';').strip()
                    if value:
                        return value
    return None


def read_param_str_param(line: str, param: Param) -> Param:
    """Đọc tham số từ một dòng và cập nhật Param."""

    # Tham số chung
    val = find_parameter("test", line)
    if val:
        param.test = int(val)

    val = find_parameter(["gpudevice", "GPUDEVICE"], line)
    if val:
        param.GPUDEVICE = int(val)

    val = find_parameter("doubleprecision", line)
    if val:
        param.doubleprecision = int(val)

    # Adaptation
    val = find_parameter("maxlevel", line)
    if val:
        param.maxlevel = int(val)

    val = find_parameter("minlevel", line)
    if val:
        param.minlevel = int(val)

    val = find_parameter("initlevel", line)
    if val:
        param.initlevel = int(val)

    val = find_parameter("conserveelevation", line)
    if val:
        param.conserve_elevation = val.lower() in ("true", "1")

    val = find_parameter("membuffer", line)
    if val:
        param.membuffer = float(val)

    # Flow
    val = find_parameter("eps", line)
    if val:
        param.eps = float(val)

    val = find_parameter("frictionmodel", line)
    if val:
        param.frictionmodel = int(val)

    val = find_parameter(["cf", "cfmap", "roughnessmap"], line)
    if val:
        if is_number(val):
            param.cf = float(val)
        else:
            param.cfmap = val

    val = find_parameter("Cd", line)
    if val:
        param.Cd = float(val)

    val = find_parameter("Pa2m", line)
    if val:
        param.Pa2m = float(val)

    val = find_parameter("Paref", line)
    if val:
        param.Paref = float(val)

    val = find_parameter("mask", line)
    if val:
        param.mask = float(val)

    val = find_parameter("minmask", line)
    if val:
        param.minmask = float(val)

    # Infiltration
    val = find_parameter(["il", "initialloss", "Rain_il", "ilfile"], line)
    if val:
        if is_number(val):
            param.il = float(val)
        else:
            param.ilfile = val

    val = find_parameter(["cl", "continuousloss", "Rain_cl", "clfile"], line)
    if val:
        if is_number(val):
            param.cl = float(val)
        else:
            param.clfile = val

    # Time
    val = find_parameter("dt", line)
    if val:
        param.dt = float(val)

    val = find_parameter("CFL", line)
    if val:
        param.CFL = float(val)

    val = find_parameter("theta", line)
    if val:
        param.theta = float(val)

    val = find_parameter(["outputtimestep", "outtimestep"], line)
    if val:
        param.outputtimestep = float(val)

    val = find_parameter("endtime", line)
    if val:
        param.endtime = float(val)

    val = find_parameter("totaltime", line)
    if val:
        param.totaltime = float(val)

    # Input/Output
    val = find_parameter("outfile", line)
    if val:
        param.outfile = val

    val = find_parameter("TSOutput", line)
    if val:
        items = [s.strip() for s in val.split(',')]
        if len(items) >= 3:
            node = TSOutNode()
            node.outname = items[0]
            node.x = float(items[1])
            node.y = float(items[2])
            param.TSnodesout.append(node)

    val = find_parameter("outvars", line)
    if val:
        supported = {"zb", "zs", "u", "v", "h", "hmean", "zsmean", "umean", "vmean",
                      "hmax", "zsmax", "umax", "vmax", "vort"}
        alias_map = {"hh": "h", "uu": "u", "vv": "v"}
        vars_list = [s.strip() for s in val.split(',')]
        for v in vars_list:
            mapped = alias_map.get(v, v)
            if mapped in supported:
                param.outvars.append(mapped)
            if 'mean' in v:
                param.outmean = True
            if 'max' in v:
                param.outmax = True
            if v == 'vort':
                param.outvort = True

    val = find_parameter("resetmax", line)
    if val:
        param.resetmax = bool(int(val))

    # Grid
    val = find_parameter("nx", line)
    if val:
        param.nx = int(val)

    val = find_parameter("ny", line)
    if val:
        param.ny = int(val)

    val = find_parameter("dx", line)
    if val:
        param.dx = float(val)

    val = find_parameter("grdalpha", line)
    if val:
        param.grdalpha = float(val)

    val = find_parameter(["xo", "xmin"], line)
    if val:
        param.xo = float(val)

    val = find_parameter(["yo", "ymin"], line)
    if val:
        param.yo = float(val)

    val = find_parameter("xmax", line)
    if val:
        param.xmax = float(val)

    val = find_parameter("ymax", line)
    if val:
        param.ymax = float(val)

    val = find_parameter("g", line)
    if val:
        param.g = float(val)

    val = find_parameter("rho", line)
    if val:
        param.rho = float(val)

    val = find_parameter("smallnc", line)
    if val:
        param.smallnc = int(val)

    val = find_parameter("scalefactor", line)
    if val:
        param.scalefactor = float(val)

    val = find_parameter("addoffset", line)
    if val:
        param.addoffset = float(val)

    val = find_parameter("posdown", line)
    if val:
        param.posdown = int(val)

    val = find_parameter(["initzs", "zsinit"], line)
    if val:
        param.zsinit = float(val)

    val = find_parameter("zsoffset", line)
    if val:
        param.zsoffset = float(val)

    val = find_parameter("hotstartfile", line)
    if val:
        param.hotstartfile = val

    val = find_parameter("hotstep", line)
    if val:
        param.hotstep = int(val)

    val = find_parameter("spherical", line)
    if val:
        param.spherical = int(val)

    val = find_parameter("Radius", line)
    if val:
        param.Radius = float(val)

    val = find_parameter("lat", line)
    if val:
        param.lat = float(val)

    val = find_parameter(["frictionmodel", "friction"], line)
    if val:
        param.frictionmodel = int(val)

    val = find_parameter("blkwidth", line)
    if val:
        param.blkwidth = int(val)

    return param


def read_param_str_forcing(line: str, forcing: Forcing) -> Forcing:
    """Đọc tham số lực tác động từ một dòng."""

    val = find_parameter("bathy", line)
    if val:
        bathy = StaticForcingP()
        bathy = _read_file_info(val, bathy)
        forcing.Bathy.append(bathy)

    val = find_parameter("roughnessmap", line)
    if val:
        forcing.cf = _read_file_info(val, forcing.cf)

    # Đọc biên theo cách tương thích với C++:
    # Hỗ trợ: leftbndfile, leftbnd, left (và tương tự cho right, top, bot)
    # Format: name = type  HOẶC  name = file,type  HOẶC  name = file
    for side_name, side_obj_name in [("left", "left"), ("right", "right"),
                                      ("top", "top"), ("bot", "bot")]:
        aliases = [f"{side_name}bndfile", f"{side_name}bnd", side_name]
        if side_name == "bot":
            aliases.append("bottom")
        val = find_parameter(aliases, line)
        if val:
            side = getattr(forcing, side_obj_name)
            items = [x.strip() for x in val.split(',')]
            if len(items) == 1:
                # Một giá trị: nếu là số → type, nếu là file → inputfile
                try:
                    side.type = int(items[0])
                    side.on = True
                except ValueError:
                    side.inputfile = items[0]
                    side.on = True
            elif len(items) >= 2:
                # Hai giá trị: file,type
                side.inputfile = items[0]
                try:
                    side.type = int(items[1])
                except ValueError:
                    pass
                side.on = True
            setattr(forcing, side_obj_name, side)

    # Vẫn hỗ trợ leftbndtype riêng cho tương thích ngược
    val = find_parameter("leftbndtype", line)
    if val:
        forcing.left.type = int(val)

    val = find_parameter("rightbndtype", line)
    if val:
        forcing.right.type = int(val)

    val = find_parameter("topbndtype", line)
    if val:
        forcing.top.type = int(val)

    val = find_parameter("botbndtype", line)
    if val:
        forcing.bot.type = int(val)

    val = find_parameter("windfile", line)
    if val:
        forcing.UWind.inputfile = val

    val = find_parameter("rainfile", line)
    if val:
        forcing.Rain.inputfile = val

    val = find_parameter("rainunits", line)
    if val:
        forcing.Rain.units = val.strip().lower()

    val = find_parameter("atmpfile", line)
    if val:
        forcing.Atmp.inputfile = val

    val = find_parameter("rain_stations", line)
    if val:
        # Kiểm tra xem có phải định dạng GRID không
        if val.startswith("GRID"):
            pass

    val = find_parameter("river", line)
    if val:
        items = [x.strip() for x in val.split(',')]
        if len(items) >= 5:
            from .input import River
            riv = River()
            riv.river_flow_file = items[0]
            riv.xstart = float(items[1])
            riv.xend = float(items[2])
            riv.ystart = float(items[3])
            riv.yend = float(items[4])
            if len(items) >= 6:
                riv.radius = float(items[5])
            forcing.rivers.append(riv)
            
    val = find_parameter("pointsource", line)
    if val:
        items = [x.strip() for x in val.split(',')]
        if len(items) >= 4:
            from .input import River
            riv = River()
            riv.river_flow_file = items[0]
            cx = float(items[1])
            cy = float(items[2])
            rad = float(items[3])
            riv.xstart = cx - rad
            riv.xend = cx + rad
            riv.ystart = cy - rad
            riv.yend = cy + rad
            riv.radius = rad
            forcing.rivers.append(riv)

            parts = val.split(',')
            # Định dạng: GRID,lat_min,lat_max,nlat,lon_min,lon_max,nlon
            forcing.Rain.is_grid = True
            forcing.Rain.lat_range = [float(parts[1]), float(parts[2])]
            forcing.Rain.nlat = int(parts[3])
            forcing.Rain.lon_range = [float(parts[4]), float(parts[5])]
            forcing.Rain.nlon = int(parts[6])
        else:
            # Format cũ: lon1,lat1; lon2,lat2; ...
            station_groups = val.split(';')
            for group in station_groups:
                group = group.strip()
                if not group: continue
                coords = [float(x.strip()) for x in group.split(',')]
                if len(coords) == 2:
                    forcing.Rain.station_coords.append(coords)

    return forcing


def _read_file_info(input_str: str, outinfo):
    """
    Phân tích tên file và extension.
    Hỗ trợ dạng: file.ext hoặc file.ext?varname
    """
    parts = input_str.split('.')
    if len(parts) >= 2:
        ext_parts = parts[-1].split('?')
        outinfo.extension = ext_parts[0]
        if len(ext_parts) > 1:
            outinfo.varname = ext_parts[-1]
        outinfo.inputfile = '.'.join(parts[:-1]) + '.' + outinfo.extension
    return outinfo


def read_param_file(filename: str = "BG_param.txt"):
    """
    Đọc file BG_param.txt và trả về Param và Forcing.
    """
    param = Param()
    forcing = Forcing()

    print(f"\nĐọc file {filename}...")

    if not os.path.exists(filename):
        print(f"LỖI: Không tìm thấy file {filename}")
        raise FileNotFoundError(f"File {filename} không tồn tại")

    with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                param = read_param_str_param(line, param)
                forcing = read_param_str_forcing(line, forcing)

    # Cập nhật trạng thái biên
    param.leftbnd = forcing.left.on
    param.rightbnd = forcing.right.on
    param.topbnd = forcing.top.on
    param.botbnd = forcing.bot.on

    # Default outvars nếu chưa chỉ định (giống C++)
    if not param.outvars and param.outputtimestep > 0.0:
        param.outvars = ['zb', 'zs', 'u', 'v', 'h']

    # Tính blkmemwidth và blksize
    param.blkmemwidth = param.blkwidth + 2 * param.halowidth
    param.blksize = param.blkmemwidth * param.blkmemwidth

    print(f"\tĐã đọc xong file tham số")

    return param, forcing


def read_asc_bathy(filename: str):
    """
    Đọc file địa hình định dạng ASCII (.asc).
    Trả về: nx, ny, xo, yo, dx, data
    """
    with open(filename, 'r') as f:
        header = {}
        for _ in range(6):
            line = f.readline().strip().split()
            header[line[0].lower()] = float(line[1])

        nx = int(header.get('ncols', 0))
        ny = int(header.get('nrows', 0))
        dx = header.get('cellsize', 0.0)
        if nx <= 0 or ny <= 0 or dx <= 0:
            raise ValueError(f"Invalid ASC dimensions or cellsize in {filename}")
        # Raster samples are at cell centers. Model bounds are outer edges.
        xo = header['xllcenter'] if 'xllcenter' in header else header['xllcorner'] + 0.5*dx
        yo = header['yllcenter'] if 'yllcenter' in header else header['yllcorner'] + 0.5*dx
        nodata = header.get('nodata_value', -9999.0)

        # Đọc dữ liệu
        data = []
        for line in f:
            row = [float(v) for v in line.strip().split()]
            data.append(row)

        data = np.array(data, dtype=np.float64)
        if data.shape != (ny, nx):
            raise ValueError(f"ASC shape {data.shape} differs from ({ny}, {nx}) in {filename}")

        # ASC lưu từ trên xuống (hàng đầu = y cao nhất), đảo lại cho đúng hệ tọa độ
        data = np.flipud(data)

        # Chuyển thành mảng 1D theo thứ tự C++ (x nhanh nhất)
        # Trong C++: val[i + j*nx] với i là cột (x), j là hàng (y)
        # Sau flipud, data[j, i] = giá trị tại (x=i, y=j)
        # ravel() row-major: data[j, i] → index = j*nx + i  ≡  val[i + j*nx]
        data_1d = data.ravel()  # Không cần transpose

    return nx, ny, xo, yo, dx, nodata, data_1d


def read_bnd_file(filename: str) -> BndParam:
    """
    Đọc file điều kiện biên.
    Trả về danh sách SLTS (chuỗi thời gian mực nước biên).
    """
    bnd = BndParam()
    bnd.inputfile = filename
    bnd.on = True

    if not os.path.exists(filename):
        print(f"CẢNH BÁO: File biên {filename} không tồn tại")
        bnd.on = False
        return bnd

    with open(filename, 'r') as f:
        lines = f.readlines()

    # Phân tích file biên - định dạng đơn giản: time wlev [u] [v]
    data = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        vals = [float(v) for v in line.split()]
        if len(vals) >= 2:
            slts = SLTS()
            slts.time = vals[0]
            slts.wlevs = [vals[1]]
            if len(vals) >= 3:
                slts.uuvel = [vals[2]]
            if len(vals) >= 4:
                slts.vvvel = [vals[3]]
            data.append(slts)

    bnd.data = data
    bnd.nbnd = 1  # Mặc định 1 biên đồng nhất

    return bnd


def read_bathy_data(forcing: Forcing, param: Param) -> tuple:
    """
    Đọc dữ liệu địa hình từ file và cập nhật forcing và param.
    """
    for bathy in forcing.Bathy:
        if bathy.inputfile:
            print(f"\tĐọc file địa hình: {bathy.inputfile}")
            if bathy.extension.lower() == 'asc':
                nx, ny, xo, yo, dx, nodata, data = read_asc_bathy(bathy.inputfile)
                bathy.nx = nx
                bathy.ny = ny
                bathy.xo = xo
                bathy.yo = yo
                bathy.dx = dx
                bathy.xmax = xo + (nx - 1) * dx
                bathy.ymax = yo + (ny - 1) * dx
                bathy.val = data

                if param.posdown == 1:
                    bathy.val = -bathy.val

                # Thay nodata hoặc giá trị quá thấp (minmask) bằng giá trị an toàn (mask)
                # để mesh.py biết chỗ nào không tính toán.
                bathy.val[bathy.val == nodata] = param.mask
                bathy.val[bathy.val <= param.minmask] = param.mask

            elif bathy.extension.lower() == 'nc':
                try:
                    import netCDF4 as nc4
                    ds = nc4.Dataset(bathy.inputfile)
                    varname = bathy.varname if bathy.varname else 'zb'

                    # Tìm biến
                    if varname not in ds.variables:
                        for v in ds.variables:
                            if v not in ds.dimensions:
                                varname = v
                                break

                    var = ds.variables[varname]
                    data = var[:].filled(param.mask)

                    # Tìm tọa độ
                    dims = var.dimensions
                    if len(dims) >= 2:
                        yvar = ds.variables[dims[-2]][:]
                        xvar = ds.variables[dims[-1]][:]
                    else:
                        xvar = ds.variables[list(ds.dimensions.keys())[-1]][:]
                        yvar = ds.variables[list(ds.dimensions.keys())[-2]][:]

                    bathy.nx = len(xvar)
                    bathy.ny = len(yvar)
                    
                    x0, x1 = float(xvar[0]), float(xvar[-1])
                    y0, y1 = float(yvar[0]), float(yvar[-1])
                    
                    bathy.xo = min(x0, x1)
                    bathy.yo = min(y0, y1)
                    bathy.dx = abs(float(xvar[1] - xvar[0])) if len(xvar) > 1 else 1.0
                    bathy.xmax = max(x0, x1)
                    bathy.ymax = max(y0, y1)

                    if data.ndim == 3:
                        data = data[0]
                    
                    if float(yvar[0]) > float(yvar[-1]):
                        data = np.flipud(data)

                    bathy.val = data.ravel()

                    if param.posdown == 1:
                        bathy.val = -bathy.val

                    # Áp dụng minmask cho dữ liệu NetCDF
                    bathy.val[bathy.val <= param.minmask] = param.mask

                    ds.close()
                except ImportError:
                    print("LỖI: Cần cài đặt netCDF4 để đọc file .nc")
                    raise

            print(f"\t\tnx={bathy.nx}, ny={bathy.ny}, dx={bathy.dx}")
            print(f"\t\txo={bathy.xo}, yo={bathy.yo}")
            print(f"\t\txmax={bathy.xmax}, ymax={bathy.ymax}")

    # Cập nhật param từ bathy nếu chưa được thiết lập
    if forcing.Bathy and not math.isnan(forcing.Bathy[0].dx):
        b = forcing.Bathy[0]
        if math.isnan(param.dx):
            param.dx = b.dx
        if math.isnan(param.xo):
            param.xo = b.xo - 0.5*b.dx
        if math.isnan(param.yo):
            param.yo = b.yo - 0.5*b.dx
        if math.isnan(param.xmax):
            param.xmax = b.xmax + 0.5*b.dx
        if math.isnan(param.ymax):
            param.ymax = b.ymax + 0.5*b.dx

        # Tính nx, ny nếu chưa có
        if param.nx == 0:
            param.nx = int(round((param.xmax - param.xo) / param.dx))
        if param.ny == 0:
            param.ny = int(round(abs(param.ymax - param.yo) / param.dx))


    # Đọc file biên nếu có
    if forcing.left.on and forcing.left.inputfile:
        old_type = forcing.left.type
        forcing.left = read_bnd_file(forcing.left.inputfile)
        forcing.left.type = old_type
        forcing.left.isright = -1
        forcing.left.side = 3

    if forcing.right.on and forcing.right.inputfile:
        old_type = forcing.right.type
        forcing.right = read_bnd_file(forcing.right.inputfile)
        forcing.right.type = old_type
        forcing.right.isright = 1
        forcing.right.side = 1

    if forcing.top.on and forcing.top.inputfile:
        old_type = forcing.top.type
        forcing.top = read_bnd_file(forcing.top.inputfile)
        forcing.top.type = old_type
        forcing.top.istop = 1
        forcing.top.side = 0

    if forcing.bot.on and forcing.bot.inputfile:
        old_type = forcing.bot.type
        forcing.bot = read_bnd_file(forcing.bot.inputfile)
        forcing.bot.type = old_type
        forcing.bot.istop = -1
        forcing.bot.side = 2

    return param, forcing

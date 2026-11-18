"""
Đọc và chuẩn bị forcing (mưa, gió, áp suất) từ file.
"""

import os
import re
from .input import Windin
from .forcing import Forcing


def _rain_unit_factor(filename: str, configured_units: str = ""):
    """Resolve source units explicitly and normalize rainfall exactly once."""
    header_units = ""
    with open(filename, "r", encoding="utf-8-sig") as source:
        for line in source:
            if not line.strip():
                continue
            if not line.lstrip().startswith("#"):
                break
            match = re.search(r"(?<![a-z])(?:mm/h|mm/hr|m/s)(?![a-z])", line, re.I)
            if match:
                header_units = match.group(0).lower().replace("mm/hr", "mm/h")
                break
    configured_units = configured_units.strip().lower().replace("mm/hr", "mm/h")
    if configured_units and header_units and configured_units != header_units:
        raise ValueError(f"Rain units conflict: config={configured_units}, header={header_units} in {filename}")
    units = configured_units or header_units
    factors = {"m/s": 1.0, "mm/h": 1.0/3600000.0}
    if units not in factors:
        raise ValueError(f"Rain units missing/unsupported in {filename}; set rainunits = m/s or mm/h")
    return units, factors[units]


def read_uni_forcing_file(filename: str):
    """
    Đọc file forcing dạng uniform (2 cột: time, value).
    """
    if not os.path.isfile(filename):
        raise FileNotFoundError(
            f"ERROR: Rainfall/Forcing file could not be opened: {filename}")

    data = []
    with open(filename, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            parts = line.split('\t')
            if len(parts) < 2:
                parts = line.split()
            if len(parts) < 2:
                parts = line.split(',')
            if len(parts) < 2:
                raise ValueError(
                    f"ERROR: Forcing file format error: {len(parts)} columns, need 2")

            w = Windin()
            w.time = float(parts[0])
            w.wspeed = float(parts[1])
            # Lưu tất cả các giá trị cột sau cột thời gian
            w.all_vals = [float(x) for x in parts[1:]] 
            
            if len(parts) >= 3:
                w.uwind = float(parts[1])
                w.vwind = float(parts[2])
            data.append(w)

    return data


def prepare_forcing(param, forcing: Forcing):
    """
    Đọc tất cả file forcing được khai báo trong BG_param.txt.
    Gọi sau read_param_file() và trước mainloop.
    """
    # ---- Rain ----
    if forcing.Rain.inputfile:
        print(f"\nPreparing Rain forcing: {forcing.Rain.inputfile}")
        forcing.Rain.unidata = read_uni_forcing_file(forcing.Rain.inputfile)
        source_units, factor = _rain_unit_factor(forcing.Rain.inputfile, forcing.Rain.units)
        for row in forcing.Rain.unidata:
            row.all_vals = [value * factor for value in row.all_vals]
            row.wspeed = row.all_vals[0]
        forcing.Rain.units = "m/s"
        forcing.Rain.source_units = source_units
        print(f"  Rain units: {source_units} -> m/s (factor={factor:g})")
        forcing.Rain.nowvalue = 0.0

        if forcing.Rain.unidata:
            forcing.Rain.to = forcing.Rain.unidata[0].time
            forcing.Rain.tmax = forcing.Rain.unidata[-1].time
            forcing.Rain.nt = len(forcing.Rain.unidata)
            print(f"  Time range: {forcing.Rain.to:.1f} - {forcing.Rain.tmax:.1f} s")
            print(f"  Data points: {forcing.Rain.nt}")
            forcing.Rain.nowvalue = forcing.Rain.unidata[0].wspeed
            
            # Tự động phát hiện số lượng cột trong file
            n_cols_in_file = len(forcing.Rain.unidata[0].all_vals)
            n_stations_config = len(forcing.Rain.station_coords)

            if n_cols_in_file > 1:
                # File có nhiều cột -> Chế độ Spatial
                forcing.Rain.uniform = False
                n_stations = n_cols_in_file
                forcing.Rain.multi_val = []
                for row in forcing.Rain.unidata:
                    forcing.Rain.multi_val.append(row.all_vals)
                import numpy as np
                forcing.Rain.multi_val = np.array(forcing.Rain.multi_val)
                print(f"  Detected Spatial Rain in file: {n_stations} stations")
                
                if not forcing.Rain.is_grid and n_stations_config != n_stations:
                    print(f"  WARNING: File has {n_stations} stations but BG_param.txt defines {n_stations_config}.")
                    if n_stations_config == 0:
                        print(f"  ERROR: Please add 'rain_stations' to BG_param.txt to use spatial rainfall.")
                elif forcing.Rain.is_grid:
                    expected = forcing.Rain.nlat * forcing.Rain.nlon
                    if n_stations != expected:
                        print(f"  ERROR: Grid rain file has {n_stations} columns but expected {expected} ({forcing.Rain.nlon}x{forcing.Rain.nlat}).")

            else:
                # Chỉ có 1 cột dữ liệu (sau cột thời gian) -> Chế độ Uniform
                forcing.Rain.uniform = True
                print(f"  Using Uniform Rain mode.")

        param.rainforcing = True

    # ---- Atmospheric Pressure ----
    if forcing.Atmp.inputfile:
        print(f"\nPreparing Atmp forcing: {forcing.Atmp.inputfile}")
        forcing.Atmp.uniform = True
        forcing.Atmp.unidata = read_uni_forcing_file(forcing.Atmp.inputfile)
        forcing.Atmp.nowvalue = 0.0

    # ---- Wind ----
    if forcing.UWind.inputfile:
        print(f"\nPreparing Wind forcing: {forcing.UWind.inputfile}")
        wind_data = read_uni_forcing_file(forcing.UWind.inputfile)

        forcing.UWind.uniform = True
        forcing.UWind.unidata = []
        forcing.UWind.nowvalue = 0.0

        forcing.VWind.uniform = True
        forcing.VWind.unidata = []
        forcing.VWind.nowvalue = 0.0

        for row in wind_data:
            wu = Windin()
            wu.time = row.time
            wu.wspeed = row.uwind if row.uwind != 0.0 or row.vwind != 0.0 else row.wspeed
            forcing.UWind.unidata.append(wu)

            wv = Windin()
            wv.time = row.time
            wv.wspeed = row.vwind if row.uwind != 0.0 or row.vwind != 0.0 else 0.0
            forcing.VWind.unidata.append(wv)

        if forcing.UWind.unidata:
            forcing.UWind.to = forcing.UWind.unidata[0].time
            forcing.UWind.tmax = forcing.UWind.unidata[-1].time
            forcing.UWind.nt = len(forcing.UWind.unidata)
            forcing.UWind.nowvalue = forcing.UWind.unidata[0].wspeed

            forcing.VWind.to = forcing.VWind.unidata[0].time
            forcing.VWind.tmax = forcing.VWind.unidata[-1].time
            forcing.VWind.nt = len(forcing.VWind.unidata)
            forcing.VWind.nowvalue = forcing.VWind.unidata[0].wspeed

    # ---- Rivers ---- (BUG FIX: river flow files were parsed but never loaded!)
    from .input import FlowIn
    for river in forcing.rivers:
        if river.river_flow_file:
            print(f"\nPreparing River forcing: {river.river_flow_file}")
            raw = read_uni_forcing_file(river.river_flow_file)
            river.flow_input = []
            for row in raw:
                fi = FlowIn()
                fi.time = row.time
                fi.q = row.wspeed  # wspeed column = Q (m3/s)
                river.flow_input.append(fi)
            if river.flow_input:
                print(f"  Time range: {river.flow_input[0].time:.1f} - {river.flow_input[-1].time:.1f} s")
                print(f"  Q range: {min(f.q for f in river.flow_input):.1f} - {max(f.q for f in river.flow_input):.1f} m3/s")
                print(f"  Data points: {len(river.flow_input)}")

    print()

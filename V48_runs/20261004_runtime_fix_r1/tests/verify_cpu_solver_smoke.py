"""A closed 32x32 domain must gain 10 mm after one hour at 10 mm/hour."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import netCDF4
import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix="v48_rain_smoke_") as directory:
        tmp=Path(directory)
        dem=tmp/"dem.asc"
        with dem.open("w",encoding="utf-8") as stream:
            stream.write("ncols 32\nnrows 32\nxllcorner 270000\nyllcorner 1415000\ncellsize 30\nNODATA_value -9999\n")
            np.savetxt(stream,np.zeros((32,32)),fmt="%.1f")
        rain=tmp/"rain.txt"
        rain.write_text("# constant rainfall (mm/h)\n0 10\n3600 10\n",encoding="utf-8")
        out=tmp/"rain.nc"
        config=tmp/"BG_param.txt"
        config.write_text(f"bathy = {dem.as_posix()};\ndx = 30;\ndy = 30;\nminmask = -4;\n"
                          f"rainfile = {rain.as_posix()};\nrainunits = mm/h;\nzsinit = 0;\nil = 0;\ncl = 0;\n"
                          f"left = 0;\nright = 0;\ntop = 0;\nbottom = 0;\nendtime = 3600;\n"
                          f"outputtimestep = 1200;\noutfile = {out.as_posix()};\noutvars = h, zb, zs;\n",encoding="utf-8")
        driver=ROOT/"python/run_bgflood.py"
        bootstrap="import runpy,sys; sys.modules['cupy']=None; sys.argv=[sys.argv[1],sys.argv[2]]; runpy.run_path(sys.argv[0],run_name='__main__')"
        log=ROOT/"results/cpu_solver_smoke.log"
        with log.open("w",encoding="utf-8") as stream:
            done=subprocess.run([sys.executable,"-X","utf8","-B","-c",bootstrap,str(driver),str(config)],
                                cwd=tmp,stdout=stream,stderr=subprocess.STDOUT,timeout=120)
        assert done.returncode==0, f"Solver failed; see {log}"
        with netCDF4.Dataset(out) as ds:
            times=np.asarray(ds["time"][:],dtype=float)
            assert len(times)==3 and abs(times[-1]-3600)<1e-4,times
            max_error=0.
            for i,t in enumerate(times):
                h=np.asarray(ds["h"][i],dtype=float)
                expected=t*10/3600000.
                max_error=max(max_error,float(np.max(np.abs(h-expected))))
                np.testing.assert_allclose(h,expected,rtol=1e-5,atol=1e-8)
            result={"status":"PASS","backend":"CPU NumPy","time_s":float(times[-1]),
                    "frame_times_s":times.tolist(),"shape":list(h.shape),
                    "rainfall_mm_per_hour":10,"expected_depth_m_after_one_hour":.01,
                    "observed_depth_min_m":float(h.min()),"observed_depth_max_m":float(h.max()),
                    "max_abs_depth_error_m":max_error,"driver":str(driver)}
    (ROOT/"results/cpu_solver_smoke.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2))


if __name__=="__main__":
    main()

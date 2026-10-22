import time
import subprocess
import shutil
import os
import netCDF4 as nc

NC_PATH = r"D:\VTP\V45_runs\20260928_engine_r1\results\PhuYen_30m_V45_exploratory.nc"
OUT_IMG = r"D:\VTP\V45_runs\20260928_engine_r1\results\SAR_vs_Sim_V45_Frame9_30h.png"
OUT_JSON = r"D:\VTP\V45_runs\20260928_engine_r1\results\V45_Frame9_metrics.json"
ARTIFACT_IMG = r"C:\Users\CuongHM\.gemini\antigravity\brain\2a14d3b9-0c61-4507-b922-ac4882d9ae0d\V45_Frame9_30h_Evaluation.png"

print("Starting Watcher for Frame 9 (30h = 108,000s)...")

max_checks = 120 # up to 20 minutes
for check in range(max_checks):
    try:
        if os.path.exists(NC_PATH):
            with nc.Dataset(NC_PATH, "r") as ds:
                n_frames = len(ds.variables["time"])
                times = [float(t) for t in ds.variables["time"][:]]
                print(f"[Check {check+1}] Current frames: {n_frames}, Latest time: {times[-1] if times else 0}s")
                if n_frames >= 10 and times[-1] >= 108000.0:
                    print("\n>>> FRAME 9 (30h) COMMITTED TO NETCDF! <<<")
                    break
    except Exception as e:
        print(f"[Check {check+1}] Note: {e}")
    time.sleep(10)

print("\nRunning eval_v45.py for Frame 9...")
cmd = [
    "python",
    r"D:\VTP\eval_v45.py",
    "--frame", "9",
    "--out-img", OUT_IMG,
    "--out-json", OUT_JSON
]
res = subprocess.run(cmd, capture_output=True, text=True)
print(res.stdout)
if res.stderr:
    print("Stderr:", res.stderr)

if os.path.exists(OUT_IMG):
    shutil.copyfile(OUT_IMG, ARTIFACT_IMG)
    print(f"Copied {OUT_IMG} to {ARTIFACT_IMG}")

print("Frame 9 processing completed.")

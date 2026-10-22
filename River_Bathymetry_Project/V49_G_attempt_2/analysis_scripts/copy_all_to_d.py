import os
import shutil
import glob

brain_dir = r"C:\Users\CuongHM\.gemini\antigravity\brain\303aa3cb-1e89-49b2-8549-ccb345e3d166"
dst_base = r"D:\VTP\River_Bathymetry_Project\V49_G_attempt_2\visual_reports"
dst_scripts = r"D:\VTP\River_Bathymetry_Project\V49_G_attempt_2\analysis_scripts"
os.makedirs(dst_base, exist_ok=True)
os.makedirs(dst_scripts, exist_ok=True)

copied_files = []

# 1. Copy all PNGs
for png in glob.glob(os.path.join(brain_dir, "*.png")):
    fname = os.path.basename(png)
    dst = os.path.join(dst_base, fname)
    shutil.copy2(png, dst)
    copied_files.append((fname, dst, os.path.getsize(dst)))

# 2. Copy markdown reports
for md in glob.glob(os.path.join(brain_dir, "*.md")):
    fname = os.path.basename(md)
    dst = os.path.join(dst_base, fname)
    shutil.copy2(md, dst)
    copied_files.append((fname, dst, os.path.getsize(dst)))

# 3. Copy scratch scripts
scratch_dir = os.path.join(brain_dir, "scratch")
if os.path.exists(scratch_dir):
    for py in glob.glob(os.path.join(scratch_dir, "*.py")):
        fname = os.path.basename(py)
        dst = os.path.join(dst_scripts, fname)
        shutil.copy2(py, dst)
        copied_files.append((fname, dst, os.path.getsize(dst)))

# 4. Copy live task log snapshot
task_log = os.path.join(brain_dir, ".system_generated", "tasks", "task-373.log")
if os.path.exists(task_log):
    dst_log = r"D:\VTP\River_Bathymetry_Project\V49_G_attempt_2\supervisor_live_console.log"
    shutil.copy2(task_log, dst_log)
    copied_files.append(("task-373.log", dst_log, os.path.getsize(dst_log)))

print(f"Successfully copied {len(copied_files)} items to Drive D:")
for name, path, sz in copied_files:
    print(f" - {name} ({sz/1024:.1f} KB) -> {path}")

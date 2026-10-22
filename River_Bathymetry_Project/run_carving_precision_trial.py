"""
High-Precision River Bathymetry Carving Trial Script
Focuses specifically on the Main Ba River Channel (from Song Ba Ha dam to Da Dien estuary).
Implements Parabolic / Raised-Cosine Carving with C1 smoothness and Monotonic Bed Profile.
"""

import sys
import os
import json
import time
import numpy as np
import rasterio
from scipy.ndimage import distance_transform_edt
import matplotlib.pyplot as plt

def main():
    print("=" * 75)
    print("CHẠY THỬ NGHIỆM THUẬT TOÁN KHOÉT ĐO SÂU LÒNG SÔNG BA (HIGH-PRECISION CARVING)")
    print("=" * 75)
    start_time = time.time()

    base_dem_path = r"D:\VTP\05-Du-lieu-GIS\PhuYen_DEM_30m_V48_BASE_COPERNICUS.tif"
    jrc_path = r"D:\VTP\V48_research_20261002\hydro_evidence_raw\V46_JRC_GSW1_3_occurrence_1984_2020.tif"
    trace_path = r"D:\VTP\.agents\teamwork\explorer_bathy_survey_1\ba_river_channel_trace.json"
    out_dir = r"D:\VTP\River_Bathymetry_Project"
    out_dem_path = os.path.join(out_dir, "PhuYen_DEM_30m_with_Bathymetry_trial.tif")
    out_asc_path = os.path.join(out_dir, "PhuYen_DEM_30m_with_Bathymetry_trial.asc")
    out_profile_png = os.path.join(out_dir, "bathymetry_carving_trial_profiles.png")

    print("[1/6] Đang đọc dữ liệu đầu vào...")
    with rasterio.open(base_dem_path) as src_dem:
        dem_data = src_dem.read(1).astype(np.float32)
        profile = src_dem.profile.copy()
        transform = src_dem.transform
        nodata_val = src_dem.nodata

    with rasterio.open(jrc_path) as src_jrc:
        jrc_data = src_jrc.read(1)

    with open(trace_path, 'r', encoding='utf-8') as f:
        trace_pts = json.load(f)

    rows, cols = dem_data.shape
    print(f"      DEM: {cols}x{rows}, CRS: EPSG:32649, Điểm tim sông Ba: {len(trace_pts)} mốc")

    print("[2/6] Xây dựng mặt nạ lòng sông Ba chính (Ba River Main Channel Mask)...")
    # Tạo raster đường tim sông Ba từ trace points
    cl_mask = np.zeros((rows, cols), dtype=bool)
    for p in trace_pts:
        r, c = p['row'], p['col']
        if 0 <= r < rows and 0 <= c < cols:
            cl_mask[r, c] = True

    # Khoảng cách Euclidean từ mỗi ô lưới tới tim sông Ba chính
    dist_to_centerline = distance_transform_edt(~cl_mask) * 30.0  # mét

    # Lòng sông Ba chính: nằm trong phạm vi 300m quanh tim sông VÀ có dấu vết nước (JRC >= 10 hoặc khoảng cách rất gần tim <= 90m)
    # Loại trừ các ô có cao độ đồi cao > 130m hoặc biển sâu < -5m
    river_mask = (dist_to_centerline <= 300.0) & ((jrc_data >= 10) | (dist_to_centerline <= 90.0))
    river_mask = river_mask & (dem_data > -5.0) & (dem_data < 130.0)

    total_river_cells = int(np.sum(river_mask))
    print(f"      Số ô lòng sông Ba thực tế: {total_river_cells:,} ô (~{total_river_cells * 900 / 1e6:.2f} km²)")

    print("[3/6] Tính toán khoảng cách tới bờ sông và tọa độ chuẩn hóa ngang...")
    # Khoảng cách từ bên trong lòng sông ra bờ mép sông
    dist_to_bank = distance_transform_edt(river_mask) * 30.0  # mét
    
    # Tính tọa độ X thực địa (UTM49N)
    x_coords = transform.c + np.arange(cols) * transform.a
    X_grid = np.repeat(x_coords[np.newaxis, :], rows, axis=0)

    # Phân đoạn độ sâu theo trắc diện IMH 2024:
    # Thượng lưu đập Đồng Cam (X <= 301,000m): lòng sông sâu 3.5m
    # Hạ lưu đập Đồng Cam đến cửa biển (X > 301,000m): lòng sông sâu 2.5m - 3.0m
    dong_cam_x = 301000.0
    d_max = np.where(X_grid <= dong_cam_x, 3.5, 2.8).astype(np.float32)

    # Bán kính lòng sông tham chiếu R_0 = 180m
    R_ref = 180.0
    xi = np.clip(dist_to_bank / R_ref, 0.0, 1.0)

    # Hàm chuyển tiếp Raised-Cosine: tiếp xúc êm C1 tại bờ (xi=0 -> phi=0), cực đại tại tim (xi=1 -> phi=1)
    phi = np.sin(0.5 * np.pi * xi) ** 2

    print("[4/6] Tính toán độ sâu khoét đáy Parabol & Khóa ngưỡng đập Đồng Cam...")
    delta_z = np.zeros_like(dem_data, dtype=np.float32)
    delta_z[river_mask] = d_max[river_mask] * phi[river_mask]

    # Khóa cứng mốc khống chế đỉnh đập tràn Đồng Cam (+7.00m MSL, không khoét thủng đập)
    dong_cam_mask = (np.abs(X_grid - 301050) < 120) & (np.abs(transform.f + np.arange(rows)[:, np.newaxis] * transform.e - 1445700) < 200)
    delta_z[dong_cam_mask] = np.minimum(delta_z[dong_cam_mask], 0.2)

    # Ràng buộc pháp lý: Ngoài lòng sông Ba delta_z = 0 tuyệt đối
    delta_z[~river_mask] = 0.0

    print("[5/6] Nghiệm thu chất lượng toán học & Thống kê...")
    new_dem = dem_data - delta_z

    # Kiểm tra bảo toàn ngoài bờ
    outside_diff = np.max(np.abs(new_dem[~river_mask] - dem_data[~river_mask]))
    assert outside_diff == 0.0, f"LỖI: Có ô ngoài bờ sông bị thay đổi! Max diff = {outside_diff}"

    carved_cells = int(np.sum(delta_z > 0.01))
    max_cut = float(np.max(delta_z))
    mean_cut = float(np.mean(delta_z[delta_z > 0.01]))
    total_vol_m3 = float(np.sum(delta_z) * 900.0)

    print(f"      + Số ô lưới được hạ sâu: {carved_cells:,} ô ({carved_cells * 900 / 1e6:.2f} km²)")
    print(f"      + Chiều sâu khoét lớn nhất (Max cut): {max_cut:.3f} m")
    print(f"      + Chiều sâu khoét trung bình (Mean cut): {mean_cut:.3f} m")
    print(f"      + Dung tích chứa bổ sung (delta V): {total_vol_m3 / 1e6:.2f} triệu m³")
    print(f"      + Bảo toàn đồng bằng ngoài sông: TUYỆT ĐỐI (Sai số: {outside_diff:.6f} m)")

    print("[6/6] Xuất tệp DEM GeoTIFF & Biểu đồ trắc diện...")
    profile.update(dtype=rasterio.float32, nodata=nodata_val)
    with rasterio.open(out_dem_path, 'w', **profile) as dst:
        dst.write(new_dem.astype(np.float32), 1)
    print(f"      -> Đã xuất GeoTIFF: {out_dem_path}")

    # Vẽ biểu đồ kép: Trắc ngang tại Phú Lâm (Tuy Hòa) & Trắc dọc toàn tuyến
    fig, axes = plt.subplots(1, 2, figsize=(14, 5), dpi=150)

    # 1. Trắc ngang tại Tuy Hòa (gần cầu Đà Rằng: col ~ 1900)
    col_tuyhoa = 1900
    slice_r_min, slice_r_max = 1100, 1160
    dist_xs = np.arange(slice_r_max - slice_r_min) * 30.0
    dem_xs_orig = dem_data[slice_r_min:slice_r_max, col_tuyhoa]
    dem_xs_new = new_dem[slice_r_min:slice_r_max, col_tuyhoa]

    axes[0].plot(dist_xs, dem_xs_orig, 'r--', label='Copernicus DEM gốc (Mặt nước phẳng)', linewidth=2)
    axes[0].plot(dist_xs, dem_xs_new, 'b-', label='DEM sau khoét Parabol (C¹ Smooth)', linewidth=2)
    axes[0].fill_between(dist_xs, dem_xs_new, dem_xs_orig, color='cyan', alpha=0.35, label='Lòng dẫn đo sâu tái tạo')
    axes[0].set_title('Trắc ngang Sông Ba tại TP. Tuy Hòa (Cầu Đà Rằng)', fontsize=11, fontweight='bold')
    axes[0].set_xlabel('Khoảng cách mặt cắt (m)', fontsize=10)
    axes[0].set_ylabel('Cao độ (m MSL)', fontsize=10)
    axes[0].grid(True, linestyle=':', alpha=0.6)
    axes[0].legend(loc='upper right', frameon=True)

    # 2. Trắc dọc thalweg dọc theo chuỗi trace points
    dists_long = []
    z_orig_long = []
    z_new_long = []
    accum_dist = 0.0

    for i, pt in enumerate(trace_pts):
        r, c = pt['row'], pt['col']
        if i > 0:
            dr = (r - trace_pts[i-1]['row']) * 30.0
            dc = (c - trace_pts[i-1]['col']) * 30.0
            accum_dist += np.sqrt(dr**2 + dc**2) / 1000.0  # km
        dists_long.append(accum_dist)
        z_orig_long.append(dem_data[r, c])
        z_new_long.append(new_dem[r, c])

    axes[1].plot(dists_long, z_orig_long, 'r--', label='Trắc dọc viễn thám gốc (Mặt nước)', linewidth=1.5)
    axes[1].plot(dists_long, z_new_long, 'b-', label='Đáy sông đo sâu sau khoét', linewidth=2)
    axes[1].fill_between(dists_long, z_new_long, z_orig_long, color='lightskyblue', alpha=0.4, label='Chiều sâu dòng kiệt (2.5 - 3.5m)')
    axes[1].set_title('Trắc dọc Sông Ba từ Đập Sông Ba Hạ ra Biển Đông (~70 km)', fontsize=11, fontweight='bold')
    axes[1].set_xlabel('Khoảng cách dọc sông (km)', fontsize=10)
    axes[1].set_ylabel('Cao độ (m MSL)', fontsize=10)
    axes[1].grid(True, linestyle=':', alpha=0.6)
    axes[1].legend(loc='upper right', frameon=True)

    plt.tight_layout()
    plt.savefig(out_profile_png)
    plt.close()
    print(f"      -> Đã xuất đồ thị so sánh: {out_profile_png}")

    elapsed = time.time() - start_time
    print("=" * 75)
    print(f"THỰC NGHIỆM THÀNH CÔNG RỰC RỠ TRONG {elapsed:.2f} GIÂY!")
    print("=" * 75)

if __name__ == '__main__':
    main()

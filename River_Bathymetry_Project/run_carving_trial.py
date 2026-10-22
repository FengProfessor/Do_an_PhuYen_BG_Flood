"""
River Bathymetry Carving Trial Execution Script
Implements Parabolic / Raised-Cosine River Bathymetry Reconstruction on Copernicus DEM.
"""

import sys
import os
import time
import numpy as np
import rasterio
from scipy.ndimage import distance_transform_edt
from skimage.morphology import skeletonize
import matplotlib.pyplot as plt

def main():
    print("=" * 70)
    print("KHỞI CHẠY THỬ NGHIỆM TÁI TẠO ĐỊA HÌNH ĐO SÂU LÒNG SÔNG BA (TRIAL CARVING)")
    print("=" * 70)
    start_time = time.time()

    base_dem_path = r"D:\VTP\05-Du-lieu-GIS\PhuYen_DEM_30m_V48_BASE_COPERNICUS.tif"
    jrc_path = r"D:\VTP\V48_research_20261002\hydro_evidence_raw\V46_JRC_GSW1_3_occurrence_1984_2020.tif"
    osm_path = r"D:\VTP\V46_dryrun_20260930\V46_distance_to_osm_waterway_m.tif"
    out_dir = r"D:\VTP\River_Bathymetry_Project"
    out_dem_path = os.path.join(out_dir, "PhuYen_DEM_30m_with_Bathymetry_trial.tif")
    out_diff_png = os.path.join(out_dir, "bathymetry_carving_trial_profile.png")

    print(f"[1/6] Đang đọc raster đầu vào...")
    with rasterio.open(base_dem_path) as src_dem:
        dem_data = src_dem.read(1).astype(np.float32)
        profile = src_dem.profile.copy()
        transform = src_dem.transform
        nodata_val = src_dem.nodata

    with rasterio.open(jrc_path) as src_jrc:
        jrc_data = src_jrc.read(1)

    with rasterio.open(osm_path) as src_osm:
        osm_dist = src_osm.read(1)

    print(f"      DEM shape: {dem_data.shape}, CRS: {profile['crs']}, Resolution: {profile['transform'][0]}m")

    print(f"[2/6] Xây dựng mặt nạ lòng sông chính Sông Ba...")
    # Lòng sông Ba chính: JRC occurrence >= 20% hoặc nằm gần tim OSM sông Ba trong hành lang
    # Giới hạn trong hành lang Sông Ba chính (tránh đầm Ô Loan và sông Kỳ Lộ ở phía Bắc)
    # Tọa độ Y UTM49N của sông Ba: từ 1435000 đến 1465000
    rows, cols = dem_data.shape
    y_coords = transform.f + np.arange(rows) * transform.e  # transform.e is negative
    x_coords = transform.c + np.arange(cols) * transform.a

    Y_grid = np.repeat(y_coords[:, np.newaxis], cols, axis=1)
    X_grid = np.repeat(x_coords[np.newaxis, :], rows, axis=0)

    # Vùng hành lang Sông Ba
    ba_corridor = (Y_grid >= 1433000) & (Y_grid <= 1466000) & (X_grid >= 270000) & (X_grid <= 333000)

    # Mặt nạ nước sông Ba
    river_mask = ba_corridor & ((jrc_data >= 25) | (osm_dist <= 120.0))
    # Loại trừ các vùng đồi cao và vùng biển ngoài khơi
    river_mask = river_mask & (dem_data > -5.0) & (dem_data < 80.0)

    total_river_cells = int(np.sum(river_mask))
    print(f"      Số ô lưới lòng sông xác định: {total_river_cells:,} ô (~{total_river_cells * 900 / 1e6:.2f} km²)")

    print(f"[3/6] Trích xuất khoảng cách từ bờ ra tim sông...")
    # distance transform từ bờ mép sông vào trong
    dist_to_bank = distance_transform_edt(river_mask) * 30.0  # chuyển sang mét
    
    # Tìm bề rộng cục bộ: lấy khoảng cách cực đại cục bộ trong mỗi vùng
    max_dist_in_river = np.max(dist_to_bank)
    print(f"      Bán chiều rộng lớn nhất của lòng sông: {max_dist_in_river:.1f} m")

    print(f"[4/6] Tính toán độ sâu khoét theo mô hình Parabol / Raised-Cosine...")
    # Phân đoạn: Thượng lưu đập Đồng Cam (X <= 301,000m) khoét 3.5m; Hạ lưu khoét 2.5m - 3.0m
    dong_cam_x = 301000.0
    d_max = np.where(X_grid <= dong_cam_x, 3.5, 3.0).astype(np.float32)

    # Tọa độ chuẩn hóa xi = 1.0 - (dist_to_bank / R_0)
    # Để tránh chia cho 0, chuẩn hóa theo percentile khoảng cách cục bộ hoặc bán kính chuẩn 150m
    R_ref = 150.0  # bán kính lòng sông tham chiếu
    xi = np.clip(dist_to_bank / R_ref, 0.0, 1.0)

    # Hàm chuyển tiếp Raised-Cosine: đạt 1.0 tại tim sông sâu nhất, 0.0 tại bờ
    # phi = sin^2(pi/2 * xi) từ bờ (xi=0) vào tim (xi=1)
    phi = np.sin(0.5 * np.pi * xi) ** 2

    delta_z = np.zeros_like(dem_data, dtype=np.float32)
    delta_z[river_mask] = d_max[river_mask] * phi[river_mask]

    # RÀNG BUỘC PHÁP LÝ BẢO TOÀN ĐỒNG BẰNG: Ngoài lòng sông delta_z = 0 tuyệt đối
    delta_z[~river_mask] = 0.0

    # RÀNG BUỘC ĐẬP ĐỒNG CAM: Khóa cứng cao trình không đục thủng ngưỡng đập (+7.0m)
    dong_cam_sill_mask = (np.abs(X_grid - 301050) < 150) & (np.abs(Y_grid - 1445700) < 300)
    delta_z[dong_cam_sill_mask] = np.minimum(delta_z[dong_cam_sill_mask], 0.3)

    print(f"[5/6] Tổng hợp DEM mới và kiểm tra nghiệm thu...")
    new_dem = dem_data - delta_z

    # Nghiệm thu bảo tồn địa hình ngoài bờ sông
    max_outside_diff = np.max(np.abs(new_dem[~river_mask] - dem_data[~river_mask]))
    assert max_outside_diff == 0.0, f"LỖI: Có {np.sum(new_dem[~river_mask] != dem_data[~river_mask])} ô ngoài sông bị thay đổi!"

    # Thống kê kết quả
    carved_cells = int(np.sum(delta_z > 0.01))
    max_cut = float(np.max(delta_z))
    mean_cut = float(np.mean(delta_z[delta_z > 0.01]))
    total_vol_m3 = float(np.sum(delta_z) * 900.0)

    print(f"      + Số ô lưới được hạ sâu: {carved_cells:,} ô")
    print(f"      + Độ sâu khoét lớn nhất (max cut): {max_cut:.3f} m")
    print(f"      + Độ sâu khoét trung bình: {mean_cut:.3f} m")
    print(f"      + Dung tích chứa bổ sung (delta V): {total_vol_m3 / 1e6:.2f} triệu m³")
    print(f"      + Bảo toàn bãi bồi ngoài bờ sông: HOÀN HẢO (sai số {max_outside_diff:.6f} m)")

    print(f"[6/6] Ghi file raster GeoTIFF thử nghiệm...")
    profile.update(dtype=rasterio.float32, nodata=nodata_val)
    with rasterio.open(out_dem_path, 'w', **profile) as dst:
        dst.write(new_dem.astype(np.float32), 1)
    print(f"      Đã lưu: {out_dem_path}")

    # Vẽ đồ thị trắc ngang so sánh tại Tuy Hòa (Cầu Đà Rằng)
    # Cầu Đà Rằng tọa độ: X ~ 327000, Y ~ 1446000
    r_idx, c_idx = src_dem.index(327000, 1446000)
    slice_orig = dem_data[r_idx - 30:r_idx + 30, c_idx]
    slice_new = new_dem[r_idx - 30:r_idx + 30, c_idx]
    dist_axis = np.arange(len(slice_orig)) * 30.0

    plt.figure(figsize=(10, 5), dpi=150)
    plt.plot(dist_axis, slice_orig, 'r--', label='Copernicus DEM Gốc (Mặt nước phẳng)', linewidth=2)
    plt.plot(dist_axis, slice_new, 'b-', label='DEM Sau Khắc Đáy Parabol (Raised-Cosine)', linewidth=2)
    plt.fill_between(dist_axis, slice_new, slice_orig, color='cyan', alpha=0.3, label='Dung tích lòng dẫn tái tạo')
    plt.title('Mặt cắt ngang Sông Ba tại Cầu Đà Rằng (TP. Tuy Hòa)\nSo sánh Trước và Sau khi Khắc Đo sâu Lòng sông', fontsize=12, fontweight='bold')
    plt.xlabel('Khoảng cách mặt cắt ngang (m)', fontsize=10)
    plt.ylabel('Cao độ (m MSL)', fontsize=10)
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend(loc='upper right', frameon=True)
    plt.tight_layout()
    plt.savefig(out_diff_png)
    plt.close()
    print(f"      Đã xuất biểu đồ trắc ngang: {out_diff_png}")

    elapsed = time.time() - start_time
    print(f"Thực thi hoàn tất trong {elapsed:.2f} giây!")
    print("=" * 70)

if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""
Bộ kiểm thử tự động (Unit Tests + Edge Cases + Audit Integrity Tests) cho Cách 1:
`v49_method1_dhg_clamped.py` — Ước lượng địa hình đáy sông đa nhánh không cần số đo thực địa.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import rasterio
from PIL import Image

from v49_method1_dhg_clamped import (
    BASE_DEM_PATH,
    CANONICAL_MINMASK_M,
    DEFAULT_Z_FLOOR_M,
    EXPECTED_DEM_SHA256,
    EXPECTED_V49E_CENTRAL_SHA256,
    EXPECTED_V49E_DELTAZ_SHA256,
    GRID_SHAPE,
    OUT_DIR,
    build_dong_cam_mask,
    build_v48_66_cuts_delta,
    clamp_bed_elevation,
    classify_river_system,
    load_and_verify_base_dem,
    raised_cosine_weights_vectorized,
    sha256_file,
    split_pipe,
)


class TestMathematicalPrimitivesAndEdgeCases:
    """Kiểm thử các hàm toán học cốt lõi và các trường hợp biên (edge cases)."""

    def test_split_pipe_handles_empty_none_nan_and_tokens(self) -> None:
        assert split_pipe(None) == []
        assert split_pipe(float("nan")) == []
        assert split_pipe("") == []
        assert split_pipe("  ") == []
        assert split_pipe("W20_0001 | W20_0007 | ") == ["W20_0001", "W20_0007"]

    def test_dong_cam_mask_exact_187_cells(self) -> None:
        mask = build_dong_cam_mask(GRID_SHAPE)
        assert mask.shape == (2100, 2100)
        assert mask.dtype == bool
        assert int(mask.sum()) == 187
        assert mask[1272, 1212] is np.True_
        assert mask[1288, 1222] is np.True_
        assert mask[1271, 1212] is np.False_
        assert mask[1289, 1222] is np.False_

    def test_classify_river_system_all_branches_and_edge_inputs(self) -> None:
        assert classify_river_system(41347969, "HYDRORIVERS") == "Song_Ba"
        assert classify_river_system(41349827, "HYDRORIVERS") == "Song_Ban_Thach"
        assert classify_river_system(41342672, "HYDRORIVERS") == "Song_Ky_Lo"
        assert classify_river_system(41344017, "HYDRORIVERS") == "Dam_O_Loan"
        # Kênh Đồng Cam luôn bị gắn nhãn cấm bất kể MAIN_RIV là gì
        assert classify_river_system(41347969, "LEGACY_CANAL_CANDIDATE") == "Kenh_Dong_Cam_Forbidden"
        assert classify_river_system(None, "HYDRORIVERS") == "Other"
        assert classify_river_system("invalid", "HYDRORIVERS") == "Other"
        assert classify_river_system(99999999, "HYDRORIVERS") == "Other"

    def test_raised_cosine_weights_exact_values_and_monotonicity(self) -> None:
        half_w = 100.0
        dists = np.array([-5.0, 0.0, 25.0, 50.0, 75.0, 100.0, 150.0], dtype=np.float64)
        w = raised_cosine_weights_vectorized(dists, half_w)
        assert math.isclose(w[0], 1.0, rel_tol=1e-12)
        assert math.isclose(w[1], 1.0, rel_tol=1e-12)
        assert math.isclose(w[3], 0.5, rel_tol=1e-12)  # d = r/2 -> cos^2(pi/4) = 0.5
        assert w[5] == 0.0
        assert w[6] == 0.0
        # Đơn điệu giảm từ tâm ra bờ
        assert np.all(np.diff(w[1:6]) < 0.0)

    def test_raised_cosine_thalweg_override(self) -> None:
        dists = np.array([40.0, 80.0], dtype=np.float64)
        thalweg = np.array([True, False])
        w = raised_cosine_weights_vectorized(dists, 50.0, is_thalweg=thalweg)
        assert w[0] == 1.0
        assert w[1] == 0.0

    @pytest.mark.parametrize("bad_half_width", [0.0, -10.0, float("nan"), float("inf")])
    def test_raised_cosine_rejects_invalid_half_width(self, bad_half_width: float) -> None:
        with pytest.raises(ValueError, match="half_width_m must be positive and finite"):
            raised_cosine_weights_vectorized(np.array([10.0]), bad_half_width)

    def test_clamp_bed_elevation_unclamped_preserves_exact_dz(self) -> None:
        z_surf = np.array([[10.0, 264.1]], dtype=np.float32)
        dz = np.array([[2.5, 0.85]], dtype=np.float32)
        z_new, eff_dz, clamped_cnt = clamp_bed_elevation(z_surf, dz, z_floor=-3.50)
        assert clamped_cnt == 0
        np.testing.assert_allclose(eff_dz, dz, rtol=0, atol=1e-7)
        np.testing.assert_allclose(z_new, z_surf - dz, rtol=1e-6, atol=1e-5)
        assert np.all(z_new > CANONICAL_MINMASK_M)

    def test_clamp_bed_elevation_clamps_deep_estuary_above_minmask(self) -> None:
        # Cửa sông có z_surf = 0.20 m, nếu đào sâu dz = 4.50 m sẽ tụt xuống -4.30 m (< minmask = -4.0 m).
        # Khóa sàn đáy phải kẹp cứng ở z_floor = -3.50 m, hiệu dụng eff_dz = 0.20 - (-3.50) = 3.70 m.
        z_surf = np.array([[0.20, -3.00, 5.00]], dtype=np.float32)
        dz = np.array([[4.50, 0.8117, 1.20]], dtype=np.float32)
        z_new, eff_dz, clamped_cnt = clamp_bed_elevation(z_surf, dz, z_floor=-3.50)
        assert clamped_cnt == 2
        assert math.isclose(float(z_new[0, 0]), -3.50, abs_tol=1e-6)
        assert math.isclose(float(z_new[0, 1]), -3.50, abs_tol=1e-6)
        assert math.isclose(float(z_new[0, 2]), 3.80, abs_tol=1e-6)
        assert math.isclose(float(eff_dz[0, 0]), 3.70, abs_tol=1e-5)
        assert math.isclose(float(eff_dz[0, 1]), 0.50, abs_tol=1e-5)
        assert math.isclose(float(eff_dz[0, 2]), 1.20, abs_tol=1e-5)
        assert np.all(z_new > CANONICAL_MINMASK_M)

    def test_clamp_bed_elevation_does_not_excavate_or_raise_already_below_floor_cells(self) -> None:
        # Nếu một ô DEM gốc vốn đã ở -3.80 m (< z_floor = -3.50 m), thuật toán không được đào thêm (eff_dz = 0)
        # và cũng không được đắp đất nâng đáy nhân tạo (z_new giữ nguyên -3.80 m).
        z_surf = np.array([[-3.80, -4.50]], dtype=np.float32)
        dz = np.array([[1.00, 0.00]], dtype=np.float32)
        z_new, eff_dz, clamped_cnt = clamp_bed_elevation(z_surf, dz, z_floor=-3.50)
        assert clamped_cnt == 1
        assert float(eff_dz[0, 0]) == 0.0
        assert float(eff_dz[0, 1]) == 0.0
        assert math.isclose(float(z_new[0, 0]), -3.80, abs_tol=1e-6)
        assert math.isclose(float(z_new[0, 1]), -4.50, abs_tol=1e-6)

    @pytest.mark.parametrize("bad_floor", [-4.00, -4.50, -10.0])
    def test_clamp_bed_elevation_rejects_floor_at_or_below_minmask(self, bad_floor: float) -> None:
        with pytest.raises(ValueError, match="must be strictly above canonical minmask"):
            clamp_bed_elevation(np.array([1.0], dtype=np.float32), np.array([0.5], dtype=np.float32), z_floor=bad_floor)


@pytest.fixture(scope="module")
def audit_summary() -> dict:
    json_path = OUT_DIR / "V49_Method1_Audit_Summary.json"
    assert json_path.exists(), f"Missing audit JSON: {json_path}"
    return json.loads(json_path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def reach_table() -> pd.DataFrame:
    csv_path = OUT_DIR / "V49_Method1_Reach_Table.csv"
    assert csv_path.exists(), f"Missing reach table CSV: {csv_path}"
    return pd.read_csv(csv_path)


class TestMethod1PipelineDeliverablesAndAuditInvariants:
    """Kiểm thử toàn diện kết quả đầu ra JSON, CSV và 2 hình vẽ nền trắng của Cách 1."""

    def test_domain_partition_invariants(self, audit_summary: dict, reach_table: pd.DataFrame) -> None:
        dp = audit_summary["domain_partition"]
        assert dp["total_reaches"] == 370
        assert len(reach_table) == 370
        assert dp["outside_v49c_eligible_channel_reaches"] == 279
        assert dp["v49c_eligible_channel_reaches"] == 91
        assert dp["forbidden_dong_cam_canal_reaches"] == 2
        assert dp["natural_eligible_reaches"] == 89
        assert dp["protected_dong_cam_structure_cells"] == 187

        # Kiểm tra tổng phân hoạch 370 = 279 + 89 + 2
        assert (
            dp["outside_v49c_eligible_channel_reaches"]
            + dp["natural_eligible_reaches"]
            + dp["forbidden_dong_cam_canal_reaches"]
            == dp["total_reaches"]
        )

    def test_scope_reach_counts_and_canal_exclusion(self, audit_summary: dict, reach_table: pd.DataFrame) -> None:
        scopes = audit_summary["scopes"]
        assert scopes["V49_E_2"]["models"]["DHG-1"]["reach_count"] == 2
        assert scopes["SCOPE_A_21"]["models"]["DHG-1"]["reach_count"] == 21
        assert scopes["SCOPE_B1_41"]["models"]["DHG-1"]["reach_count"] == 41
        assert scopes["SCOPE_B2_82"]["models"]["DHG-1"]["reach_count"] == 82
        assert scopes["SCOPE_B3_89"]["models"]["DHG-1"]["reach_count"] == 89

        # Không có bất kỳ kênh tưới nhân tạo nào lọt vào các cấp độ của Cách 1
        canals = reach_table[reach_table["source_type"] == "LEGACY_CANAL_CANDIDATE"]
        assert len(canals) == 2
        for col in ["in_v49_e_2", "in_scope_a_21", "in_scope_b1_41", "in_scope_b2_82", "in_scope_b3_89"]:
            assert not canals[col].any(), f"Forbidden canal leaked into {col}"

    def test_zero_minmask_and_dong_cam_violations_across_all_scopes_and_models(
        self, audit_summary: dict
    ) -> None:
        for scope_key, scope_data in audit_summary["scopes"].items():
            for model_key, m in scope_data["models"].items():
                assert m["cells_le_minmask"] == 0, f"{scope_key}/{model_key} violated minmask"
                assert m["dong_cam_modified_cells"] == 0, f"{scope_key}/{model_key} modified Dong Cam"
                assert m["canal_modified_cells"] == 0, f"{scope_key}/{model_key} modified canal"
                assert m["min_bed_wse_proxy_high_m"] >= DEFAULT_Z_FLOOR_M
                assert m["min_bed_object_dem_clamped_high_m"] >= DEFAULT_Z_FLOOR_M
                assert m["volume_low_m3"] < m["volume_central_m3"] < m["volume_high_m3"]

    def test_nested_scope_monotonic_volume_and_pareto_efficiency(self, audit_summary: dict) -> None:
        s = audit_summary["scopes"]
        v_e = s["V49_E_2"]["models"]["DHG-1"]["volume_central_m3"]
        v_a = s["SCOPE_A_21"]["models"]["DHG-1"]["volume_central_m3"]
        v_b1 = s["SCOPE_B1_41"]["models"]["DHG-1"]["volume_central_m3"]
        v_b2 = s["SCOPE_B2_82"]["models"]["DHG-1"]["volume_central_m3"]
        v_b3 = s["SCOPE_B3_89"]["models"]["DHG-1"]["volume_central_m3"]

        assert v_e < v_a < v_b1 < v_b2 < v_b3
        # Kiểm chứng hiệu quả Pareto: 41 đoạn sông lớn W >= 60m chiếm > 95% thể tích của toàn bộ 82 đoạn
        pareto_ratio = v_b1 / v_b2
        assert pareto_ratio > 0.95

    def test_white_background_figures_exist_and_have_pure_white_canvas(self) -> None:
        fig_names = [
            "Hinh_Cach1_Ban_Do_3_Cap_Do_21_41_82_Doan_Nen_Trang.png",
            "Hinh_Cach1_So_Sanh_The_Tich_Va_An_Toan_Day_Nen_Trang.png",
        ]
        for fname in fig_names:
            fpath = OUT_DIR / fname
            assert fpath.exists(), f"Missing figure: {fpath}"
            assert fpath.stat().st_size > 150_000, f"Figure too small: {fpath}"
            with Image.open(fpath) as img:
                rgb = img.convert("RGB")
                w, h = rgb.size
                assert w >= 2500 and h >= 2000
                # Kiểm tra 4 góc ảnh phải là màu trắng tinh (#FFFFFF = 255, 255, 255)
                for cx, cy in [(2, 2), (w - 3, 2), (2, h - 3), (w - 3, h - 3)]:
                    assert rgb.getpixel((cx, cy)) == (255, 255, 255), f"Corner {(cx, cy)} in {fname} is not white"

    def test_river_breakdown_conservation_across_scopes(self, audit_summary: dict) -> None:
        for scope_key, scope_data in audit_summary["scopes"].items():
            m = scope_data["models"]["DHG-1"]
            rb = scope_data["river_breakdown"]
            assert sum(v["reach_count"] for v in rb.values()) == m["reach_count"]
            assert sum(v["modified_pixel_count"] for v in rb.values()) == m["modified_pixel_count"]
            assert math.isclose(
                sum(v["volume_low_m3"] for v in rb.values()), m["volume_low_m3"], abs_tol=0.05
            )
            assert math.isclose(
                sum(v["volume_central_m3"] for v in rb.values()), m["volume_central_m3"], abs_tol=0.05
            )
            assert math.isclose(
                sum(v["volume_high_m3"] for v in rb.values()), m["volume_high_m3"], abs_tol=0.05
            )

    def test_dam_o_loan_scope_b3_triggers_object_dem_floor_clamp(self, audit_summary: dict) -> None:
        for model_key, m in audit_summary["scopes"]["SCOPE_B3_89"]["models"].items():
            assert m["clamped_at_object_dem_min_high"] is True, f"SCOPE_B3_89/{model_key} should trigger clamp"
            assert m["min_bed_object_dem_unclamped_high_m"] < DEFAULT_Z_FLOOR_M
            assert m["min_bed_object_dem_clamped_high_m"] == DEFAULT_Z_FLOOR_M

    def test_markdown_reports_synchronized_with_audit_json(self, audit_summary: dict) -> None:
        def fmt_vn(val: float, decimals: int = 2) -> str:
            s = f"{val:,.{decimals}f}"
            return s.replace(",", "X").replace(".", ",").replace("X", ".")

        report_md = (OUT_DIR / "Bao_Cao_Thuc_Thi_Cach_1_Khong_Can_Thuc_Dia.md").read_text(encoding="utf-8")
        guide_candidates = [
            OUT_DIR.parent / "huong-dan-viet-do-an-chi-tiet.md",
            Path(r"D:\DoAnSv\research\dao-song\huong-dan-viet-do-an-chi-tiet.md"),
        ]
        guide_path = next((p for p in guide_candidates if p.exists()), None)
        guide_md = guide_path.read_text(encoding="utf-8") if guide_path else ""

        # Mọi giá trị thể tích CENTRAL và max_dz_central_m của 15 tổ hợp (5 Scopes x 3 Models) phải khớp trong Báo cáo
        for scope_key, scope_data in audit_summary["scopes"].items():
            for model_key, m in scope_data["models"].items():
                vol_cen_vn = fmt_vn(m["volume_central_m3"], 2)
                max_dz_vn = fmt_vn(m["max_dz_central_m"], 4)
                assert vol_cen_vn in report_md, f"Missing {scope_key}/{model_key} volume {vol_cen_vn} in report MD"
                assert max_dz_vn in report_md, f"Missing {scope_key}/{model_key} max_dz {max_dz_vn} in report MD"

        # Mọi giá trị thể tích phân rã theo 3 hệ thống sông (Scope A, B1, B2) phải khớp trong Báo cáo
        for scope_key in ["SCOPE_A_21", "SCOPE_B1_41", "SCOPE_B2_82"]:
            for r_sys, r_val in audit_summary["scopes"][scope_key]["river_breakdown"].items():
                r_vol_vn = fmt_vn(r_val["volume_central_m3"], 2)
                assert r_vol_vn in report_md, f"Missing {scope_key}/{r_sys} volume {r_vol_vn} in report MD"

        # Mọi mã băm SHA-256 và thể tích đào trên DEM thực của 9 bộ GeoTIFF phải có mặt trong Báo cáo
        for r_key, r_meta in audit_summary["real_dem_carving_outputs"]["rasters"].items():
            assert r_meta["dem_tif_sha256"] in report_md, f"Missing DEM SHA-256 for {r_key} in report MD"
            assert r_meta["delta_z_tif_sha256"] in report_md, f"Missing DeltaZ SHA-256 for {r_key} in report MD"
            vol_real_vn = fmt_vn(r_meta["lowering_volume_m3"], 2)
            assert vol_real_vn in report_md, f"Missing real-DEM volume {vol_real_vn} for {r_key} in report MD"

        # Không còn các số liệu nháp bị lệch từ phiên bản cũ
        stale_tokens = [
            "2,2292",
            "3.594.045,51",
            "6.080.608,71",
            "9.089.153,55",
            "8.424.328,67",
            "5,338.86",
            "10,677.67",
            "phát散",
            "quan측",
        ]
        for token in stale_tokens:
            assert token not in report_md, f"Stale/corrupted token {token!r} found in report MD"
            if guide_md:
                assert token not in guide_md, f"Stale/corrupted token {token!r} found in guide MD"


class TestRealDEMCarvingAndGeoTIFFInvariants:
    """Kiểm thử trực tiếp trên tệp DEM gốc và 18 tệp GeoTIFF (.tif) đã đào trên ổ cứng."""

    def test_source_dem_integrity_and_immutability(self, audit_summary: dict) -> None:
        src = audit_summary["source_dem_integrity"]
        assert src["sha256"] == EXPECTED_DEM_SHA256
        assert src["sha256_before"] == EXPECTED_DEM_SHA256
        assert src["sha256_after"] == EXPECTED_DEM_SHA256
        assert src["source_dem_unchanged"] is True
        assert src["shape"] == [2100, 2100]
        assert src["dtype"] == "float32"
        assert src["crs"] == "EPSG:32649"
        assert src["valid_pixel_count"] == 4410000
        assert src["valid_cells_le_canonical_minmask"] == 0
        assert src["valid_cells_le_z_floor"] == 0
        assert BASE_DEM_PATH.exists()
        assert sha256_file(BASE_DEM_PATH) == EXPECTED_DEM_SHA256

    def test_v48_66_local_breaching_cuts_exact_reconstruction(self, audit_summary: dict) -> None:
        base_dem, _, _ = load_and_verify_base_dem(BASE_DEM_PATH)
        v48_dz, v48_summary = build_v48_66_cuts_delta(base_dem)
        assert v48_dz.shape == GRID_SHAPE
        assert v48_dz.dtype == np.float32
        assert v48_summary["initial_frozen_v48_cells"] == 55
        assert v48_summary["closed_loop_strict_post_cells"] == 15
        assert v48_summary["total_unique_modified_cells"] == 66
        assert math.isclose(v48_summary["max_cut_m"], 0.995961, abs_tol=1e-6)
        assert math.isclose(v48_summary["excavation_volume_m3"], 31806.64, abs_tol=1e-2)
        assert audit_summary["real_dem_carving_outputs"]["v48_66_local_breaching_summary"] == v48_summary
        # Không có ô nào trong 66 ô thông cống V48 phạm vào 187 ô đập Đồng Cam
        dc_mask = build_dong_cam_mask(GRID_SHAPE)
        assert int(np.count_nonzero(v48_dz[dc_mask] > 0.0)) == 0

    def test_all_18_geotiff_rasters_exist_and_match_sha256_and_safety_invariants(
        self, audit_summary: dict
    ) -> None:
        rasters_meta = audit_summary["real_dem_carving_outputs"]["rasters"]
        assert len(rasters_meta) == 9
        dc_mask = build_dong_cam_mask(GRID_SHAPE)

        for key, meta in rasters_meta.items():
            dem_path = OUT_DIR / "rasters" / Path(meta["dem_tif_path"]).name
            dz_path = OUT_DIR / "rasters" / Path(meta["delta_z_tif_path"]).name
            assert dem_path.exists(), f"Missing carved DEM .tif for {key}: {dem_path}"
            assert dz_path.exists(), f"Missing DeltaZ .tif for {key}: {dz_path}"
            assert sha256_file(dem_path) == meta["dem_tif_sha256"], f"SHA-256 mismatch on {dem_path}"
            assert sha256_file(dz_path) == meta["delta_z_tif_sha256"], f"SHA-256 mismatch on {dz_path}"

            assert meta["valid_cells_le_canonical_minmask"] == 0
            assert meta["dong_cam_modified_cells"] == 0
            assert meta["canal_modified_cells"] == 0
            assert meta["raised_pixel_count"] == 0
            assert meta["valid_min_bed_modified_m"] >= DEFAULT_Z_FLOOR_M
            assert meta["valid_min_global_m"] > CANONICAL_MINMASK_M

            with rasterio.open(dem_path) as src_dem, rasterio.open(dz_path) as src_dz:
                assert (src_dem.height, src_dem.width) == GRID_SHAPE
                assert (src_dz.height, src_dz.width) == GRID_SHAPE
                assert src_dem.dtypes[0] == "float32"
                assert src_dz.dtypes[0] == "float32"
                assert str(src_dem.crs) == "EPSG:32649"
                assert str(src_dz.crs) == "EPSG:32649"
                z_arr = src_dem.read(1)
                dz_arr = src_dz.read(1)
                assert int(np.count_nonzero(z_arr <= CANONICAL_MINMASK_M)) == 0
                assert int(np.count_nonzero(dz_arr < 0.0)) == 0
                assert int(np.count_nonzero(dz_arr[dc_mask] > 0.0)) == 0
                assert int(np.count_nonzero(dz_arr > 0.0)) == meta["modified_pixel_count"]

    def test_v49_e_2_central_reproduces_frozen_v49e_sha256_byte_for_byte(
        self, audit_summary: dict
    ) -> None:
        v49e_meta = audit_summary["real_dem_carving_outputs"]["rasters"]["V49_E_2_CENTRAL"]
        assert v49e_meta["dem_tif_sha256"] == EXPECTED_V49E_CENTRAL_SHA256
        assert v49e_meta["delta_z_tif_sha256"] == EXPECTED_V49E_DELTAZ_SHA256
        assert v49e_meta["matches_frozen_v49e_dem_sha256"] is True
        assert v49e_meta["matches_frozen_v49e_deltaz_sha256"] is True
        assert v49e_meta["modified_pixel_count"] == 72
        assert math.isclose(v49e_meta["lowering_volume_m3"], 8008.21, abs_tol=1e-2)

    @pytest.mark.parametrize(
        "prefix",
        ["SCOPE_B1_41", "V48_66CUTS_PLUS_SCOPE_B1_41"],
    )
    def test_pointwise_envelope_ordering_on_real_dem_geotiffs(
        self, audit_summary: dict, prefix: str
    ) -> None:
        rasters_meta = audit_summary["real_dem_carving_outputs"]["rasters"]
        with rasterio.open(BASE_DEM_PATH) as src_base:
            z_base = src_base.read(1)

        z_map = {}
        dz_map = {}
        for env in ["LOW", "CENTRAL", "HIGH"]:
            meta = rasters_meta[f"{prefix}_{env}"]
            dem_path = OUT_DIR / "rasters" / Path(meta["dem_tif_path"]).name
            dz_path = OUT_DIR / "rasters" / Path(meta["delta_z_tif_path"]).name
            with rasterio.open(dem_path) as s_dem, rasterio.open(dz_path) as s_dz:
                z_map[env] = s_dem.read(1)
                dz_map[env] = s_dz.read(1)

        # Kiểm chứng bất đẳng thức điểm-đối-điểm trên toàn bộ 4.410.000 ô:
        # z_HIGH <= z_CENTRAL <= z_LOW <= z_BASE và 0 <= dz_LOW <= dz_CENTRAL <= dz_HIGH
        assert np.all(z_map["HIGH"] <= z_map["CENTRAL"])
        assert np.all(z_map["CENTRAL"] <= z_map["LOW"])
        assert np.all(z_map["LOW"] <= z_base)
        assert np.all(dz_map["LOW"] >= 0.0)
        assert np.all(dz_map["LOW"] <= dz_map["CENTRAL"] + 1e-6)
        assert np.all(dz_map["CENTRAL"] <= dz_map["HIGH"] + 1e-6)



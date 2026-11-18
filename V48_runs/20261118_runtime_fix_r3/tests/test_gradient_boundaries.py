"""Boundary reconstruction regressions for the isolated R3 vectorized runtime."""
from pathlib import Path
from types import SimpleNamespace
import sys

import numpy as np
import pytest

sys.modules["cupy"] = None
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
from bg_flood.flow_gpu import fill_gradient_halo_vec  # noqa: E402
from bg_flood.forcing import Forcing  # noqa: E402
from bg_flood.model import GradientsP  # noqa: E402


def fixture():
    idx = SimpleNamespace()
    for side in ("left", "right", "bot", "top"):
        for suffix in ("dst", "src"):
            setattr(idx, f"flux_halo_{side}_{suffix}", np.array([], dtype=int))
        setattr(idx, f"bnd_{side}_i", np.array([], dtype=int))
        setattr(idx, f"bnd_{side}_inside", np.array([], dtype=int))
    grad = GradientsP()
    grad.allocate(4)
    for field in ("h", "zs", "u", "v"):
        for axis in ("x", "y"):
            getattr(grad, f"d{field}d{axis}")[:] = [7., 0., 0., 0.]
    return idx, grad, Forcing()


@pytest.mark.parametrize("side,normal", (("left", "x"), ("right", "x"), ("bot", "y"), ("top", "y")))
def test_wall_parity_reconstructs_scalar_even_and_normal_velocity_odd(side, normal):
    idx, grad, forcing = fixture()
    setattr(idx, f"bnd_{side}_i", np.array([1]))
    setattr(idx, f"bnd_{side}_inside", np.array([0]))
    getattr(forcing, side).type = 0
    fill_gradient_halo_vec(idx, forcing, grad)
    for field in ("h", "zs", "u", "v"):
        for axis in ("x", "y"):
            # Với bước nửa ô1, giá trị odd/even ở tâm và đạo hàm đã biết
            # phải cho giá trị tái dựng trái/phải phản xạ đúng ở mặt tường.
            parity = -1 if field == ("u" if normal == "x" else "v") else 1
            derivative = getattr(grad, f"d{field}d{axis}")
            if axis == normal:
                interior_face = 20. - derivative[0]
                ghost_face = parity * 20. + derivative[1]
                assert ghost_face == parity * interior_face
            else:
                assert derivative[1] == parity * derivative[0]


def test_free_outflow_has_zero_normal_derivatives():
    idx, grad, forcing = fixture()
    idx.bnd_right_i, idx.bnd_right_inside = np.array([1]), np.array([0])
    forcing.right.type = 2
    fill_gradient_halo_vec(idx, forcing, grad)
    for field in ("h", "zs", "u", "v"):
        assert getattr(grad, f"d{field}dx")[1] == 0.
        assert getattr(grad, f"d{field}dy")[1] == 7.


def test_unsupported_fixed_level_boundary_fails_before_modifying_gradients():
    idx, grad, forcing = fixture()
    idx.bnd_left_i, idx.bnd_left_inside = np.array([1]), np.array([0])
    forcing.left.type = 1
    with pytest.raises(NotImplementedError, match="wall=0/outflow=2"):
        fill_gradient_halo_vec(idx, forcing, grad)
    assert grad.dhdx[1] == 0.


def test_internal_exchange_reads_neighbor_gradient():
    idx, grad, forcing = fixture()
    idx.flux_halo_right_dst, idx.flux_halo_right_src = np.array([1]), np.array([0])
    fill_gradient_halo_vec(idx, forcing, grad)
    for field in ("h", "zs", "u", "v"):
        for axis in ("x", "y"):
            assert getattr(grad, f"d{field}d{axis}")[1] == 7.

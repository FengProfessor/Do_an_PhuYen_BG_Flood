import numpy as np
import pytest

from v49_audit_2021_water_history import annual_counts, monthly_counts


def test_cloud_obscured_month_does_not_become_dry_or_zero_water_fraction():
    result = monthly_counts(np.array([0, 0, 0], dtype=np.uint8))
    assert result["observed_cells"] == 0
    assert result["dry_observed_cells"] == 0
    assert result["water_fraction_of_observed"] is None
    result = monthly_counts(np.array([0, 1, 2], dtype=np.uint8))
    assert result["observation_fraction"] == pytest.approx(2/3)
    assert result["water_fraction_of_observed"] == .5


def test_one_wet_month_and_eleven_unobserved_is_not_permanent():
    values = np.zeros((12, 3), dtype=np.uint8)
    values[0, 0] = 2
    values[:, 1] = 2
    values[:, 2] = 1
    values[10, 2] = 2
    counts = annual_counts(values)
    assert counts["observed_water_all_12_months_cells"] == 1
    assert counts["observed_all_12_months_cells"] == 2
    assert counts["both_water_and_dry_observed_cells"] == 1
    assert counts["authorizes_bathymetry"] is False


def test_wrong_codes_or_missing_months_are_rejected():
    with pytest.raises(ValueError):
        monthly_counts(np.array([255], dtype=np.uint8))
    with pytest.raises(ValueError):
        annual_counts(np.ones((11, 3), dtype=np.uint8))

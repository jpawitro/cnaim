"""Tests for risk profile composition from PoF and CoF outputs."""

from __future__ import annotations

import pytest

from cnaim.consequences import ConsequenceBreakdown
from cnaim.pof import PoFResult
from cnaim.risk_profile import RiskProfile


def test_risk_profile_maps_matrix_coordinates() -> None:
    """Verify matrix coordinates and monetary risk are derived correctly."""
    pof_result = PoFResult(pof=0.08, chs=5.5)
    consequence = ConsequenceBreakdown(
        financial=10000,
        safety=9000,
        environmental=7000,
        network_performance=18542,
        reference_total_cost=20034,
    )

    profile = RiskProfile.from_results(
        asset_id="RISK-1", pof_result=pof_result, consequence=consequence
    )

    assert profile.risk_matrix_x == pytest.approx(50.0)
    assert profile.risk_matrix_y == pytest.approx(75.0)
    assert profile.monetary_risk == pytest.approx(pof_result.pof * consequence.total)


def test_risk_profile_derives_table_weight_outputs() -> None:
    """Verify in-year and long-term risk matrix values from tables 236-241."""
    pof_result = PoFResult(pof=0.08, chs=5.5)
    consequence = ConsequenceBreakdown(
        financial=10000,
        safety=9000,
        environmental=7000,
        network_performance=18542,
        reference_total_cost=20034,
    )

    profile = RiskProfile.from_results(
        asset_id="RISK-2",
        pof_result=pof_result,
        consequence=consequence,
        asset_category="LV UGB",
        compute_table_weights=True,
    )

    assert profile.in_year_hi_band == "HI3"
    assert profile.in_year_ci_band == "C4"
    assert profile.typical_cof_weight == pytest.approx(39708.86)
    assert profile.typical_in_year_pof_weight == pytest.approx(0.005777)
    assert profile.in_year_monetised_risk == pytest.approx(229)

    assert profile.long_term_hi_band == "HI3"
    assert profile.long_term_ci_band == "C4"
    assert profile.forecast_ageing_rate == pytest.approx(0.0435981)
    assert profile.long_term_cumulative_pof_weight == pytest.approx(0.3617)
    assert profile.long_term_risk_index == pytest.approx(14363)


def test_risk_profile_requires_category_for_table_weights() -> None:
    """Table weighting mode must provide an explicit asset category."""
    pof_result = PoFResult(pof=0.06, chs=4.0)
    consequence = ConsequenceBreakdown(
        financial=3000,
        safety=2000,
        environmental=1000,
        network_performance=500,
        reference_total_cost=20034,
    )

    with pytest.raises(ValueError, match="asset_category is required"):
        RiskProfile.from_results(
            asset_id="RISK-3",
            pof_result=pof_result,
            consequence=consequence,
            compute_table_weights=True,
        )


def test_risk_profile_canonical_category_lookup() -> None:
    """Category lookup should tolerate formatting differences via canonical matching."""
    pof_result = PoFResult(pof=0.06, chs=5.9)
    consequence = ConsequenceBreakdown(
        financial=3000,
        safety=2000,
        environmental=1000,
        network_performance=500,
        reference_total_cost=20034,
    )

    profile = RiskProfile.from_results(
        asset_id="RISK-4",
        pof_result=pof_result,
        consequence=consequence,
        asset_category="33kV CB (Air Insulated Busbars)(ID) (GM)",
        compute_table_weights=True,
    )

    assert profile.in_year_monetised_risk is not None
    assert profile.long_term_risk_index is not None

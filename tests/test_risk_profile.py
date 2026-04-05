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

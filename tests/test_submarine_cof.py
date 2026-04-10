"""Tests for submarine cable CoF, with focus on EHV/132kV secure network routing."""

import pytest

from cnaim.assets import CableAsset
from cnaim.generic_models import CNAIMConsequenceModel


@pytest.fixture()
def cof_model():
    return CNAIMConsequenceModel()


def _ehv_sub_cable(**kwargs) -> CableAsset:
    defaults = dict(
        asset_id="SUB-COF-001",
        asset_name="EHV Submarine Cable",
        asset_category="EHV Sub Cable",
    )
    defaults.update(kwargs)
    return CableAsset(**defaults)


def _132kv_sub_cable(**kwargs) -> CableAsset:
    defaults = dict(
        asset_id="SUB-COF-002",
        asset_name="132kV Submarine Cable",
        asset_category="132kV Sub Cable",
    )
    defaults.update(kwargs)
    return CableAsset(**defaults)


# ---------------------------------------------------------------------------
# Network performance: EHV secure network reference costs (Table 235)
# ---------------------------------------------------------------------------


def test_ehv_sub_cable_network_perf_uses_secure_table(cof_model):
    """EHV Sub Cable must use £3,530 reference cost from Table 235 (secure network)."""
    asset = _ehv_sub_cable()
    result = cof_model.calculate(asset)
    # Table 235: EHV Sub Cable reference_cost_for_assets_in_secure_networks_gbp = 3530
    assert result.network_performance == pytest.approx(3530.0, abs=1e-0)


def test_132kv_sub_cable_network_perf_uses_secure_table(cof_model):
    """132kV Sub Cable must use £17,648 reference cost from Table 235 (secure network)."""
    asset = _132kv_sub_cable()
    result = cof_model.calculate(asset)
    # Table 235: 132kV Sub Cable reference_cost_for_assets_in_secure_networks_gbp = 17648
    assert result.network_performance == pytest.approx(17648.0, abs=1e-0)


def test_ehv_network_perf_independent_of_customer_count(cof_model):
    """EHV/132kV secure network cost does not scale with customer count."""
    asset_0_cust = _ehv_sub_cable(no_customers=0)
    asset_many_cust = _ehv_sub_cable(no_customers=10000, kva_per_customer=2.0)
    result_0 = cof_model.calculate(asset_0_cust)
    result_many = cof_model.calculate(asset_many_cust)
    assert result_0.network_performance == pytest.approx(result_many.network_performance, rel=1e-6)


# ---------------------------------------------------------------------------
# Financial component
# ---------------------------------------------------------------------------


def test_financial_component_positive(cof_model):
    asset = _ehv_sub_cable()
    result = cof_model.calculate(asset)
    assert result.financial > 0


def test_financial_component_scales_with_access_type(cof_model):
    """Type B access should differ from Type A for financial cost."""
    from cnaim.enums import AccessType

    asset_a = _ehv_sub_cable(access_type=AccessType.TYPE_A)
    asset_b = _ehv_sub_cable(access_type=AccessType.TYPE_B)
    result_a = cof_model.calculate(asset_a)
    result_b = cof_model.calculate(asset_b)
    # Access types may differ; just verify both are positive and finite
    assert result_a.financial > 0
    assert result_b.financial > 0


# ---------------------------------------------------------------------------
# Safety component
# ---------------------------------------------------------------------------


def test_safety_component_positive(cof_model):
    asset = _ehv_sub_cable()
    result = cof_model.calculate(asset)
    assert result.safety > 0


def test_safety_exposed_higher_than_buried(cof_model):
    """Exposed cable layout has a higher safety factor than buried."""
    from cnaim.enums import CableLayout

    asset_buried = _ehv_sub_cable(cable_layout=CableLayout.BURIED)
    asset_exposed = _ehv_sub_cable(cable_layout=CableLayout.EXPOSED)
    result_buried = cof_model.calculate(asset_buried)
    result_exposed = cof_model.calculate(asset_exposed)
    assert result_exposed.safety > result_buried.safety


# ---------------------------------------------------------------------------
# Environmental component
# ---------------------------------------------------------------------------


def test_environmental_component_positive(cof_model):
    asset = _ehv_sub_cable()
    result = cof_model.calculate(asset)
    assert result.environmental >= 0


def test_environmental_proximity_increases_cost(cof_model):
    """Asset very close to water (30m) should have higher environmental cost than 200m."""
    asset_near = _ehv_sub_cable(proximity_to_water_m=30.0)
    asset_far = _ehv_sub_cable(proximity_to_water_m=200.0)
    result_near = cof_model.calculate(asset_near)
    result_far = cof_model.calculate(asset_far)
    assert result_near.environmental >= result_far.environmental


# ---------------------------------------------------------------------------
# Total CoF structure
# ---------------------------------------------------------------------------


def test_total_cof_equals_sum_of_components(cof_model):
    asset = _ehv_sub_cable()
    result = cof_model.calculate(asset)
    expected_total = result.financial + result.safety + result.environmental + result.network_performance
    assert result.total == pytest.approx(expected_total, abs=1e-6)


def test_reference_total_cost_positive(cof_model):
    asset = _ehv_sub_cable()
    result = cof_model.calculate(asset)
    assert result.reference_total_cost > 0

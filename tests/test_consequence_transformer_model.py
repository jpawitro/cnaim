"""Regression tests for transformer consequence component calculations."""

from __future__ import annotations

import pytest

from cnaim import Transformer11kVConsequenceModel, TransformerAsset
from cnaim.enums import AccessType


def test_transformer_consequence_components_reference_cases() -> None:
    """Validate non-zero consequence components for a representative transformer."""
    model = Transformer11kVConsequenceModel()
    asset = TransformerAsset(
        asset_id="TF-01",
        asset_name="Transformer 01",
        rated_capacity_kva=750,
        access_type=AccessType.TYPE_B,
        no_customers=750,
        kva_per_customer=51,
        bunded=True,
        proximity_to_water_m=100,
    )

    result = model.calculate(asset)

    assert result.financial > 0
    assert result.safety > 0
    assert result.environmental > 0
    assert result.network_performance > 0
    assert result.total == pytest.approx(
        result.financial + result.safety + result.environmental + result.network_performance
    )


def test_transformer_component_regression_values() -> None:
    """Lock expected transformer CoF component values for baseline inputs."""
    model = Transformer11kVConsequenceModel()

    financial_asset = TransformerAsset(
        asset_id="TF-02",
        asset_name="Transformer 02",
        rated_capacity_kva=700,
    )
    financial = model.calculate(financial_asset).financial
    assert financial == pytest.approx(9297.0, abs=0.2)

    safety_asset = TransformerAsset(
        asset_id="TF-03",
        asset_name="Transformer 03",
    )
    safety = model.calculate(safety_asset).safety
    assert safety == pytest.approx(4823.0, abs=0.2)

    environmental_asset = TransformerAsset(
        asset_id="TF-04",
        asset_name="Transformer 04",
        rated_capacity_kva=750,
        proximity_to_water_m=100,
        bunded=True,
    )
    environmental = model.calculate(environmental_asset).environmental
    assert environmental == pytest.approx(1904.5, abs=0.5)

    network_asset = TransformerAsset(
        asset_id="TF-05",
        asset_name="Transformer 05",
        no_customers=750,
        kva_per_customer=51,
    )
    network = model.calculate(network_asset).network_performance
    assert network == pytest.approx(407156.2, abs=2.0)

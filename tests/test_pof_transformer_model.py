"""Regression tests for the transformer PoF model."""

from __future__ import annotations

import pytest

from cnaim import Installation, Transformer11To20kVPoFModel, TransformerAsset
from cnaim.enums import Placement


def test_transformer_current_pof_default_case() -> None:
    """Check current PoF output for the baseline default transformer case."""
    model = Transformer11To20kVPoFModel()
    asset = TransformerAsset(asset_id="A1", asset_name="Transformer A1")
    installation = Installation(age_years=1)

    result = model.calculate_current(asset=asset, installation=installation)

    assert result.pof == pytest.approx(0.00013, abs=1e-5)
    assert result.chs == pytest.approx(0.5)


def test_transformer_future_pof_vector() -> None:
    """Validate length and year/age indexing of the future PoF vector."""
    model = Transformer11To20kVPoFModel()
    asset = TransformerAsset(asset_id="A2", asset_name="Transformer A2")
    installation = Installation(age_years=12)

    result = model.calculate_future(asset=asset, installation=installation, simulation_end_year=10)

    assert len(result.future_points) == 11
    assert result.future_points[0].year == 0
    assert result.future_points[-1].year == 10
    assert result.future_points[-1].age == pytest.approx(22)


def test_transformer_explicit_location_factor_override() -> None:
    """Explicit location_factor should override table-driven transformer lookup."""
    model = Transformer11To20kVPoFModel()
    asset = TransformerAsset(asset_id="A3", asset_name="Transformer A3")

    installation_auto = Installation(
        age_years=20,
        placement=Placement.OUTDOOR,
        altitude_m=250,
        distance_from_coast_km=0.5,
        corrosion_category_index=5,
    )
    installation_forced = Installation(
        age_years=20,
        placement=Placement.OUTDOOR,
        altitude_m=250,
        distance_from_coast_km=0.5,
        corrosion_category_index=5,
        location_factor=1.0,
    )

    auto = model.calculate_current(asset=asset, installation=installation_auto)
    forced = model.calculate_current(asset=asset, installation=installation_forced)

    assert auto.pof > forced.pof

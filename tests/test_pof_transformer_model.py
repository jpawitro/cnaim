"""Regression tests for the transformer PoF model."""

from __future__ import annotations

import pytest

from cnaim import Installation, Transformer11To20kVPoFModel, TransformerAsset


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

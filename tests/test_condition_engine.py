"""Tests for shared table-driven OCI/MCI evaluation and typed condition routing."""

from __future__ import annotations

import pytest

from cnaim.assets import LowVoltageAsset
from cnaim.condition_engine import (
    evaluate_table_driven_condition,
    supports_table_driven_condition,
)
from cnaim.condition_models import (
    LowVoltageConditionInput,
    NonSubmarineCableConditionInput,
    PoleConditionInput,
)
from cnaim.generic_models import CNAIMPoFModel
from cnaim.installation import Installation


def test_supports_table_driven_condition_for_expected_categories() -> None:
    """Known non-transformer families should route through the shared evaluator."""
    assert supports_table_driven_condition("LV UGB")
    assert supports_table_driven_condition("6.6/11kV Poles")
    assert not supports_table_driven_condition("11kV Transformer (GM)")


def test_hv_pole_top_rot_uses_dedicated_table_113() -> None:
    """Pole-top rot 'Yes' must apply table-113 degradation for HV poles."""
    condition = PoleConditionInput(
        visual_pole_condition="Acceptable",
        pole_top_rot_present="Yes",
        pole_leaning="Default",
        bird_animal_damage="Default",
        pole_decay_deterioration="Default",
    )

    aggregate = evaluate_table_driven_condition("6.6/11kV Poles", condition)

    assert aggregate is not None
    assert aggregate.observed_factor == pytest.approx(1.3)
    assert aggregate.measured_factor == pytest.approx(1.0)


def test_non_submarine_fault_history_sentinel_row_is_resolved() -> None:
    """Sentinel text for fault history should resolve the bounded-table sentinel row."""
    condition = NonSubmarineCableConditionInput(
        sheath_test_result="Pass",
        partial_discharge_test_result="Low",
        fault_rate="No historic faults recorded",
    )

    aggregate = evaluate_table_driven_condition(
        "33kV UG Cable (Non Pressurised)",
        condition,
    )

    assert aggregate is not None
    assert aggregate.measured_factor == pytest.approx(1.0)
    assert aggregate.measured_cap == pytest.approx(5.4)


def test_table_driven_condition_type_mismatch_raises() -> None:
    """Asset category profile and condition input model must match."""
    with pytest.raises(ValueError, match="Condition input type does not match"):
        evaluate_table_driven_condition("LV UGB", PoleConditionInput())


def test_generic_pof_accepts_typed_lv_condition_input() -> None:
    """Typed LV condition inputs should alter CHS/PoF through shared routing."""
    model = CNAIMPoFModel()
    asset = LowVoltageAsset(
        asset_id="LV-1",
        asset_name="LV UGB Test",
        asset_category="LV UGB",
    )
    installation = Installation(age_years=15)

    base = model.calculate_current(asset=asset, installation=installation)
    stressed = model.calculate_current(
        asset=asset,
        installation=installation,
        condition=LowVoltageConditionInput(
            steel_cover_and_pit_condition="Substantial Deterioration",
            operational_adequacy="Inoperable",
        ),
    )

    assert stressed.chs > base.chs
    assert stressed.pof > base.pof

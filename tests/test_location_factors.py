"""Tests for table-driven location factors from CNAIM tables 22-26."""

from __future__ import annotations

import pytest

from cnaim.enums import Placement
from cnaim.installation import Installation
from cnaim.location_factors import (
    default_placement_for_asset,
    location_factor_column_for_asset,
    location_factor_from_tables,
)


def test_table_26_default_placement_resolution() -> None:
    """Known categories resolve to expected Table 26 defaults."""
    assert default_placement_for_asset("6.6/11kV RMU") == Placement.INDOOR
    assert default_placement_for_asset("33kV Tower") == Placement.OUTDOOR
    assert default_placement_for_asset("LV UGB") is None


def test_location_factor_column_mapping_core_families() -> None:
    """Switchgear, transformer, tower, fittings, and conductor map to correct columns."""
    assert location_factor_column_for_asset("20kV Transformer (GM)") == "transformers"
    assert location_factor_column_for_asset("6.6/11kV RMU") == "switchgear"
    assert location_factor_column_for_asset("33kV Tower") == "towers_structure"
    assert location_factor_column_for_asset("132kV Fittings") == "towers_fittings"
    assert (
        location_factor_column_for_asset("132kV OHL (Tower Line) Conductor")
        == "towers_conductor"
    )


def test_location_factor_column_mapping_poles_and_fallback() -> None:
    """Poles use material mapping and default to concrete when material is unknown."""
    assert location_factor_column_for_asset("33kV Pole", sub_division="Steel") == "poles_steel"
    assert location_factor_column_for_asset("33kV Pole", sub_division="Wood") == "poles_wood"
    assert location_factor_column_for_asset("33kV Pole") == "poles_concrete"
    assert (
        location_factor_column_for_asset(
            "33kV Pole",
            sub_division="Other (e.g. fibreglass)",
        )
        == "poles_concrete"
    )


def test_non_submarine_cables_are_not_table_22_24_mapped() -> None:
    """Non-submarine and submarine cable categories are excluded from 22-24 mapping."""
    assert location_factor_column_for_asset("33kV UG Cable (Oil)") is None
    assert location_factor_column_for_asset("HV Sub Cable") is None


def test_location_factor_switchgear_outdoor_high_stress_case() -> None:
    """Outdoor switchgear with harsh inputs should follow table 22-25 formula."""
    location_factor = location_factor_from_tables(
        factor_column="switchgear",
        placement=Placement.OUTDOOR,
        altitude_m=250.0,
        distance_from_coast_km=0.5,
        corrosion_category_index=5,
    )
    assert location_factor == pytest.approx(1.45)


def test_location_factor_switchgear_indoor_high_stress_case() -> None:
    """Indoor switchgear should use the indoor branch scaling."""
    location_factor = location_factor_from_tables(
        factor_column="switchgear",
        placement=Placement.INDOOR,
        altitude_m=250.0,
        distance_from_coast_km=0.5,
        corrosion_category_index=5,
    )
    assert location_factor == pytest.approx(1.0375)


def test_location_factor_transformer_default_profile_matches_expected() -> None:
    """Transformer legacy default profile should still produce 0.925."""
    location_factor = location_factor_from_tables(
        factor_column="transformers",
        placement=Placement.INDOOR,
        altitude_m=150.0,
        distance_from_coast_km=15.0,
        corrosion_category_index=3,
    )
    assert location_factor == pytest.approx(0.925)


def test_installation_generic_uses_table_26_placement_and_cable_neutral() -> None:
    """Generic resolver should use table-driven defaults except for cable neutral behavior."""
    installation = Installation(age_years=5)

    resolved_switchgear = installation.resolve_generic(asset_category="6.6/11kV RMU")
    assert resolved_switchgear.placement == Placement.INDOOR
    assert resolved_switchgear.location_factor == pytest.approx(0.9)

    resolved_non_submarine_cable = installation.resolve_generic(
        asset_category="33kV UG Cable (Oil)"
    )
    assert resolved_non_submarine_cable.placement == Placement.OUTDOOR
    assert resolved_non_submarine_cable.location_factor == pytest.approx(1.0)


def test_installation_generic_pole_fallback_uses_concrete_column() -> None:
    """Poles without subdivision should use concrete column factors."""
    installation = Installation(
        age_years=5,
        placement=Placement.OUTDOOR,
        altitude_m=250.0,
        distance_from_coast_km=0.5,
        corrosion_category_index=5,
    )
    resolved = installation.resolve_generic(asset_category="33kV Pole")
    assert resolved.location_factor == pytest.approx(1.25)

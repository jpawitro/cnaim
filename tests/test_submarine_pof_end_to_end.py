"""End-to-end PoF tests for submarine cable assets."""

import pytest

from cnaim.assets import CableAsset
from cnaim.enums import (
    CombinedWaveEnergyIntensity,
    SheathTestResult,
    SubmarineArmourCondition,
    SubmarineSituation,
    SubmarineTopography,
)
from cnaim.generic_models import CNAIMPoFModel
from cnaim.installation import Installation
from cnaim.submarine import SubmarineCableConditionInput


@pytest.fixture()
def pof_model():
    return CNAIMPoFModel()


def _ehv_sub_cable(**kwargs) -> CableAsset:
    defaults = dict(
        asset_id="SUB-EHV-001",
        asset_name="EHV Submarine Cable",
        asset_category="EHV Sub Cable",
    )
    defaults.update(kwargs)
    return CableAsset(**defaults)


def _installation(age: float = 20.0) -> Installation:
    return Installation(age_years=age)


# ---------------------------------------------------------------------------
# Basic smoke test
# ---------------------------------------------------------------------------


def test_pof_returns_float_for_ehv_sub_cable(pof_model):
    asset = _ehv_sub_cable()
    result = pof_model.calculate_current(asset, _installation())
    assert isinstance(result.pof, float)
    assert 0.0 <= result.pof <= 1.0
    assert result.chs >= 0.5


def test_pof_returns_float_for_132kv_sub_cable(pof_model):
    asset = CableAsset(
        asset_id="SUB-132-001",
        asset_name="132kV Submarine Cable",
        asset_category="132kV Sub Cable",
    )
    result = pof_model.calculate_current(asset, _installation())
    assert isinstance(result.pof, float)
    assert 0.0 <= result.pof <= 1.0


# ---------------------------------------------------------------------------
# Location factor integration
# ---------------------------------------------------------------------------


def test_submarine_location_factor_applied(pof_model):
    """High topography should produce higher PoF than default topography."""
    asset_default = _ehv_sub_cable()
    asset_high = _ehv_sub_cable(
        topography=SubmarineTopography.VERY_HIGH,
        situation=SubmarineSituation.LAID_ON_BED,
        wind_wave_rating=3,
        combined_wave_energy_intensity=CombinedWaveEnergyIntensity.HIGH,
        is_landlocked=False,
    )
    result_default = pof_model.calculate_current(asset_default, _installation())
    result_high = pof_model.calculate_current(asset_high, _installation())
    # Higher location factor → shorter adjusted expected life → higher PoF
    assert result_high.pof > result_default.pof


def test_buried_lower_pof_than_laid_on_bed(pof_model):
    """Buried situation (factor 0.8 < 1.0) reduces location factor → lower PoF."""
    asset_bed = _ehv_sub_cable(
        topography=SubmarineTopography.DEFAULT,
        situation=SubmarineSituation.LAID_ON_BED,
        wind_wave_rating=None,
        is_landlocked=False,
    )
    asset_buried = _ehv_sub_cable(
        topography=SubmarineTopography.DEFAULT,
        situation=SubmarineSituation.BURIED,
        wind_wave_rating=None,
        is_landlocked=False,
    )
    result_bed = pof_model.calculate_current(asset_bed, _installation())
    result_buried = pof_model.calculate_current(asset_buried, _installation())
    assert result_buried.pof < result_bed.pof


def test_landlocked_vs_sea_pof(pof_model):
    """Landlocked assets use lower topography scores → generally lower location factor."""
    asset_sea = _ehv_sub_cable(
        topography=SubmarineTopography.VERY_HIGH,
        is_landlocked=False,
    )
    asset_ll = _ehv_sub_cable(
        topography=SubmarineTopography.VERY_HIGH,
        is_landlocked=True,
    )
    result_sea = pof_model.calculate_current(asset_sea, _installation())
    result_ll = pof_model.calculate_current(asset_ll, _installation())
    # sea score_sea=3.0 >> score_land_locked=1.2 → sea has higher PoF
    assert result_sea.pof > result_ll.pof


# ---------------------------------------------------------------------------
# Condition modifier integration
# ---------------------------------------------------------------------------


def test_condition_input_raises_pof(pof_model):
    """Poor armour condition and major sheath failure should raise PoF."""
    asset = _ehv_sub_cable()
    condition_clean = SubmarineCableConditionInput().to_asset_condition_input()
    condition_poor = SubmarineCableConditionInput(
        armour_condition=SubmarineArmourCondition.CRITICAL,
        sheath_test_result=SheathTestResult.FAILED_MAJOR,
        partial_discharge_level="High",
        fault_rate=0.5,
    ).to_asset_condition_input()

    result_clean = pof_model.calculate_current(asset, _installation(), condition=condition_clean)
    result_poor = pof_model.calculate_current(asset, _installation(), condition=condition_poor)
    assert result_poor.pof > result_clean.pof
    assert result_poor.chs > result_clean.chs


def test_condition_default_equals_no_condition_arg(pof_model):
    """Passing default SubmarineCableConditionInput == passing no condition arg."""
    asset = _ehv_sub_cable()
    installation = _installation()
    result_none = pof_model.calculate_current(asset, installation, condition=None)
    result_default = pof_model.calculate_current(
        asset,
        installation,
        condition=SubmarineCableConditionInput().to_asset_condition_input(),
    )
    assert result_none.pof == pytest.approx(result_default.pof, rel=1e-6)


# ---------------------------------------------------------------------------
# Future PoF trajectory
# ---------------------------------------------------------------------------


def test_future_pof_trajectory_increases(pof_model):
    """PoF should generally increase over the projection horizon."""
    asset = _ehv_sub_cable()
    result = pof_model.calculate_future(asset, _installation(age=5.0), simulation_end_year=50)
    assert result.future_points is not None
    pofs = [p.pof for p in result.future_points]
    # Not strictly monotone (ageing reduction factor), but later values higher
    assert pofs[-1] > pofs[0]


# ---------------------------------------------------------------------------
# Manual location_factor override
# ---------------------------------------------------------------------------


def test_explicit_location_factor_overrides_computation(pof_model):
    """When Installation.location_factor is set, it takes precedence."""
    asset = _ehv_sub_cable(
        topography=SubmarineTopography.VERY_HIGH,
        situation=SubmarineSituation.LAID_ON_BED,
        wind_wave_rating=3,
        combined_wave_energy_intensity=CombinedWaveEnergyIntensity.HIGH,
    )
    # Override with a neutral factor of 1.0
    install_forced = Installation(age_years=20.0, location_factor=1.0)
    install_auto = Installation(age_years=20.0)

    result_forced = pof_model.calculate_current(asset, install_forced)
    result_auto = pof_model.calculate_current(asset, install_auto)
    # Forced to 1.0 vs computed high → forced has lower PoF
    assert result_forced.pof < result_auto.pof

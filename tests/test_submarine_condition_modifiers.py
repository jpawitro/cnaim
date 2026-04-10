"""Tests for submarine cable OCI/MCI condition modifier functions."""

import pytest

from cnaim.enums import SheathTestResult, SubmarineArmourCondition
from cnaim.health import ConditionModifier
from cnaim.submarine import (
    SubmarineCableConditionInput,
    submarine_armour_condition_modifier,
    submarine_fault_history_modifier,
    submarine_partial_discharge_modifier,
    submarine_sheath_test_modifier,
)


# ---------------------------------------------------------------------------
# OCI — armour external condition (Table 107)
# ---------------------------------------------------------------------------


def test_armour_good():
    mod = submarine_armour_condition_modifier(SubmarineArmourCondition.GOOD)
    assert isinstance(mod, ConditionModifier)
    assert mod.factor == pytest.approx(1.0, abs=1e-9)
    assert mod.cap == pytest.approx(10.0, abs=1e-9)
    assert mod.collar == pytest.approx(0.5, abs=1e-9)


def test_armour_poor():
    mod = submarine_armour_condition_modifier(SubmarineArmourCondition.POOR)
    assert mod.factor == pytest.approx(1.6, abs=1e-9)
    assert mod.collar == pytest.approx(5.5, abs=1e-9)


def test_armour_critical():
    mod = submarine_armour_condition_modifier(SubmarineArmourCondition.CRITICAL)
    assert mod.factor == pytest.approx(1.8, abs=1e-9)
    assert mod.collar == pytest.approx(8.0, abs=1e-9)


def test_armour_default():
    mod = submarine_armour_condition_modifier(SubmarineArmourCondition.DEFAULT)
    assert mod.factor == pytest.approx(1.0, abs=1e-9)
    assert mod.collar == pytest.approx(0.5, abs=1e-9)


def test_armour_string_api():
    mod_enum = submarine_armour_condition_modifier(SubmarineArmourCondition.POOR)
    mod_str = submarine_armour_condition_modifier("Poor")
    assert mod_enum.factor == pytest.approx(mod_str.factor, abs=1e-9)


# ---------------------------------------------------------------------------
# MCI — sheath test (Table 189)
# ---------------------------------------------------------------------------


def test_sheath_pass():
    mod = submarine_sheath_test_modifier(SheathTestResult.PASS)
    assert mod.factor == pytest.approx(1.0, abs=1e-9)
    assert mod.collar == pytest.approx(0.5, abs=1e-9)


def test_sheath_failed_minor():
    mod = submarine_sheath_test_modifier(SheathTestResult.FAILED_MINOR)
    assert mod.factor == pytest.approx(1.3, abs=1e-9)
    assert mod.collar == pytest.approx(0.5, abs=1e-9)


def test_sheath_failed_major():
    mod = submarine_sheath_test_modifier(SheathTestResult.FAILED_MAJOR)
    assert mod.factor == pytest.approx(1.6, abs=1e-9)
    assert mod.collar == pytest.approx(5.5, abs=1e-9)


def test_sheath_default():
    mod = submarine_sheath_test_modifier(SheathTestResult.DEFAULT)
    assert mod.factor == pytest.approx(1.0, abs=1e-9)


def test_sheath_string_api():
    mod_enum = submarine_sheath_test_modifier(SheathTestResult.FAILED_MAJOR)
    mod_str = submarine_sheath_test_modifier("Failed Major")
    assert mod_enum.factor == pytest.approx(mod_str.factor, abs=1e-9)


# ---------------------------------------------------------------------------
# MCI — partial discharge (Table 190)
# ---------------------------------------------------------------------------


def test_pd_low():
    mod = submarine_partial_discharge_modifier("Low")
    assert mod.factor == pytest.approx(1.0, abs=1e-9)
    assert mod.collar == pytest.approx(0.5, abs=1e-9)


def test_pd_medium():
    mod = submarine_partial_discharge_modifier("Medium")
    assert mod.factor == pytest.approx(1.15, abs=1e-9)


def test_pd_high():
    mod = submarine_partial_discharge_modifier("High")
    assert mod.factor == pytest.approx(1.5, abs=1e-9)
    assert mod.collar == pytest.approx(5.5, abs=1e-9)


def test_pd_default():
    mod = submarine_partial_discharge_modifier("Default")
    assert mod.factor == pytest.approx(1.0, abs=1e-9)


# ---------------------------------------------------------------------------
# MCI — fault history (Table 191)
# ---------------------------------------------------------------------------


def test_fault_hist_no_faults():
    mod = submarine_fault_history_modifier("No historic faults recorded")
    assert mod.factor == pytest.approx(1.0, abs=1e-9)
    assert mod.cap == pytest.approx(5.4, abs=1e-9)
    assert mod.collar == pytest.approx(0.5, abs=1e-9)


def test_fault_hist_low_rate():
    """Fault rate <= 0.01 → factor 1.3 (second band: -Inf < rate <= 0.01)."""
    mod = submarine_fault_history_modifier(0.005)
    assert mod.factor == pytest.approx(1.3, abs=1e-9)


def test_fault_hist_medium_rate():
    """Fault rate in (0.01, 0.1] → factor 1.6."""
    mod = submarine_fault_history_modifier(0.05)
    assert mod.factor == pytest.approx(1.6, abs=1e-9)
    assert mod.collar == pytest.approx(5.5, abs=1e-9)


def test_fault_hist_high_rate():
    """Fault rate > 0.1 → factor 1.8."""
    mod = submarine_fault_history_modifier(0.5)
    assert mod.factor == pytest.approx(1.8, abs=1e-9)
    assert mod.collar == pytest.approx(8.0, abs=1e-9)


def test_fault_hist_default_string():
    mod = submarine_fault_history_modifier("Default")
    assert mod.factor == pytest.approx(1.0, abs=1e-9)


def test_fault_hist_zero_rate():
    """Exact zero (0.0) falls in first numeric band (-Inf, 0.01] → factor 1.3."""
    mod = submarine_fault_history_modifier(0.0)
    assert mod.factor == pytest.approx(1.3, abs=1e-9)


def test_fault_hist_boundary_0_01():
    """Boundary value 0.01 belongs to band (-Inf, 0.01] → factor 1.3."""
    mod = submarine_fault_history_modifier(0.01)
    assert mod.factor == pytest.approx(1.3, abs=1e-9)


def test_fault_hist_just_above_0_01():
    """0.011 falls in (0.01, 0.1] → factor 1.6."""
    mod = submarine_fault_history_modifier(0.011)
    assert mod.factor == pytest.approx(1.6, abs=1e-9)


# ---------------------------------------------------------------------------
# SubmarineCableConditionInput.to_asset_condition_input() integration
# ---------------------------------------------------------------------------


def test_all_defaults_produce_unit_factors():
    """All default inputs → combined factor = 1.0."""
    sci = SubmarineCableConditionInput()
    aci = sci.to_asset_condition_input()
    assert aci.observed_condition_factor == pytest.approx(1.0, abs=1e-9)
    assert aci.measured_condition_factor == pytest.approx(1.0, abs=1e-9)


def test_combined_oci_poor_raises_observed_factor():
    """Poor armour condition should raise the observed_condition_factor above 1."""
    sci = SubmarineCableConditionInput(armour_condition=SubmarineArmourCondition.POOR)
    aci = sci.to_asset_condition_input()
    assert aci.observed_condition_factor == pytest.approx(1.6, abs=1e-9)


def test_combined_mci_uses_mmi():
    """Multiple MCI inputs: MMI must return max + scaled cumulative excess."""
    # sheath=1.6, pd=1.15, fault=1.0 → sorted desc: [1.6, 1.15, 1.0]
    # MMI(divider1=1.5, max_combined=2): var1=1.6, var2=(1.15-1)=0.15, total=0.15
    # result = 1.6 + 0.15/1.5 = 1.6 + 0.1 = 1.7
    sci = SubmarineCableConditionInput(
        sheath_test_result=SheathTestResult.FAILED_MAJOR,
        partial_discharge_level="Medium",
        fault_rate="Default",
    )
    aci = sci.to_asset_condition_input()
    assert aci.measured_condition_factor == pytest.approx(1.7, abs=1e-9)


def test_combined_collar_is_worst_case():
    """The MCI collar should reflect the maximum collar across all MCI modifiers."""
    sci = SubmarineCableConditionInput(
        sheath_test_result=SheathTestResult.FAILED_MAJOR,  # collar=5.5
        partial_discharge_level="High",                     # collar=5.5
        fault_rate=0.5,                                     # collar=8.0
    )
    aci = sci.to_asset_condition_input()
    # max collar across the three MCI inputs = 8.0
    assert aci.measured_condition_collar == pytest.approx(8.0, abs=1e-9)


def test_combined_cap_is_minimum():
    """The combined cap is the minimum cap across OCI and MCI modifiers."""
    sci = SubmarineCableConditionInput(
        armour_condition=SubmarineArmourCondition.CRITICAL,  # cap=10
        sheath_test_result=SheathTestResult.PASS,            # cap=10
        fault_rate="No historic faults recorded",            # cap=5.4
    )
    aci = sci.to_asset_condition_input()
    assert aci.measured_condition_cap == pytest.approx(5.4, abs=1e-9)

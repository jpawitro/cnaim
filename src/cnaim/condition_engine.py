"""Shared table-driven OCI/MCI evaluator for non-transformer families."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

from .condition_models import (
    FittingsConditionInput,
    LowVoltageConditionInput,
    NonSubmarineCableConditionInput,
    PoleConditionInput,
    SwitchgearConditionInput,
    TableDrivenConditionInput,
    TowerConditionInput,
    TowerLineConductorConditionInput,
)
from .health import ConditionModifier, mmi
from .lookups import canonical_name, coerce_numeric, load_reference_table


@dataclass(frozen=True)
class ConditionAggregate:
    """Final observed/measured condition aggregate used by generic PoF calculations."""

    observed_factor: float = 1.0
    measured_factor: float = 1.0
    observed_cap: float = 10.0
    measured_cap: float = 10.0
    observed_collar: float = 0.5
    measured_collar: float = 0.5


@dataclass(frozen=True)
class _MMIConfig:
    factor_divider_1: float
    factor_divider_2: float
    max_no_combined_factors: int


@dataclass(frozen=True)
class _CriterionSpec:
    criterion: str
    table_id: str


@dataclass(frozen=True)
class _ConditionGroup:
    criteria: tuple[_CriterionSpec, ...]
    mmi_config: _MMIConfig | None


@dataclass(frozen=True)
class _ProfileDefinition:
    input_type: type[TableDrivenConditionInput]
    observed_groups: tuple[_ConditionGroup, ...]
    measured_groups: tuple[_ConditionGroup, ...]


def _mmi(max_combined: int | None) -> _MMIConfig | None:
    if max_combined is None:
        return None
    return _MMIConfig(
        factor_divider_1=1.5,
        factor_divider_2=1.5,
        max_no_combined_factors=max_combined,
    )


def _group(criteria_and_tables: list[tuple[str, str]], max_combined: int | None) -> _ConditionGroup:
    return _ConditionGroup(
        criteria=tuple(_CriterionSpec(criterion=criterion, table_id=table_id) for criterion, table_id in criteria_and_tables),
        mmi_config=_mmi(max_combined),
    )


# Mapping from runtime asset register categories to condition profile categories
# (tables 12-15 / 35-202).
_PROFILE_FOR_ASSET_CATEGORY: dict[str, str] = {
    # Low voltage
    "LV UGB": "LV UGB",
    "LV Circuit Breaker": "LV Circuit Breaker",
    "LV Board (WM)": "LV Board (WM)",
    "LV Board (X-type Network) (WM)": "LV Board (WM)",
    "LV Pillar (ID)": "LV Pillars",
    "LV Pillar (OD at Substation)": "LV Pillars",
    "LV Pillar (OD not at a Substation)": "LV Pillars",
    # Switchgear
    "6.6/11kV CB (GM) Primary": "HV Switchgear (GM) - Primary",
    "20kV CB (GM) Primary": "HV Switchgear (GM) - Primary",
    "6.6/11kV CB (GM) Secondary": "HV Switchgear (GM) - Distribution",
    "6.6/11kV RMU": "HV Switchgear (GM) - Distribution",
    "6.6/11kV X-type RMU": "HV Switchgear (GM) - Distribution",
    "6.6/11kV Switch (GM)": "HV Switchgear (GM) - Distribution",
    "20kV CB (GM) Secondary": "HV Switchgear (GM) - Distribution",
    "20kV RMU": "HV Switchgear (GM) - Distribution",
    "20kV Switch (GM)": "HV Switchgear (GM) - Distribution",
    "33kV CB (Air Insulated Busbars)(ID) (GM)": "EHV Switchgear (GM)",
    "33kV CB (Air Insulated Busbars)(OD) (GM)": "EHV Switchgear (GM)",
    "33kV CB (Gas Insulated Busbars)(ID) (GM)": "EHV Switchgear (GM)",
    "33kV CB (Gas Insulated Busbars)(OD) (GM)": "EHV Switchgear (GM)",
    "33kV RMU": "EHV Switchgear (GM)",
    "33kV Switch (GM)": "EHV Switchgear (GM)",
    "66kV CB (Air Insulated Busbars)(ID) (GM)": "EHV Switchgear (GM)",
    "66kV CB (Air Insulated Busbars)(OD) (GM)": "EHV Switchgear (GM)",
    "66kV CB (Gas Insulated Busbars)(ID) (GM)": "EHV Switchgear (GM)",
    "66kV CB (Gas Insulated Busbars)(OD) (GM)": "EHV Switchgear (GM)",
    "132kV CB (Air Insulated Busbars)(ID) (GM)": "132kV Switchgear (GM)",
    "132kV CB (Air Insulated Busbars)(OD) (GM)": "132kV Switchgear (GM)",
    "132kV CB (Gas Insulated Busbars)(ID) (GM)": "132kV Switchgear (GM)",
    "132kV CB (Gas Insulated Busbars)(OD) (GM)": "132kV Switchgear (GM)",
    # Non-submarine cables
    "33kV UG Cable (Non Pressurised)": "EHV Cable (Non Pressurised)",
    "66kV UG Cable (Non Pressurised)": "EHV Cable (Non Pressurised)",
    "33kV UG Cable (Oil)": "EHV Cable (Oil)",
    "66kV UG Cable (Oil)": "EHV Cable (Oil)",
    "33kV UG Cable (Gas)": "EHV Cable (Gas)",
    "66kV UG Cable (Gas)": "EHV Cable (Gas)",
    "132kV UG Cable (Non Pressurised)": "132kV Cable (Non Pressurised)",
    "132kV UG Cable (Oil)": "132kV Cable (Oil)",
    "132kV UG Cable (Gas)": "132kV Cable (Gas)",
    # Poles
    "LV Poles": "LV Poles",
    "6.6/11kV Poles": "HV Poles",
    "20kV Poles": "HV Poles",
    "33kV Pole": "EHV Poles",
    "66kV Pole": "EHV Poles",
    # Towers
    "33kV Tower": "EHV Towers",
    "66kV Tower": "EHV Towers",
    "132kV Tower": "132kV Towers",
    # Fittings
    "33kV Fittings": "EHV Fittings",
    "66kV Fittings": "EHV Fittings",
    "132kV Fittings": "132kV Fittings",
    # Tower line conductors
    "33kV OHL (Tower Line) Conductor": "EHV Tower Line Conductor",
    "66kV OHL (Tower Line) Conductor": "EHV Tower Line Conductor",
    "132kV OHL (Tower Line) Conductor": "132kV Tower Line Conductor",
}


_PROFILE_DEFINITIONS: dict[str, _ProfileDefinition] = {
    "LV UGB": _ProfileDefinition(
        input_type=LowVoltageConditionInput,
        observed_groups=(
            _group(
                [
                    ("Steel Cover and Pit condition", "oci_lv_ugb_steel_covr_pit_cond"),
                    ("Water/Moisture", "oci_lv_ugb_water_moisture"),
                    ("Bell Condition", "oci_lv_ugb_bell_cond"),
                    ("Insulation Condition", "oci_lv_ugb_insulation_cond"),
                    ("Signs of heating", "oci_lv_ugb_signs_heating"),
                    ("Phase Barriers", "oci_lv_ugb_phase_barriers"),
                ],
                3,
            ),
        ),
        measured_groups=(
            _group(
                [("Operational Adequacy", "mci_lv_ugb_opsal_adequacy")],
                1,
            ),
        ),
    ),
    "LV Circuit Breaker": _ProfileDefinition(
        input_type=LowVoltageConditionInput,
        observed_groups=(
            _group(
                [("Switchgear external condition", "oci_lv_circuit_breakr_ext_cond")],
                1,
            ),
        ),
        measured_groups=(
            _group(
                [("Operational Adequacy", "mci_lv_cb_opsal_adequacy")],
                1,
            ),
        ),
    ),
    "LV Board (WM)": _ProfileDefinition(
        input_type=LowVoltageConditionInput,
        observed_groups=(
            _group(
                [
                    ("Switchgear external condition", "oci_lv_board_swg_ext_cond"),
                    ("Compound Leaks", "oci_lv_board_wm_compound_leak"),
                    (
                        "Switchgear internal condition",
                        "oci_lv_board_wm_swg_int_cond",
                    ),
                    ("Insulation", "oci_lv_board_wm_insulation_cond"),
                    ("Signs of Heating", "oci_lv_board_wm_signs_heating"),
                    ("Phase Barriers", "oci_lv_board_wm_phase_barriers"),
                ],
                3,
            ),
        ),
        measured_groups=(
            _group(
                [("Operational Adequacy", "mci_lv_board_wm_opsal_adequacy")],
                1,
            ),
        ),
    ),
    "LV Pillars": _ProfileDefinition(
        input_type=LowVoltageConditionInput,
        observed_groups=(
            _group(
                [
                    ("Switchgear external condition", "oci_lv_pillar_swg_ext_cond"),
                    ("Compound Leaks", "oci_lv_pillar_compound_leak"),
                    (
                        "Switchgear internal condition",
                        "oci_lv_pillar_swg_int_cond_op",
                    ),
                    ("Insulation", "oci_lv_pillar_insulation_cond"),
                    ("Signs of Heating", "oci_lv_pillar_signs_heating"),
                    ("Phase Barriers", "oci_lv_pillar_phase_barrier"),
                ],
                3,
            ),
        ),
        measured_groups=(
            _group(
                [("Operational Adequacy", "mci_lv_pillar_opsal_adequacy")],
                1,
            ),
        ),
    ),
    "HV Switchgear (GM) - Distribution": _ProfileDefinition(
        input_type=SwitchgearConditionInput,
        observed_groups=(
            _group(
                [
                    ("Switchgear external condition", "oci_hv_swg_dist_swg_ext_cond"),
                    ("Cable boxes conditions", "oci_hv_swg_dist_cable_box_cond"),
                    ("Oil leaks/ Gas pressure", "oci_hv_swg_dist_oil_lek_gas_pr"),
                    ("Thermographic Assessment", "oci_hv_swg_dist_thermo_assment"),
                    (
                        "Switchgear internal condition and operation",
                        "oci_hv_swg_dist_swg_int_cond",
                    ),
                    ("Indoor Environment", "oci_hv_swg_dist_indoor_environ"),
                ],
                3,
            ),
        ),
        measured_groups=(
            _group(
                [
                    ("Partial Discharge", "mci_hv_swg_distr_prtl_dischrg"),
                    ("Ductor Test", "mci_hv_swg_distr_ductor_test"),
                    ("Oil Tests", "mci_hv_swg_distr_oil_test"),
                    ("Temperature Readings", "mci_hv_swg_distr_temp_reading"),
                    ("Trip Test", "mci_hv_swg_distr_trip_test"),
                ],
                3,
            ),
        ),
    ),
    "HV Switchgear (GM) - Primary": _ProfileDefinition(
        input_type=SwitchgearConditionInput,
        observed_groups=(
            _group(
                [
                    ("Switchgear external condition", "oci_hv_swg_pri_swg_ext"),
                    ("Cable boxes conditions", "oci_hv_swg_pri_cable_box_cond"),
                    ("Oil leaks/ Gas pressure", "oci_hv_swg_pri_oil_leak_gas_pr"),
                    ("Thermographic Assessment", "oci_hv_swg_pri_thermo_assment"),
                    (
                        "Switchgear internal condition and operation",
                        "oci_hv_swg_pri_swg_int_cond_op",
                    ),
                    ("Indoor Environment", "oci_hv_swg_pri_indoor_environ"),
                ],
                3,
            ),
        ),
        measured_groups=(
            _group(
                [
                    ("Partial Discharge", "mci_hv_swg_pri_prtl_dischrg"),
                    ("Ductor Test", "mci_hv_swg_pri_ductor_test"),
                    ("IR Test", "mci_hv_swg_pri_ir_test"),
                    ("Oil Tests", "mci_hv_swg_pri_oil_tests"),
                    ("Temperature Readings", "mci_hv_swg_pri_temp_reading"),
                    ("Trip Test", "mci_hv_swg_pri_trip_test"),
                ],
                3,
            ),
        ),
    ),
    "EHV Switchgear (GM)": _ProfileDefinition(
        input_type=SwitchgearConditionInput,
        observed_groups=(
            _group(
                [
                    ("Switchgear external condition", "oci_ehv_swg_swg_ext_cond"),
                    ("Cable boxes conditions", "oci_ehv_swg_pri_cable_box_cond"),
                    ("Oil leaks/ Gas pressure", "oci_ehv_swg_oil_leak_gas_pr"),
                    ("Thermographic Assessment", "oci_ehv_swg_thermo_assessment"),
                    (
                        "Switchgear internal condition and operation",
                        "oci_ehv_swg_swg_int_cond_ops",
                    ),
                    ("Indoor Environment", "oci_ehv_swg_indoor_environ"),
                    ("Support Structures", "oci_ehv_swg_support_structure"),
                ],
                3,
            ),
        ),
        measured_groups=(
            _group(
                [
                    ("Partial Discharge", "mci_ehv_swg_partial_discharge"),
                    ("Ductor Test", "mci_ehv_swg_ductor_test"),
                    ("IR Test", "mci_ehv_swg_ir_test"),
                    ("Oil Tests/ Gas Tests", "mci_ehv_swg_oil_tests_gas_test"),
                    ("Temperature Readings", "mci_ehv_swg_temp_readings"),
                    ("Trip Test", "mci_ehv_swg_trip_test"),
                ],
                3,
            ),
        ),
    ),
    "132kV Switchgear (GM)": _ProfileDefinition(
        input_type=SwitchgearConditionInput,
        observed_groups=(
            _group(
                [
                    ("Switchgear external condition", "oci_132kv_swg_swg_ext_cond"),
                    ("Cable boxes conditions", "oci_132kv_swg_cable_boxes_cond"),
                    ("Oil leaks/ Gas pressure", "oci_132kv_swg_oil_leak_gas_pr"),
                    ("Thermographic Assessment", "oci_132kv_swg_thermo_assment"),
                    (
                        "Switchgear internal condition and operation",
                        "oci_132kv_swg_swg_int_cond_ops",
                    ),
                    ("Indoor Environment", "oci_132kv_swg_indoor_environ"),
                    ("Support Structures", "oci_132kv_swg_support_structur"),
                    ("Air systems", "oci_132kv_swg_air_systems"),
                ],
                3,
            ),
        ),
        measured_groups=(
            _group(
                [
                    ("Partial Discharge", "mci_132kv_swg_partial_discharg"),
                    ("Ductor Test", "mci_132kv_swg_ductor_test"),
                    ("IR Test", "mci_132kv_swg_ir_test"),
                    ("Oil Tests/ Gas Tests", "mci_132kv_swg_oil_gas_test"),
                    ("Temperature Readings", "mci_132kv_swg_temp_reading"),
                    ("Trip Test", "mci_132kv_swg_trip_test"),
                ],
                3,
            ),
        ),
    ),
    "EHV Cable (Non Pressurised)": _ProfileDefinition(
        input_type=NonSubmarineCableConditionInput,
        observed_groups=(),
        measured_groups=(
            _group(
                [
                    ("Sheath Test", "mci_ehv_cbl_non_pr_sheath_test"),
                    ("Partial Discharge", "mci_ehv_cbl_non_pr_prtl_disch"),
                    ("Fault history", "mci_ehv_cbl_non_pr_fault_hist"),
                ],
                2,
            ),
        ),
    ),
    "EHV Cable (Oil)": _ProfileDefinition(
        input_type=NonSubmarineCableConditionInput,
        observed_groups=(
            _group(
                [("Presence of Crystalline Lead", "oci_ehv_cable_oil_cry_lead")],
                1,
            ),
        ),
        measured_groups=(
            _group(
                [("Leakage", "mci_ehv_cable_oil_leakage")],
                1,
            ),
        ),
    ),
    "EHV Cable (Gas)": _ProfileDefinition(
        input_type=NonSubmarineCableConditionInput,
        observed_groups=(
            _group(
                [("Presence of Crystalline Lead", "oci_ehv_cable_gas_cry_lead")],
                1,
            ),
        ),
        measured_groups=(
            _group(
                [("Leakage", "mci_ehv_cable_gas_leakage")],
                1,
            ),
        ),
    ),
    "132kV Cable (Non Pressurised)": _ProfileDefinition(
        input_type=NonSubmarineCableConditionInput,
        observed_groups=(),
        measured_groups=(
            _group(
                [
                    ("Sheath Test", "mci_132kv_cbl_non_pr_shth_test"),
                    ("Partial Discharge", "mci_132kv_cbl_non_pr_prtl_disc"),
                    ("Fault history", "mci_132kv_cbl_non_pr_flt_hist"),
                ],
                2,
            ),
        ),
    ),
    "132kV Cable (Oil)": _ProfileDefinition(
        input_type=NonSubmarineCableConditionInput,
        observed_groups=(
            _group(
                [("Presence of Crystalline Lead", "oci_132kv_cable_oil_cry_lead")],
                1,
            ),
        ),
        measured_groups=(
            _group(
                [("Leakage", "mci_132kv_cable_oil_leakage")],
                1,
            ),
        ),
    ),
    "132kV Cable (Gas)": _ProfileDefinition(
        input_type=NonSubmarineCableConditionInput,
        observed_groups=(
            _group(
                [("Presence of Crystalline Lead", "oci_132kv_cable_gas_cry_lead")],
                1,
            ),
        ),
        measured_groups=(
            _group(
                [("Leakage", "mci_132kv_cable_gas_leakage")],
                1,
            ),
        ),
    ),
    "LV Poles": _ProfileDefinition(
        input_type=PoleConditionInput,
        observed_groups=(
            _group(
                [
                    ("Visual Pole Condition", "oci_lv_pole_visual_pole_cond"),
                    ("Pole Top Rot", "oci_lv_pole_pole_top_rot"),
                    ("Pole Leaning", "oci_lv_pole_pole_leaning"),
                    ("Bird / Animal Damage", "oci_lv_pole_bird_animal_damage"),
                ],
                2,
            ),
        ),
        measured_groups=(
            _group(
                [("Pole decay / deterioration", "mci_lv_pole_pole_decay_deter")],
                1,
            ),
        ),
    ),
    "HV Poles": _ProfileDefinition(
        input_type=PoleConditionInput,
        observed_groups=(
            _group(
                [
                    ("Visual Pole Condition", "oci_hv_pole_visual_pole_cond"),
                    ("Pole Top Rot", "oci_hv_pole_pole_top_rot"),
                    ("Pole Leaning", "oci_hv_pole_pole_leaning"),
                    ("Bird / Animal Damage", "oci_hv_pole_bird_animal_damage"),
                ],
                2,
            ),
        ),
        measured_groups=(
            _group(
                [("Pole decay / deterioration", "mci_hv_pole_pole_decay_deter")],
                1,
            ),
        ),
    ),
    "EHV Poles": _ProfileDefinition(
        input_type=PoleConditionInput,
        observed_groups=(
            _group(
                [
                    ("Visual Pole Condition", "oci_ehv_pole_visual_pole_cond"),
                    ("Pole Top Rot", "oci_ehv_pole_pole_top_rot"),
                    ("Pole Leaning", "oci_ehv_pole_pole_leaning"),
                    ("Bird / Animal Damage", "oci_ehv_pole_bird_animal_damag"),
                ],
                2,
            ),
        ),
        measured_groups=(
            _group(
                [("Pole decay / deterioration", "mci_ehv_pole_pole_decay_deter")],
                1,
            ),
        ),
    ),
    "EHV Towers": _ProfileDefinition(
        input_type=TowerConditionInput,
        observed_groups=(
            _group(
                [
                    ("Tower Legs", "oci_ehv_tower_tower_legs"),
                    ("Bracings", "oci_ehv_tower_bracings"),
                    ("Crossarms", "oci_ehv_tower_crossarms"),
                    ("Peak", "oci_ehv_tower_peak"),
                ],
                3,
            ),
            _group(
                [("Paintwork Condition", "oci_ehv_tower_paintwork_cond")],
                1,
            ),
            _group(
                [("Foundation Condition", "oci_ehv_tower_foundation_cond")],
                1,
            ),
        ),
        measured_groups=(),
    ),
    "132kV Towers": _ProfileDefinition(
        input_type=TowerConditionInput,
        observed_groups=(
            _group(
                [
                    ("Tower Legs", "oci_132kv_tower_tower_legs"),
                    ("Bracings", "oci_132kv_tower_bracings"),
                    ("Crossarms", "oci_132kv_tower_crossarms"),
                    ("Peak", "oci_132kv_tower_peak"),
                ],
                3,
            ),
            _group(
                [("Paintwork Condition", "oci_132kv_tower_paintwork_cond")],
                1,
            ),
            _group(
                [("Foundation Condition", "oci_132kv_tower_fondation_cond")],
                1,
            ),
        ),
        measured_groups=(),
    ),
    "EHV Fittings": _ProfileDefinition(
        input_type=FittingsConditionInput,
        observed_groups=(
            _group(
                [
                    ("Tower fittings", "oci_ehv_twr_fitting_cond"),
                    ("Conductor fittings", "oci_ehv_cond_fitting_cond"),
                    (
                        "Insulators - Electrical",
                        "oci_ehv_fitg_insltr_elect_cond",
                    ),
                    (
                        "Insulators - Mechanical",
                        "oci_ehv_fitg_insltr_mech_cond",
                    ),
                ],
                3,
            ),
        ),
        measured_groups=(
            _group(
                [
                    ("Thermal Imaging", "mci_ehv_fittings_thrml_imaging"),
                    ("Ductor Tests", "mci_ehv_fittings_ductor_test"),
                ],
                1,
            ),
        ),
    ),
    "132kV Fittings": _ProfileDefinition(
        input_type=FittingsConditionInput,
        observed_groups=(
            _group(
                [
                    ("Tower fittings", "oci_132kv_tower_fitting_cond"),
                    ("Conductor fittings", "oci_132kv_cond_fitting_cond"),
                    (
                        "Insulators - Electrical",
                        "oci_132kv_insulatr_elect_cond",
                    ),
                    (
                        "Insulators - Mechanical",
                        "oci_132kv_insulatr_mech_cond",
                    ),
                ],
                3,
            ),
        ),
        measured_groups=(
            _group(
                [
                    ("Thermal Imaging", "mci_132kv_fittings_therml_imag"),
                    ("Ductor Tests", "mci_132kv_fittings_ductor_test"),
                ],
                1,
            ),
        ),
    ),
    "EHV Tower Line Conductor": _ProfileDefinition(
        input_type=TowerLineConductorConditionInput,
        observed_groups=(
            _group(
                [
                    ("Visual Condition", "oci_ehv_twr_line_visal_cond"),
                    ("Midspan joints", "oci_ehv_twr_cond_midspan_joint"),
                ],
                1,
            ),
        ),
        measured_groups=(
            _group(
                [
                    ("Conductor Sampling", "mci_ehv_twr_line_cond_sampl"),
                    (
                        "Corrosion Monitoring Survey",
                        "mci_ehv_twr_line_cond_srvy",
                    ),
                ],
                1,
            ),
        ),
    ),
    "132kV Tower Line Conductor": _ProfileDefinition(
        input_type=TowerLineConductorConditionInput,
        observed_groups=(
            _group(
                [
                    ("Visual Condition", "oci_132kv_twr_line_visual_cond"),
                    ("Midspan joints", "oci_132kv_twr_line_cond_midspn"),
                ],
                1,
            ),
        ),
        measured_groups=(
            _group(
                [
                    ("Conductor Sampling", "mci_132kv_twr_line_cond_sampl"),
                    (
                        "Corrosion Monitoring Survey",
                        "mci_132kv_twr_line_cond_srvy",
                    ),
                ],
                1,
            ),
        ),
    ),
}


_CRITERIA_TO_FIELD_BY_TYPE: dict[type[TableDrivenConditionInput], dict[str, str]] = {
    LowVoltageConditionInput: {
        "steelcoverandpitcondition": "steel_cover_and_pit_condition",
        "watermoisture": "water_moisture",
        "bellcondition": "bell_condition",
        "insulationcondition": "insulation_condition",
        "signsofheating": "signs_of_heating",
        "phasebarriers": "phase_barriers",
        "switchgearexternalcondition": "switchgear_external_condition",
        "compoundleaks": "compound_leaks",
        "switchgearinternalcondition": "switchgear_internal_condition_operation",
        "switchgearinternalconditionandoperation": "switchgear_internal_condition_operation",
        "operationaladequacy": "operational_adequacy",
        "security": "operational_adequacy",
    },
    SwitchgearConditionInput: {
        "switchgearexternalcondition": "switchgear_external_condition",
        "cableboxesconditions": "cable_boxes_condition",
        "cableboxescondition": "cable_boxes_condition",
        "oilleaksgaspressure": "oil_leaks_gas_pressure",
        "thermographicassessment": "thermographic_assessment",
        "switchgearinternalcondition": "switchgear_internal_condition_operation",
        "switchgearinternalconditionandoperation": "switchgear_internal_condition_operation",
        "indoorenvironment": "indoor_environment",
        "supportstructures": "support_structures",
        "airsystems": "air_systems",
        "partialdischarge": "partial_discharge_test_results",
        "partialdischargetestresults": "partial_discharge_test_results",
        "ductortest": "ductor_test_results",
        "ductortestresults": "ductor_test_results",
        "irtest": "ir_test_results",
        "irtestresults": "ir_test_results",
        "oiltests": "oil_or_gas_test_results",
        "oiltestsgastests": "oil_or_gas_test_results",
        "temperaturereadings": "temperature_readings",
        "temperaturereading": "temperature_readings",
        "triptest": "trip_test_results",
        "triptestresults": "trip_test_results",
    },
    NonSubmarineCableConditionInput: {
        "presenceofcrystallinelead": "crystalline_lead_presence",
        "sheathtest": "sheath_test_result",
        "sheathtestresult": "sheath_test_result",
        "partialdischarge": "partial_discharge_test_result",
        "partialdischargetestresult": "partial_discharge_test_result",
        "faulthistory": "fault_rate",
        "leakage": "leakage_rate",
        "leakagerate": "leakage_rate",
    },
    PoleConditionInput: {
        "visualpolecondition": "visual_pole_condition",
        "poletoprot": "pole_top_rot_present",
        "poletoprotpresent": "pole_top_rot_present",
        "poleleaning": "pole_leaning",
        "birdanimaldamage": "bird_animal_damage",
        "poledecaydeterioration": "pole_decay_deterioration",
    },
    TowerConditionInput: {
        "towerlegs": "tower_legs",
        "bracings": "bracings",
        "crossarms": "crossarms",
        "peak": "peak",
        "paintworkcondition": "paintwork_condition",
        "foundationcondition": "foundation_condition",
    },
    FittingsConditionInput: {
        "towerfittings": "tower_fittings_condition",
        "towerfittingscondition": "tower_fittings_condition",
        "conductorfittings": "conductor_fittings_condition",
        "conductorfittingscondition": "conductor_fittings_condition",
        "insulatorselectrical": "insulators_electrical_condition",
        "insulatorselectricalcondition": "insulators_electrical_condition",
        "insulatorsmechanical": "insulators_mechanical_condition",
        "insulatorsmechanicalcondition": "insulators_mechanical_condition",
        "thermalimaging": "thermal_imaging_result",
        "thermalimagingresult": "thermal_imaging_result",
        "ductortests": "ductor_test_result",
        "ductortest": "ductor_test_result",
    },
    TowerLineConductorConditionInput: {
        "visualcondition": "visual_condition",
        "midspanjoints": "midspan_joints",
        "conductorsampling": "conductor_sampling_result",
        "conductorsamplingresult": "conductor_sampling_result",
        "corrosionmonitoringsurvey": "corrosion_monitoring_survey_result",
        "corrosionmonitoringsurveyresult": "corrosion_monitoring_survey_result",
    },
}


def resolve_profile_for_asset_category(asset_category: str) -> str | None:
    """Resolve runtime asset category to the table-driven OCI/MCI profile key."""
    return _PROFILE_FOR_ASSET_CATEGORY.get(asset_category)


def supports_table_driven_condition(asset_category: str) -> bool:
    """Return whether the asset category uses this shared non-submarine evaluator."""
    return resolve_profile_for_asset_category(asset_category) is not None


def evaluate_table_driven_condition(
    asset_category: str,
    condition: TableDrivenConditionInput | None,
) -> ConditionAggregate | None:
    """Evaluate OCI/MCI for non-transformer families and return aggregate modifiers.

    Returns ``None`` when the asset category is not handled by this evaluator
    (for example transformer and submarine categories that use dedicated paths).
    """
    profile_key = resolve_profile_for_asset_category(asset_category)
    if profile_key is None:
        return None

    profile = _PROFILE_DEFINITIONS[profile_key]
    if condition is None:
        return ConditionAggregate()

    if not isinstance(condition, profile.input_type):
        raise ValueError(
            "Condition input type does not match asset category profile: "
            f"asset_category={asset_category!r}, expected={profile.input_type.__name__}, "
            f"received={type(condition).__name__}"
        )

    observed = _evaluate_groups(profile.observed_groups, condition)
    measured = _evaluate_groups(profile.measured_groups, condition)

    return ConditionAggregate(
        observed_factor=observed.factor,
        measured_factor=measured.factor,
        observed_cap=observed.cap,
        measured_cap=measured.cap,
        observed_collar=observed.collar,
        measured_collar=measured.collar,
    )


def _evaluate_groups(groups: tuple[_ConditionGroup, ...], condition: TableDrivenConditionInput) -> ConditionModifier:
    if not groups:
        return ConditionModifier(factor=1.0, cap=10.0, collar=0.5)

    group_modifiers = [_evaluate_group(group, condition) for group in groups]
    if len(group_modifiers) == 1:
        return group_modifiers[0]

    # CNAIM does not provide an additional inter-subcomponent combiner for the
    # simplified single-asset runtime path. Use conservative aggregation.
    return ConditionModifier(
        factor=max(mod.factor for mod in group_modifiers),
        cap=min(mod.cap for mod in group_modifiers),
        collar=max(mod.collar for mod in group_modifiers),
    )


def _evaluate_group(group: _ConditionGroup, condition: TableDrivenConditionInput) -> ConditionModifier:
    if not group.criteria:
        return ConditionModifier(factor=1.0, cap=10.0, collar=0.5)

    modifiers: list[ConditionModifier] = []
    for criterion in group.criteria:
        value = _value_for_criterion(condition, criterion.criterion)
        modifiers.append(_lookup_modifier(table_id=criterion.table_id, value=value))

    factors = [modifier.factor for modifier in modifiers]
    if group.mmi_config is None or len(factors) == 1:
        factor = factors[0] if len(factors) == 1 else max(factors)
    else:
        factor = mmi(
            factors=factors,
            factor_divider_1=group.mmi_config.factor_divider_1,
            factor_divider_2=group.mmi_config.factor_divider_2,
            max_no_combined_factors=group.mmi_config.max_no_combined_factors,
        )

    return ConditionModifier(
        factor=factor,
        cap=min(modifier.cap for modifier in modifiers),
        collar=max(modifier.collar for modifier in modifiers),
    )


def _value_for_criterion(condition: TableDrivenConditionInput, criterion_text: str) -> object:
    criterion_key = canonical_name(criterion_text)
    field_map = _CRITERIA_TO_FIELD_BY_TYPE[type(condition)]

    field_name = field_map.get(criterion_key)
    if field_name is None:
        raise ValueError(
            f"No field mapping for criterion {criterion_text!r} "
            f"on input {type(condition).__name__}"
        )

    return getattr(condition, field_name)


def _lookup_modifier(table_id: str, value: object) -> ConditionModifier:
    rows = load_reference_table(table_id)["rows"]
    if not rows:
        raise ValueError(f"Empty condition table: {table_id}")

    criteria_key = _criteria_column(rows[0])
    if criteria_key is not None:
        row = _find_categorical_row(rows, criteria_key, value)
        return _modifier_from_row(row, table_id)

    if _has_bounds(rows[0]):
        row = _find_bounded_row(rows, value)
        return _modifier_from_row(row, table_id)

    raise ValueError(f"Unsupported condition table schema for {table_id}")


def _criteria_column(row: Mapping[str, object]) -> str | None:
    for key in row:
        if key.startswith("condition_criteria"):
            return key
    return None


def _has_bounds(row: Mapping[str, object]) -> bool:
    return "lower" in row and "upper" in row


def _find_categorical_row(
    rows: list[dict[str, object]],
    criteria_key: str,
    value: object,
) -> dict[str, object]:
    target = canonical_name(str(value))
    default_row: dict[str, object] | None = None

    for row in rows:
        candidate_raw = row.get(criteria_key)
        if candidate_raw is None:
            continue

        candidate = canonical_name(str(candidate_raw))
        if candidate == "default":
            default_row = row
        if candidate == target:
            return row

    if default_row is not None:
        return default_row

    raise ValueError(
        f"No categorical match found for value={value!r} in criteria column {criteria_key!r}"
    )


def _find_bounded_row(rows: list[dict[str, object]], value: object) -> dict[str, object]:
    default_row: dict[str, object] | None = None
    sentinel_row: dict[str, object] | None = None

    if isinstance(value, str):
        key = canonical_name(value)
        if key == "default":
            default_row = _find_default_bound_row(rows)
            if default_row is not None:
                return default_row
        elif key == "nohistoricfaultsrecorded":
            sentinel_row = _find_sentinel_bound_row(rows, "no historic faults recorded")
            if sentinel_row is not None:
                return sentinel_row

    numeric = coerce_numeric(value)
    if numeric is not None:
        for row in rows:
            lower = row.get("lower")
            upper = row.get("upper")

            if _is_default_bound(lower, upper):
                default_row = row
                continue
            if _is_text_sentinel_bound(lower, upper):
                continue

            lower_value = coerce_numeric(lower)
            upper_value = coerce_numeric(upper)

            lower_bound = -math.inf if lower_value is None else float(lower_value)
            upper_bound = math.inf if upper_value is None else float(upper_value)

            if float(numeric) > lower_bound and float(numeric) <= upper_bound:
                return row

    if default_row is not None:
        return default_row

    default_row = _find_default_bound_row(rows)
    if default_row is not None:
        return default_row

    raise ValueError(f"No bounded match found for value={value!r}")


def _find_default_bound_row(rows: list[dict[str, object]]) -> dict[str, object] | None:
    for row in rows:
        if _is_default_bound(row.get("lower"), row.get("upper")):
            return row
    return None


def _find_sentinel_bound_row(rows: list[dict[str, object]], sentinel: str) -> dict[str, object] | None:
    sentinel_key = canonical_name(sentinel)
    for row in rows:
        lower = row.get("lower")
        upper = row.get("upper")
        if lower is None or upper is None:
            continue
        if canonical_name(str(lower)) == sentinel_key and canonical_name(str(upper)) == sentinel_key:
            return row
    return None


def _is_default_bound(lower: object, upper: object) -> bool:
    if lower is None or upper is None:
        return False
    return canonical_name(str(lower)) == "default" and canonical_name(str(upper)) == "default"


def _is_text_sentinel_bound(lower: object, upper: object) -> bool:
    if lower is None or upper is None:
        return False
    lower_key = canonical_name(str(lower))
    upper_key = canonical_name(str(upper))
    return lower_key == upper_key and lower_key not in {"default", "infinity", "-infinity"}


def _modifier_from_row(row: Mapping[str, object], table_id: str) -> ConditionModifier:
    factor = coerce_numeric(row.get("condition_input_factor"))
    cap = coerce_numeric(row.get("condition_input_cap"))
    collar = coerce_numeric(row.get("condition_input_collar"))

    if factor is None or cap is None or collar is None:
        raise ValueError(f"Invalid condition modifier row in {table_id}: {row!r}")

    return ConditionModifier(factor=float(factor), cap=float(cap), collar=float(collar))


__all__ = [
    "ConditionAggregate",
    "evaluate_table_driven_condition",
    "resolve_profile_for_asset_category",
    "supports_table_driven_condition",
]

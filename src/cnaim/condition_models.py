"""Typed condition input models for table-driven OCI/MCI derivation."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _BaseTableDrivenConditionInput(BaseModel):
    """Common base model for all table-driven family condition inputs."""

    model_config = ConfigDict(extra="forbid")


class LowVoltageConditionInput(_BaseTableDrivenConditionInput):
    """OCI/MCI inputs for LV UGB, LV board, LV pillars, and LV circuit breakers."""

    steel_cover_and_pit_condition: str = Field(default="Default")
    water_moisture: str = Field(default="Default")
    bell_condition: str = Field(default="Default")
    insulation_condition: str = Field(default="Default")
    signs_of_heating: str = Field(default="Default")
    phase_barriers: str = Field(default="Default")
    switchgear_external_condition: str = Field(default="Default")
    compound_leaks: str = Field(default="Default")
    switchgear_internal_condition_operation: str = Field(default="Default")
    operational_adequacy: str = Field(default="Default")


class SwitchgearConditionInput(_BaseTableDrivenConditionInput):
    """OCI/MCI inputs for HV, EHV, and 132kV switchgear classes."""

    switchgear_external_condition: str = Field(default="Default")
    cable_boxes_condition: str = Field(default="Default")
    oil_leaks_gas_pressure: str = Field(default="Default")
    thermographic_assessment: str = Field(default="Default")
    switchgear_internal_condition_operation: str = Field(default="Default")
    indoor_environment: str = Field(default="Default")
    support_structures: str = Field(default="Default")
    air_systems: str = Field(default="Default")

    partial_discharge_test_results: str = Field(default="Default")
    ductor_test_results: str = Field(default="Default")
    ir_test_results: str = Field(default="Default")
    oil_or_gas_test_results: str = Field(default="Default")
    temperature_readings: str = Field(default="Default")
    trip_test_results: str = Field(default="Default")


class NonSubmarineCableConditionInput(_BaseTableDrivenConditionInput):
    """OCI/MCI inputs for non-submarine cable categories."""

    crystalline_lead_presence: str = Field(default="Default")
    sheath_test_result: str = Field(default="Default")
    partial_discharge_test_result: str = Field(default="Default")
    fault_rate: float | str = Field(default="Default")
    leakage_rate: str = Field(default="Default")


class PoleConditionInput(_BaseTableDrivenConditionInput):
    """OCI/MCI inputs for LV/HV/EHV pole categories."""

    visual_pole_condition: str = Field(default="Default")
    pole_top_rot_present: str = Field(default="Default")
    pole_leaning: str = Field(default="Default")
    bird_animal_damage: str = Field(default="Default")
    pole_decay_deterioration: str = Field(default="Default")


class TowerConditionInput(_BaseTableDrivenConditionInput):
    """OCI inputs for EHV/132kV tower categories."""

    tower_legs: str = Field(default="Default")
    bracings: str = Field(default="Default")
    crossarms: str = Field(default="Default")
    peak: str = Field(default="Default")
    paintwork_condition: str = Field(default="Default")
    foundation_condition: str = Field(default="Default")


class FittingsConditionInput(_BaseTableDrivenConditionInput):
    """OCI/MCI inputs for EHV/132kV fittings categories."""

    tower_fittings_condition: str = Field(default="Default")
    conductor_fittings_condition: str = Field(default="Default")
    insulators_electrical_condition: str = Field(default="Default")
    insulators_mechanical_condition: str = Field(default="Default")
    thermal_imaging_result: str = Field(default="Default")
    ductor_test_result: str = Field(default="Default")


class TowerLineConductorConditionInput(_BaseTableDrivenConditionInput):
    """OCI/MCI inputs for EHV/132kV tower-line conductor categories."""

    visual_condition: str = Field(default="Default")
    midspan_joints: str = Field(default="Default")
    conductor_sampling_result: str = Field(default="Default")
    corrosion_monitoring_survey_result: str = Field(default="Default")


TableDrivenConditionInput = (
    LowVoltageConditionInput
    | SwitchgearConditionInput
    | NonSubmarineCableConditionInput
    | PoleConditionInput
    | TowerConditionInput
    | FittingsConditionInput
    | TowerLineConductorConditionInput
)


__all__ = [
    "FittingsConditionInput",
    "LowVoltageConditionInput",
    "NonSubmarineCableConditionInput",
    "PoleConditionInput",
    "SwitchgearConditionInput",
    "TableDrivenConditionInput",
    "TowerConditionInput",
    "TowerLineConductorConditionInput",
]

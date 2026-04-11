"""Probability of failure models for CNAIM-aligned assessments."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict, Field

from .assets import TransformerAsset
from .diagnostics import oil_test_modifier
from .enums import (
    ObservedCondition,
    PartialDischargeLevel,
    Placement,
    TemperatureReading,
)
from .health import (
    ConditionModifier,
    ageing_reduction_factor,
    beta_1,
    beta_2,
    current_health,
    health_score_excl_ehv_132kv_tf,
    initial_health,
    mmi,
    pof_cubic,
)
from .installation import Installation
from .location_factors import location_factor_column_for_asset, location_factor_from_tables
from .lookups import as_bands, load_lookup, lookup_factor_interval


class TransformerConditionInput(BaseModel):
    """Condition inputs used to derive transformer health modifiers."""

    model_config = ConfigDict(extra="forbid")

    partial_discharge: PartialDischargeLevel = PartialDischargeLevel.DEFAULT
    temperature_reading: TemperatureReading = TemperatureReading.DEFAULT
    observed_condition: ObservedCondition = ObservedCondition.DEFAULT
    moisture_ppm: float | str = "Default"
    oil_acidity_mg_koh_g: float | str = "Default"
    bd_strength_kv: float | str = "Default"


class FuturePoFPoint(BaseModel):
    """Year-wise future PoF output for a single transformer."""

    model_config = ConfigDict(extra="forbid")

    year: int = Field(ge=0)
    age: float = Field(ge=0)
    pof: float = Field(ge=0)
    future_health_score: float = Field(ge=0)


class PoFResult(BaseModel):
    """Current PoF output with optional future simulation trajectory."""

    model_config = ConfigDict(extra="forbid")

    pof: float = Field(ge=0)
    chs: float = Field(ge=0.5, le=10)
    future_points: list[FuturePoFPoint] = Field(default_factory=list)


class ProbabilityOfFailureModel(ABC):
    """Base contract for PoF model implementations."""

    @abstractmethod
    def calculate_current(
        self,
        asset: TransformerAsset,
        installation: Installation,
        condition: TransformerConditionInput | None = None,
    ) -> PoFResult:
        """Calculate the current annual probability of failure."""

    @abstractmethod
    def calculate_future(
        self,
        asset: TransformerAsset,
        installation: Installation,
        condition: TransformerConditionInput | None = None,
        simulation_end_year: int = 100,
    ) -> PoFResult:
        """Calculate current PoF and the yearly future PoF trajectory."""


class Transformer11To20kVPoFModel(ProbabilityOfFailureModel):
    """PoF model for 6.6/11kV and 20kV transformers."""

    def __init__(self) -> None:
        """Load PoF, duty, location, and condition lookup tables."""
        self._pof_params = load_lookup("transformer_11_20kv_pof_params.json")
        self._duty_cfg = load_lookup("duty_factor_transformer_11_20kv.json")
        self._condition_cfg = load_lookup("transformer_condition_lookup.json")

        self._duty_bands = as_bands(self._duty_cfg["bands"])

    def calculate_current(
        self,
        asset: TransformerAsset,
        installation: Installation,
        condition: TransformerConditionInput | None = None,
    ) -> PoFResult:
        """Compute current PoF and current health score."""
        state = self._calculate_state(asset=asset, installation=installation, condition=condition)
        return PoFResult(pof=state["current_pof"], chs=state["current_health_score"])

    def calculate_future(
        self,
        asset: TransformerAsset,
        installation: Installation,
        condition: TransformerConditionInput | None = None,
        simulation_end_year: int = 100,
    ) -> PoFResult:
        """Compute current PoF and future PoF vectors."""
        if simulation_end_year < 0:
            raise ValueError("simulation_end_year must be non-negative")

        state = self._calculate_state(asset=asset, installation=installation, condition=condition)

        b1 = state["b1"]
        b2 = beta_2(state["current_health_score"], max(state["age_years"], 1e-9))

        if b2 > 2 * b1:
            b2 = 2 * b1
        elif state["current_health_score"] == 0.5:
            b2 = b1

        reduction = ageing_reduction_factor(state["current_health_score"])

        future_points: list[FuturePoFPoint] = []
        for year in range(simulation_end_year + 1):
            future_health_score = state["current_health_score"] * math.exp((b2 / reduction) * year)

            health_for_pof = future_health_score
            if health_for_pof > 15:
                health_for_pof = 15
            elif health_for_pof < 4:
                health_for_pof = 4

            pof_year = pof_cubic(state["k_value"], state["c_value"], health_for_pof)
            future_points.append(
                FuturePoFPoint(
                    year=year,
                    age=state["age_years"] + year,
                    pof=pof_year,
                    future_health_score=future_health_score,
                )
            )

        return PoFResult(
            pof=state["current_pof"],
            chs=state["current_health_score"],
            future_points=future_points,
        )

    def _calculate_state(
        self,
        asset: TransformerAsset,
        installation: Installation,
        condition: TransformerConditionInput | None,
    ) -> dict[str, float]:
        condition_input = condition or TransformerConditionInput()
        resolved = installation.resolve_for_transformer(
            asset_category=asset.asset_category,
            sub_division=asset.sub_division,
        )

        asset_key = asset.transformer_type.value
        if asset_key not in self._pof_params:
            raise ValueError(f"Unsupported transformer type: {asset_key}")

        params = self._pof_params[asset_key]

        duty_factor = self._lookup_duty_factor(resolved.utilisation_pct)
        if installation.location_factor is not None:
            location_factor = installation.location_factor
        else:
            location_factor = self._lookup_location_factor(
                asset_category=asset.asset_category,
                sub_division=asset.sub_division,
                placement=resolved.placement,
                altitude_m=resolved.altitude_m,
                distance_from_coast_km=resolved.distance_from_coast_km,
                corrosion_category_index=resolved.corrosion_category_index,
            )

        expected_life_years = float(params["normal_expected_life_years"]) / (
            duty_factor * location_factor
        )
        b1 = beta_1(expected_life_years)
        initial_health_score = initial_health(b1, resolved.age_years)

        measured = self._measured_modifier(asset, condition_input)
        observed = self._observed_modifier(condition_input)

        health_score_factor = health_score_excl_ehv_132kv_tf(
            observed_condition_factor=observed.factor,
            measured_condition_factor=measured.factor,
        )
        health_score_cap = min(observed.cap, measured.cap)
        health_score_collar = max(observed.collar, measured.collar)

        current_health_score = current_health(
            initial_health_score=initial_health_score,
            health_score_factor=health_score_factor,
            health_score_cap=health_score_cap,
            health_score_collar=health_score_collar,
            reliability_factor=resolved.reliability_factor,
        )

        k_value = float(params["k_value_percent"]) / 100.0
        c_value = float(params["c_value"])
        current_pof = pof_cubic(k_value=k_value, c_value=c_value, health_score=current_health_score)

        return {
            "age_years": resolved.age_years,
            "b1": b1,
            "k_value": k_value,
            "c_value": c_value,
            "current_health_score": current_health_score,
            "current_pof": current_pof,
        }

    def _lookup_duty_factor(self, utilisation_pct: float) -> float:
        return lookup_factor_interval(
            value=utilisation_pct,
            bands=self._duty_bands,
            default=float(self._duty_cfg["default_duty_factor"]),
        )

    def _lookup_location_factor(
        self,
        asset_category: str | None,
        sub_division: str | None,
        placement: Placement,
        altitude_m: float,
        distance_from_coast_km: float,
        corrosion_category_index: int,
    ) -> float:
        factor_column = location_factor_column_for_asset(
            asset_category=asset_category,
            sub_division=sub_division,
        ) or "transformers"

        return location_factor_from_tables(
            factor_column=factor_column,
            placement=placement,
            altitude_m=altitude_m,
            distance_from_coast_km=distance_from_coast_km,
            corrosion_category_index=corrosion_category_index,
        )

    def _measured_modifier(
        self,
        asset: TransformerAsset,
        condition: TransformerConditionInput,
    ) -> ConditionModifier:
        measured_cfg = self._condition_cfg["measured"]
        mmi_cfg = measured_cfg["mmi"]

        partial = self._parse_modifier(
            measured_cfg["partial_discharge"][condition.partial_discharge.value]
        )
        temperature = self._parse_modifier(
            measured_cfg["temperature_reading"][condition.temperature_reading.value]
        )
        oil = oil_test_modifier(
            moisture_ppm=condition.moisture_ppm,
            acidity_mg_koh_g=condition.oil_acidity_mg_koh_g,
            bd_strength_kv=condition.bd_strength_kv,
            transformer_type_all=asset.transformer_type.value,
        )

        measured_factor = mmi(
            factors=[partial.factor, oil.factor, temperature.factor],
            factor_divider_1=float(mmi_cfg["factor_divider_1"]),
            factor_divider_2=float(mmi_cfg["factor_divider_2"]),
            max_no_combined_factors=int(mmi_cfg["max_no_combined_factors"]),
        )

        return ConditionModifier(
            factor=measured_factor,
            cap=min(partial.cap, oil.cap, temperature.cap),
            collar=max(partial.collar, oil.collar, temperature.collar),
        )

    def _observed_modifier(self, condition: TransformerConditionInput) -> ConditionModifier:
        observed_cfg = self._condition_cfg["observed"]
        mmi_cfg = observed_cfg["mmi"]

        observed = self._parse_modifier(
            observed_cfg["observed_condition"][condition.observed_condition.value]
        )
        observed_factor = mmi(
            factors=[observed.factor],
            factor_divider_1=float(mmi_cfg["factor_divider_1"]),
            factor_divider_2=float(mmi_cfg["factor_divider_2"]),
            max_no_combined_factors=int(mmi_cfg["max_no_combined_factors"]),
        )

        return ConditionModifier(
            factor=observed_factor,
            cap=observed.cap,
            collar=observed.collar,
        )

    @staticmethod
    def _parse_modifier(raw: dict[str, float]) -> ConditionModifier:
        return ConditionModifier(
            factor=float(raw["factor"]),
            cap=float(raw["cap"]),
            collar=float(raw["collar"]),
        )

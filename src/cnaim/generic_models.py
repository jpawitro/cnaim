"""Generic CNAIM PoF and CoF models covering all extracted asset subclasses.

The models in this module are driven by extracted reference tables under
`config/lookups/reference_tables`. They complement the original transformer
vertical slice with coverage for all categories currently present in
`asset_type_registry.json`.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from .assets import NetworkAsset
from .consequences import ConsequenceBreakdown
from .enums import AssetFamily, RiskLevel
from .health import (
    HEALTH_NEW_ASSET,
    ageing_reduction_factor,
    beta_1,
    beta_2,
    current_health,
    health_score_excl_ehv_132kv_tf,
    initial_health,
    pof_cubic,
)
from .installation import Installation, ResolvedInstallation
from .lookups import canonical_name, coerce_numeric, load_reference_table
from .pof import FuturePoFPoint, PoFResult


def _to_float(value: object, context: str) -> float:
    """Convert lookup values to float with explicit error context."""
    numeric = coerce_numeric(value)
    if numeric is None:
        raise ValueError(f"Expected numeric value for {context}, got {value!r}")
    return numeric


@dataclass(frozen=True)
class _PoFCurve:
    """Parameters of the CNAIM exponential PoF approximation."""

    k_value: float
    c_value: float
    health_score_limit: float


class AssetConditionInput(BaseModel):
    """Generic condition modifiers for table-driven PoF across all families.

    Formula mapping:
    - combined condition factor uses `health_score_excl_ehv_132kv_tf`
    - final CHS uses `current_health`

    The defaults (all factors=1) represent "no condition adjustment".
    """

    model_config = ConfigDict(extra="forbid")

    observed_condition_factor: float = Field(default=1.0, gt=0)
    measured_condition_factor: float = Field(default=1.0, gt=0)
    observed_condition_cap: float = Field(default=10.0, ge=0.5)
    measured_condition_cap: float = Field(default=10.0, ge=0.5)
    observed_condition_collar: float = Field(default=0.5, ge=0)
    measured_condition_collar: float = Field(default=0.5, ge=0)


class CNAIMPoFModel:
    r"""Table-driven PoF model for all available asset classes/subclasses.

    Reference tables used:
    - `categorisation_of_assets`
    - `generic_terms_for_assets`
    - `pof_curve_parameters`
    - `normal_expected_life`
    - `duty_factor_lut_distrib_tf`
    - `duty_factor_lut_grid_prim_tf`
    - `duty_factor_lut_switchgear`
    - `duty_factor_lut_cables_df1`
    - `duty_factor_lut_cables_df2`

    Core equations:
    - $\beta_1 = \ln(5.5 / 0.5) / \text{ExpectedLife}$
    - $HI_{initial} = 0.5 \cdot e^{\beta_1 \cdot age}$ (capped at 5.5)
        - $PoF = K \cdot \left(1 + C\,HI + \frac{(C\,HI)^2}{2!} +
            \frac{(C\,HI)^3}{3!}\right)$
    """

    def __init__(self) -> None:
        """Load all PoF reference tables and pre-index frequently used mappings."""
        categorisation = load_reference_table("categorisation_of_assets")
        generic_terms = load_reference_table("generic_terms_for_assets")
        pof_curve = load_reference_table("pof_curve_parameters")
        expected_life = load_reference_table("normal_expected_life")

        self._category_to_health = {
            str(row["asset_register_category"]): str(row["health_index_asset_category"])
            for row in categorisation["rows"]
        }

        self._health_to_generic: dict[str, tuple[str | None, str | None]] = {
            str(row["health_index_asset_category"]): (
                row.get("generic_term"),
                row.get("generic_term_1"),
            )
            for row in generic_terms["rows"]
        }

        self._pof_curves = {
            str(row["functional_failure_category"]): _PoFCurve(
                k_value=_to_float(row["k_value_pct"], "pof_curve.k_value") / 100.0,
                c_value=_to_float(row["c_value"], "pof_curve.c_value"),
                health_score_limit=_to_float(
                    row["health_score_limit"],
                    "pof_curve.health_score_limit",
                ),
            )
            for row in pof_curve["rows"]
        }

        self._expected_life_by_category: dict[str, list[dict[str, object]]] = defaultdict(list)
        for row in expected_life["rows"]:
            key = canonical_name(str(row["asset_register_category"]))
            self._expected_life_by_category[key].append(row)

        self._duty_switchgear = load_reference_table("duty_factor_lut_switchgear")["rows"]
        self._duty_tf_distribution = load_reference_table("duty_factor_lut_distrib_tf")["rows"]
        self._duty_tf_grid_primary = load_reference_table("duty_factor_lut_grid_prim_tf")["rows"]
        self._duty_cable_df1 = load_reference_table("duty_factor_lut_cables_df1")["rows"]
        self._duty_cable_df2 = load_reference_table("duty_factor_lut_cables_df2")["rows"]

    def calculate_current(
        self,
        asset: NetworkAsset,
        installation: Installation,
        condition: AssetConditionInput | None = None,
    ) -> PoFResult:
        """Calculate current annual probability of failure for any asset.

        The resolved asset category drives all table lookups and defaults.
        """
        state = self._calculate_state(asset, installation, condition)
        return PoFResult(
            pof=state["current_pof"],
            chs=state["current_health_score"],
        )

    def calculate_future(
        self,
        asset: NetworkAsset,
        installation: Installation,
        condition: AssetConditionInput | None = None,
        simulation_end_year: int = 100,
    ) -> PoFResult:
        """Calculate current PoF and future PoF trajectory per year."""
        if simulation_end_year < 0:
            raise ValueError("simulation_end_year must be non-negative")

        state = self._calculate_state(asset, installation, condition)
        b1 = state["b1"]
        current_chs = state["current_health_score"]

        b2 = beta_2(current_chs, max(state["age_years"], 1e-9))
        if b2 > 2 * b1:
            b2 = 2 * b1
        elif current_chs == HEALTH_NEW_ASSET:
            b2 = b1

        reduction = ageing_reduction_factor(current_chs)

        future_points: list[FuturePoFPoint] = []
        for year in range(simulation_end_year + 1):
            future_health_score = current_chs * math.exp((b2 / reduction) * year)
            health_for_pof = min(15.0, future_health_score)
            health_for_pof = max(state["health_score_limit"], health_for_pof)

            pof_year = pof_cubic(
                state["k_value"],
                state["c_value"],
                health_for_pof,
            )
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
            chs=current_chs,
            future_points=future_points,
        )

    def _calculate_state(
        self,
        asset: NetworkAsset,
        installation: Installation,
        condition: AssetConditionInput | None,
    ) -> dict[str, float]:
        if asset.asset_category is None:
            raise ValueError("asset.asset_category must be provided")

        resolved_installation = installation.resolve_generic()
        condition_input = condition or AssetConditionInput()

        expected_life_years = self._resolve_expected_life_years(
            asset.asset_category,
            asset.sub_division,
        )
        health_category = self._resolve_health_category(asset.asset_category)
        duty_factor = self._resolve_duty_factor(
            asset,
            health_category,
            resolved_installation,
        )

        adjusted_expected_life = expected_life_years / (
            duty_factor * resolved_installation.location_factor
        )
        b1 = beta_1(adjusted_expected_life)

        initial_health_score = initial_health(b1, resolved_installation.age_years)

        health_score_factor = health_score_excl_ehv_132kv_tf(
            observed_condition_factor=condition_input.observed_condition_factor,
            measured_condition_factor=condition_input.measured_condition_factor,
        )
        health_score_cap = min(
            condition_input.observed_condition_cap,
            condition_input.measured_condition_cap,
        )
        health_score_collar = max(
            condition_input.observed_condition_collar,
            condition_input.measured_condition_collar,
        )

        current_health_score = current_health(
            initial_health_score=initial_health_score,
            health_score_factor=health_score_factor,
            health_score_cap=health_score_cap,
            health_score_collar=health_score_collar,
            reliability_factor=resolved_installation.reliability_factor,
        )

        curve = self._resolve_pof_curve(
            asset_category=asset.asset_category,
            health_category=health_category,
        )

        current_pof = pof_cubic(
            k_value=curve.k_value,
            c_value=curve.c_value,
            health_score=current_health_score,
        )

        return {
            "age_years": resolved_installation.age_years,
            "b1": b1,
            "k_value": curve.k_value,
            "c_value": curve.c_value,
            "health_score_limit": curve.health_score_limit,
            "current_health_score": current_health_score,
            "current_pof": current_pof,
        }

    def _resolve_health_category(self, asset_category: str) -> str:
        try:
            return self._category_to_health[asset_category]
        except KeyError as exc:
            raise ValueError(f"Unsupported asset category: {asset_category}") from exc

    def _resolve_expected_life_years(
        self,
        asset_category: str,
        sub_division: str | None,
    ) -> float:
        rows = self._expected_life_by_category.get(canonical_name(asset_category))
        if not rows:
            raise ValueError(f"No normal expected life found for asset category: {asset_category}")

        if sub_division is not None:
            subdivision_key = canonical_name(sub_division)
            for row in rows:
                value = row.get("sub_division")
                if value and canonical_name(str(value)) == subdivision_key:
                    return _to_float(
                        row["normal_expected_life"],
                        "normal_expected_life.value",
                    )

        for row in rows:
            if row.get("sub_division") is None:
                return _to_float(
                    row["normal_expected_life"],
                    "normal_expected_life.value",
                )

        return _to_float(
            rows[0]["normal_expected_life"],
            "normal_expected_life.value",
        )

    def _resolve_pof_curve(
        self,
        asset_category: str,
        health_category: str,
    ) -> _PoFCurve:
        functional_category = self._resolve_functional_failure_category(
            asset_category=asset_category,
            health_category=health_category,
        )

        curve = self._pof_curves.get(functional_category)
        if curve is None:
            raise ValueError(
                f"No PoF curve parameters found for functional category: {functional_category}"
            )
        return curve

    def _resolve_functional_failure_category(
        self,
        asset_category: str,
        health_category: str,
    ) -> str:
        if asset_category in self._pof_curves:
            return asset_category
        if health_category in self._pof_curves:
            return health_category

        generic_term, generic_term_1 = self._health_to_generic.get(
            health_category,
            (None, None),
        )

        if health_category == "HV Switchgear (GM) - Distribution":
            return "HV Switchgear (GM) - Distribution (GM)"

        if health_category == "EHV Switchgear (GM)":
            if "66kv" in canonical_name(asset_category):
                return "EHV Switchgear (GM) (66kV assets only)"
            return "EHV Switchgear (GM) (33kV & 22kV assets only)"

        if health_category in {"EHV Transformer", "132kV Transformer"}:
            return "EHV Transformer/ 132kV Transformer"

        if health_category == "132kV OHL Support - Tower":
            return "Towers"

        if health_category == "LV Switchgear and Other":
            if asset_category == "LV Board (X-type Network) (WM)":
                return "LV Board (WM)"
            if asset_category in {
                "LV Pillar (OD at Substation)",
                "LV Pillar (OD not at a Substation)",
            }:
                return "LV Pillar (OD at Substation) / LV Pillar (OD not at a Substation)"

        if generic_term == "Overhead Line" and generic_term_1 is not None:
            return generic_term_1

        if generic_term == "Cable":
            if generic_term_1 == "Submarine Cables":
                return "Submarine Cables"
            if generic_term_1 == "Non Pressurised Cable":
                return "Non Pressurised Cable"
            if generic_term_1 == "Pressurised Cable":
                if "gas" in canonical_name(health_category):
                    return "Pressurised Cable (EHV UG Cable (Gas) and 132kV UG Cable (Gas))"
                return "Pressurised Cable (EHV UG Cable (Oil) and 132kV UG Cable (Oil))"

        if generic_term == "Transformers":
            if generic_term_1 == "HV Transformer":
                return "HV Transformer (GM)"
            if generic_term_1 and "gridprimaryorehv132kvtransformers" in canonical_name(
                generic_term_1
            ):
                return "EHV Transformer/ 132kV Transformer"

        raise ValueError(
            "Unable to map functional failure category for asset category "
            f"{asset_category} (health category: {health_category})"
        )

    def _resolve_duty_factor(
        self,
        asset: NetworkAsset,
        health_category: str,
        installation: ResolvedInstallation,
    ) -> float:
        if asset.family == AssetFamily.TRANSFORMER:
            if health_category == "HV Transformer (GM)":
                return self._banded_factor(
                    rows=self._duty_tf_distribution,
                    value=installation.utilisation_pct,
                    factor_key="duty_factor",
                    default=1.0,
                )

            if health_category in {"EHV Transformer", "132kV Transformer"}:
                transformer_factor = self._banded_factor(
                    rows=self._duty_tf_grid_primary,
                    value=installation.utilisation_pct,
                    factor_key="duty_factor",
                    default=1.0,
                    bound_description_contains="Transformer",
                )
                tap_factor = self._banded_factor(
                    rows=self._duty_tf_grid_primary,
                    value=installation.tap_operations_per_day,
                    factor_key="duty_factor",
                    default=1.0,
                    bound_description_contains="TapChanger",
                )
                return transformer_factor * tap_factor

        if asset.family in {AssetFamily.SWITCHGEAR, AssetFamily.LOW_VOLTAGE}:
            target = "Normal/Low"
            if installation.switchgear_duty_profile.value == "High":
                target = "High"

            for row in self._duty_switchgear:
                number_of_operations = str(row.get("number_of_operations", ""))
                if target == "High" and number_of_operations.startswith("High"):
                    return _to_float(row["duty_factor"], "switchgear.duty_factor")
                if target == "Normal/Low" and number_of_operations == target:
                    return _to_float(row["duty_factor"], "switchgear.duty_factor")

            return self._default_factor(self._duty_switchgear, "duty_factor", 1.0)

        if asset.family == AssetFamily.CABLE:
            column = "duty_factor_hv"
            if "ehv" in canonical_name(health_category) or "132kv" in canonical_name(
                health_category
            ):
                column = "duty_factor_ehv_132kv"

            df1 = self._banded_factor(
                rows=self._duty_cable_df1,
                value=installation.utilisation_pct,
                factor_key=column,
                default=1.0,
            )
            df2 = self._banded_factor(
                rows=self._duty_cable_df2,
                value=installation.operating_voltage_pct,
                factor_key="duty_factor",
                default=1.0,
            )
            return df1 * df2

        return 1.0

    @staticmethod
    def _default_factor(
        rows: list[dict[str, object]],
        factor_key: str,
        fallback: float,
    ) -> float:
        for row in rows:
            lower = str(row.get("lower", "")).lower()
            upper = str(row.get("upper", "")).lower()
            if lower == "default" and upper == "default":
                return _to_float(row[factor_key], f"default.{factor_key}")
        return fallback

    @staticmethod
    def _banded_factor(
        rows: list[dict[str, object]],
        value: float,
        factor_key: str,
        default: float,
        bound_description_contains: str | None = None,
    ) -> float:
        default_factor = default

        for row in rows:
            description = str(row.get("bound_description", ""))
            if (
                bound_description_contains is not None
                and bound_description_contains.lower() not in description.lower()
            ):
                continue

            lower = row.get("lower")
            upper = row.get("upper")
            if str(lower).lower() == "default" and str(upper).lower() == "default":
                default_factor = _to_float(row[factor_key], f"default.{factor_key}")
                continue

            lower_value = coerce_numeric(lower)
            upper_value = coerce_numeric(upper)

            lower_bound = -math.inf if lower_value is None else lower_value
            upper_bound = math.inf if upper_value is None else upper_value

            if value > lower_bound and value <= upper_bound:
                return _to_float(row[factor_key], f"band.{factor_key}")

        return default_factor


class CNAIMConsequenceModel:
    r"""Table-driven CoF model for all available asset classes/subclasses.

    Reference tables used:
    - `reference_costs_of_failure`
    - `categorisation_of_assets`
    - `type_financial_factors`
    - `access_factor_swg_tf_asset`
    - `access_factor_ohl`
    - `safety_conseq_factor_sg_tf_oh`
    - `safety_conseq_factor_cable`
    - `safety_risk_reduction_factor`
    - `size_enviromental_factor`
    - `location_environ_al_factor`
    - `ref_nw_perf_cost_fail_lv_hv`
    - `customer_no_adjust_lv_hv_asset`

    Component equations:
    - Financial: $F = F_{ref} \cdot f_{type} \cdot f_{access}$
    - Safety: $S = S_{ref} \cdot f_{safety} \cdot f_{reduction}$
        - Environmental: $E = E_{ref} \cdot f_{size} \cdot f_{proximity}
            \cdot f_{bunding}$
    - Network: $N = N_{ref} \cdot f_{customer}$
    """

    def __init__(self) -> None:
        """Load all CoF reference tables and build category-oriented caches."""
        categorisation = load_reference_table("categorisation_of_assets")
        reference_costs = load_reference_table("reference_costs_of_failure")
        type_financial = load_reference_table("type_financial_factors")

        self._category_to_health = {
            str(row["asset_register_category"]): str(row["health_index_asset_category"])
            for row in categorisation["rows"]
        }

        self._reference_costs: dict[str, dict[str, object]] = {
            canonical_name(str(row["asset_register_category"])): row
            for row in reference_costs["rows"]
        }

        self._type_financial_by_category: dict[str, list[dict[str, object]]] = defaultdict(list)
        for row in type_financial["rows"]:
            category = row.get("asset_register_category")
            if category:
                self._type_financial_by_category[canonical_name(str(category))].append(row)

        self._access_switchgear_transformer = {
            canonical_name(str(row["asset_category"])): row
            for row in load_reference_table("access_factor_swg_tf_asset")["rows"]
        }
        self._access_overhead = {
            canonical_name(str(row["asset_category"])): row
            for row in load_reference_table("access_factor_ohl")["rows"]
        }

        self._safety_matrix_rows = load_reference_table("safety_conseq_factor_sg_tf_oh")["rows"]
        self._safety_cable_rows = load_reference_table("safety_conseq_factor_cable")["rows"]
        self._safety_reduction_rows = load_reference_table("safety_risk_reduction_factor")["rows"]

        self._size_environmental_by_category: dict[str, list[dict[str, object]]] = defaultdict(list)
        for row in load_reference_table("size_enviromental_factor")["rows"]:
            category = row.get("asset_register_category")
            if category:
                self._size_environmental_by_category[canonical_name(str(category))].append(row)

        self._location_environment = {
            canonical_name(str(row["asset_register_category"])): row
            for row in load_reference_table("location_environ_al_factor")["rows"]
        }

        self._network_reference_customers = {
            canonical_name(str(row["asset_category"])): row
            for row in load_reference_table("ref_nw_perf_cost_fail_lv_hv")["rows"]
        }
        self._network_customer_adjustments = load_reference_table("customer_no_adjust_lv_hv_asset")[
            "rows"
        ]

    def calculate(self, asset: NetworkAsset) -> ConsequenceBreakdown:
        """Calculate financial/safety/environmental/network CoF components."""
        if asset.asset_category is None:
            raise ValueError("asset.asset_category must be provided")

        health_category = self._resolve_health_category(asset.asset_category)
        reference = self._resolve_reference_costs(asset.asset_category)

        financial = self._financial_component(asset, health_category, reference)
        safety = self._safety_component(asset, health_category, reference)
        environmental = self._environmental_component(
            asset,
            health_category,
            reference,
        )
        network = self._network_component(asset, health_category, reference)

        reference_total = _to_float(reference["total_gbp"], "reference.total")

        return ConsequenceBreakdown(
            financial=financial,
            safety=safety,
            environmental=environmental,
            network_performance=network,
            reference_total_cost=reference_total,
        )

    def _resolve_health_category(self, asset_category: str) -> str:
        try:
            return self._category_to_health[asset_category]
        except KeyError as exc:
            raise ValueError(f"Unsupported asset category: {asset_category}") from exc

    def _resolve_reference_costs(self, asset_category: str) -> dict[str, object]:
        key = canonical_name(asset_category)
        row = self._reference_costs.get(key)
        if row is None:
            raise ValueError(f"No reference costs found for asset category: {asset_category}")
        return row

    def _financial_component(
        self,
        asset: NetworkAsset,
        health_category: str,
        reference: dict[str, object],
    ) -> float:
        base = _to_float(reference["financial_gbp"], "reference.financial_gbp")
        type_factor = self._type_financial_factor(asset, health_category)
        access_factor = self._access_factor(asset, health_category)
        return base * type_factor * access_factor

    def _type_financial_factor(
        self,
        asset: NetworkAsset,
        health_category: str,
    ) -> float:
        if asset.asset_category is None:
            return 1.0

        rows = self._type_financial_by_category.get(
            canonical_name(asset.asset_category),
            [],
        )
        if not rows:
            rows = self._type_financial_by_category.get(
                canonical_name(health_category),
                [],
            )
        if not rows:
            return 1.0

        if asset.rated_capacity_kva is not None:
            for row in rows:
                lower = coerce_numeric(row.get("lower"))
                upper = coerce_numeric(row.get("upper"))
                lower_bound = -math.inf if lower is None else lower
                upper_bound = math.inf if upper is None else upper
                if (
                    asset.rated_capacity_kva > lower_bound
                    and asset.rated_capacity_kva <= upper_bound
                ):
                    return _to_float(
                        row["type_financial_factor"],
                        "financial.type_factor",
                    )

        if asset.sub_division is not None:
            target = canonical_name(asset.sub_division)
            for row in rows:
                criteria = row.get("type_financial_factor_criteria")
                if criteria and canonical_name(str(criteria)) == target:
                    return _to_float(
                        row["type_financial_factor"],
                        "financial.type_factor",
                    )

        return _to_float(rows[0]["type_financial_factor"], "financial.type_factor")

    def _access_factor(self, asset: NetworkAsset, health_category: str) -> float:
        health_key = canonical_name(health_category)

        if health_key in self._access_switchgear_transformer:
            row = self._access_switchgear_transformer[health_key]
            column = {
                "Type A": ("access_factor_type_a_criteria_normal_access_default_value"),
                "Type B": (
                    "access_factor_type_b_criteria_constrained_access_or_confined_working_space"
                ),
                "Type C": ("access_factor_type_c_criteria_underground_substation"),
            }[asset.access_type.value]
            value = row.get(column)
            if value is not None:
                return _to_float(value, "financial.access_factor")

        if health_key in self._access_overhead:
            row = self._access_overhead[health_key]
            if asset.overhead_access_type.value == "Type B":
                value = row.get(
                    "access_factor_type_b_criteria_major_crossing_"
                    "e_g_associated_span_crosses_railway_line_major_road_large_waterway_etc"
                )
                if value is not None:
                    return _to_float(value, "financial.access_factor_ohl")

            value = row.get("access_factor_type_a_criteria_normal_access_default_value")
            if value is not None:
                return _to_float(value, "financial.access_factor_ohl")

        return 1.0

    def _safety_component(
        self,
        asset: NetworkAsset,
        health_category: str,
        reference: dict[str, object],
    ) -> float:
        base = _to_float(reference["safety_gbp"], "reference.safety_gbp")

        if asset.family == AssetFamily.CABLE:
            cable_row = self._safety_cable_rows[0]
            if canonical_name(asset.cable_layout.value).startswith("exposed"):
                cable_row = self._safety_cable_rows[1]
            safety_factor = _to_float(
                cable_row["safety_consequence_factor"],
                "safety.cable_factor",
            )
        else:
            safety_factor = self._safety_matrix_factor(
                location_risk=asset.location_risk,
                type_risk=asset.type_risk,
            )

        reduction_factor = self._safety_reduction_factor(asset, health_category)
        return base * safety_factor * reduction_factor

    def _safety_matrix_factor(
        self,
        location_risk: RiskLevel,
        type_risk: RiskLevel,
    ) -> float:
        target_location = location_risk.value.lower()
        target_type_column = {
            RiskLevel.LOW: "type_risk_rating_low",
            RiskLevel.MEDIUM: "type_risk_rating_medium_default",
            RiskLevel.HIGH: "type_risk_rating_high",
        }[type_risk]

        for row in self._safety_matrix_rows:
            location_label = str(
                row["safety_consequence_factor_switchgear_transformers_overhead_lines_1"]
            ).lower()
            if target_location == "medium" and location_label.startswith("medium"):
                return _to_float(row[target_type_column], "safety.matrix_factor")
            if target_location in location_label:
                return _to_float(row[target_type_column], "safety.matrix_factor")

        return 1.0

    def _safety_reduction_factor(
        self,
        asset: NetworkAsset,
        health_category: str,
    ) -> float:
        if health_category == "LV UGB" and asset.safety_blanket:
            for row in self._safety_reduction_rows:
                description = str(row.get("safety_risk_reduction_factor", ""))
                if "with safety blanket" in description.lower():
                    return _to_float(row["unnamed_1"], "safety.reduction")

        for row in self._safety_reduction_rows:
            description = str(row.get("safety_risk_reduction_factor", ""))
            if "all other assets" in description.lower():
                return _to_float(row["unnamed_1"], "safety.reduction")

        return 1.0

    def _environmental_component(
        self,
        asset: NetworkAsset,
        health_category: str,
        reference: dict[str, object],
    ) -> float:
        base = _to_float(
            reference["environmental_gbp"],
            "reference.environmental_gbp",
        )

        size_factor = self._size_environment_factor(asset, health_category)
        proximity_factor, bunding_factor = self._location_environment_factors(
            asset,
            health_category,
        )

        return base * size_factor * proximity_factor * bunding_factor

    def _size_environment_factor(
        self,
        asset: NetworkAsset,
        health_category: str,
    ) -> float:
        if asset.asset_category is None:
            return 1.0

        candidates = [
            canonical_name(asset.asset_category),
            canonical_name(health_category),
        ]
        if health_category == "132kV CBs":
            candidates.append(canonical_name("132kV Switchgear"))

        rows: list[dict[str, object]] = []
        for candidate in candidates:
            rows = self._size_environmental_by_category.get(candidate, [])
            if rows:
                break

        if not rows:
            return 1.0

        if asset.rated_capacity_kva is None:
            for row in rows:
                lower = coerce_numeric(row.get("lower"))
                upper = coerce_numeric(row.get("upper"))
                if lower is None and upper is None:
                    return _to_float(
                        row["size_environmental_factor"],
                        "environment.size_factor",
                    )
            return _to_float(
                rows[0]["size_environmental_factor"],
                "environment.size_factor",
            )

        for row in rows:
            lower = coerce_numeric(row.get("lower"))
            upper = coerce_numeric(row.get("upper"))
            lower_bound = -math.inf if lower is None else lower
            upper_bound = math.inf if upper is None else upper
            if asset.rated_capacity_kva > lower_bound and asset.rated_capacity_kva <= upper_bound:
                return _to_float(
                    row["size_environmental_factor"],
                    "environment.size_factor",
                )

        return _to_float(
            rows[-1]["size_environmental_factor"],
            "environment.size_factor",
        )

    def _location_environment_factors(
        self,
        asset: NetworkAsset,
        health_category: str,
    ) -> tuple[float, float]:
        if asset.asset_category is None:
            return (1.0, 1.0)

        candidates = [
            canonical_name(asset.asset_category),
            canonical_name(health_category),
        ]
        row: dict[str, object] | None = None
        for candidate in candidates:
            row = self._location_environment.get(candidate)
            if row is not None:
                break

        if row is None:
            return (1.0, 1.0)

        proximity = asset.proximity_to_water_m
        if proximity is None:
            proximity_column = "proximity_factor_not_close_to_water_course_120m_or_no_oil"
        elif proximity <= 40:
            proximity_column = "proximity_factor_very_close_to_water_course_40m"
        elif proximity <= 80:
            proximity_column = "proximity_factor_close_to_water_course_between_40m_and_80m"
        elif proximity <= 120:
            proximity_column = (
                "proximity_factor_moderately_close_to_water_course_between_80m_and_120m"
            )
        else:
            proximity_column = "proximity_factor_not_close_to_water_course_120m_or_no_oil"

        bunding_column = "bunding_factor_not_bunded"
        if asset.bunded:
            bunding_column = "bunding_factor_bunded"

        proximity_factor = _to_float(
            row.get(proximity_column, 1.0),
            "environment.proximity_factor",
        )
        bunding_factor = _to_float(
            row.get(bunding_column, 1.0),
            "environment.bunding_factor",
        )
        return (proximity_factor, bunding_factor)

    def _network_component(
        self,
        asset: NetworkAsset,
        health_category: str,
        reference: dict[str, object],
    ) -> float:
        base = _to_float(
            reference["network_performance_gbp"],
            "reference.network_performance_gbp",
        )

        if asset.no_customers <= 0:
            return base

        reference_customers = self._reference_customer_count(asset, health_category)
        if reference_customers is None or reference_customers <= 0:
            return base

        customer_multiplier = self._customer_adjust_multiplier(asset.kva_per_customer)
        customer_factor = (customer_multiplier * float(asset.no_customers)) / reference_customers
        return base * customer_factor

    def _reference_customer_count(
        self,
        asset: NetworkAsset,
        health_category: str,
    ) -> float | None:
        if asset.asset_category is None:
            return None

        keys = [
            canonical_name(asset.asset_category),
            canonical_name(health_category),
        ]
        if asset.asset_category.startswith("LV Pillar"):
            keys.append(canonical_name("LV Pillar"))

        for key in keys:
            row = self._network_reference_customers.get(key)
            if row is None:
                continue

            value = row.get("reference_number_of_connected_customers")
            if value is None:
                continue

            numeric = coerce_numeric(value)
            if numeric is not None:
                return numeric

        return None

    def _customer_adjust_multiplier(self, kva_per_customer: float | None) -> float:
        if kva_per_customer is None:
            return 1.0

        default_multiplier = 1.0
        for row in self._network_customer_adjustments:
            lower = row.get("lower")
            upper = row.get("upper")

            if str(lower).lower() == "default" and str(upper).lower() == "default":
                parsed = self._extract_multiplier(
                    str(row["no_of_customers_to_be_used_in_the_derivation_of_customer_factor"])
                )
                default_multiplier = parsed
                continue

            lower_value = coerce_numeric(lower)
            upper_value = coerce_numeric(upper)
            lower_bound = -math.inf if lower_value is None else lower_value
            upper_bound = math.inf if upper_value is None else upper_value

            if kva_per_customer > lower_bound and kva_per_customer <= upper_bound:
                expression = str(
                    row["no_of_customers_to_be_used_in_the_derivation_of_customer_factor"]
                )
                return self._extract_multiplier(expression)

        return default_multiplier

    @staticmethod
    def _extract_multiplier(expression: str) -> float:
        match = re.match(r"\s*([0-9]+(?:\.[0-9]+)?)\s*x", expression, re.I)
        if match is None:
            return 1.0
        return float(match.group(1))

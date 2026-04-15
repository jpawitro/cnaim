"""Risk profile model that combines PoF and consequence outputs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache

from pydantic import BaseModel, ConfigDict, Field

from .consequences import ConsequenceBreakdown
from .lookups import canonical_name, coerce_numeric, load_lookup, load_reference_table
from .pof import PoFResult


@dataclass(frozen=True)
class _RiskWeightTables:
    """In-memory lookup structure for risk matrix weighting tables 236-241."""

    typical_cof_weight: dict[str, dict[str, float]]
    typical_in_year_pof_weight: dict[str, dict[str, float]]
    in_year_monetised_risk: dict[str, dict[str, dict[str, float]]]
    forecast_ageing_rate: dict[str, float]
    cumulative_discounted_pof_weight: dict[str, dict[str, float]]
    long_term_risk_index: dict[str, dict[str, dict[str, float]]]


def _category_key(category: str) -> str:
    """Return canonical category key while removing extracted Excel control markers."""
    cleaned = category.replace("_x000D_", " ")
    cleaned = cleaned.replace("\r", " ").replace("\n", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return canonical_name(cleaned)


@cache
def _risk_weight_tables() -> _RiskWeightTables:
    """Load and normalize risk weighting tables 236-241 for fast lookups."""
    table_236 = load_reference_table("typ_cof_weight_risk_matrices")["rows"]
    table_237 = load_reference_table("typ_pof_weight_risk_matrices")["rows"]
    table_238 = load_reference_table("risk_matrix_weight")["rows"]
    table_239 = load_reference_table("typ_forecast_age_rates")["rows"]
    table_240 = load_reference_table("typ_cum_dis_pof_weight_health")["rows"]
    table_241 = load_reference_table("risk_matrix_weight_long_term")["rows"]

    typical_cof_weight: dict[str, dict[str, float]] = {}
    for row in table_236:
        category = row.get("asset_register_category")
        if not category:
            continue
        category_key = _category_key(str(category))
        typical_cof_weight[category_key] = {
            "C1": float(row["c1_typical_cof_weightings_for_each_criticality_index_band_gbp_at_20_21_prices"]),
            "C2": float(row["c2_typical_cof_weightings_for_each_criticality_index_band_gbp_at_20_21_prices"]),
            "C3": float(row["c3_typical_cof_weightings_for_each_criticality_index_band_gbp_at_20_21_prices"]),
            "C4": float(row["c4_typical_cof_weightings_for_each_criticality_index_band_gbp_at_20_21_prices"]),
        }

    typical_in_year_pof_weight: dict[str, dict[str, float]] = {}
    for row in table_237:
        category = row.get("asset_register_category")
        if not category:
            continue
        category_key = _category_key(str(category))
        typical_in_year_pof_weight[category_key] = {
            "HI1": float(row["h1_typical_in_year_pof_weightings_for_each_health_index_band"]),
            "HI2": float(row["h2_typical_in_year_pof_weightings_for_each_health_index_band"]),
            "HI3": float(row["h3_typical_in_year_pof_weightings_for_each_health_index_band"]),
            "HI4": float(row["h4_typical_in_year_pof_weightings_for_each_health_index_band"]),
            "HI5": float(row["h5_typical_in_year_pof_weightings_for_each_health_index_band"]),
        }

    in_year_monetised_risk: dict[str, dict[str, dict[str, float]]] = {}
    for row in table_238:
        category = row.get("asset_register_category")
        ci_band = row.get("criticality_index_band")
        if not category or not ci_band:
            continue

        category_key = _category_key(str(category))
        bucket = in_year_monetised_risk.setdefault(category_key, {})
        bucket[str(ci_band)] = {
            "HI1": float(row["h1_in_year_monetised_risk_weighting_gbp_at_2020_21_prices_for_each_health_index_band"]),
            "HI2": float(row["h2_in_year_monetised_risk_weighting_gbp_at_2020_21_prices_for_each_health_index_band"]),
            "HI3": float(row["h3_in_year_monetised_risk_weighting_gbp_at_2020_21_prices_for_each_health_index_band"]),
            "HI4": float(row["h4_in_year_monetised_risk_weighting_gbp_at_2020_21_prices_for_each_health_index_band"]),
            "HI5": float(row["h5_in_year_monetised_risk_weighting_gbp_at_2020_21_prices_for_each_health_index_band"]),
        }

    forecast_ageing_rate: dict[str, float] = {}
    for row in table_239:
        category = row.get("asset_register_category")
        rate = coerce_numeric(row.get("forecast_ageing_rate"))
        if not category or rate is None:
            continue
        forecast_ageing_rate[_category_key(str(category))] = float(rate)

    cumulative_discounted_pof_weight: dict[str, dict[str, float]] = {}
    for row in table_240:
        category = row.get("asset_register_category")
        if not category:
            continue
        category_key = _category_key(str(category))
        cumulative_discounted_pof_weight[category_key] = {
            "HI1": float(row["hi1_typical_cumulative_discounted_pof_weightings_for_each_health_index_band"]),
            "HI2": float(row["hi2_typical_cumulative_discounted_pof_weightings_for_each_health_index_band"]),
            "HI3": float(row["hi3_typical_cumulative_discounted_pof_weightings_for_each_health_index_band"]),
            "HI4": float(row["hi4_typical_cumulative_discounted_pof_weightings_for_each_health_index_band"]),
            "HI5": float(row["hi5_typical_cumulative_discounted_pof_weightings_for_each_health_index_band"]),
        }

    long_term_risk_index: dict[str, dict[str, dict[str, float]]] = {}
    for row in table_241:
        category = row.get("asset_register_category")
        ci_band = row.get("criticality_index_band")
        if not category or not ci_band:
            continue

        category_key = _category_key(str(category))
        bucket = long_term_risk_index.setdefault(category_key, {})
        bucket[str(ci_band)] = {
            "HI1": float(row["hi1_risk_index_or_monetised_long_term_risk_weighting_gbp_at_20_21_prices_for_each_health_index_band"]),
            "HI2": float(row["hi2_risk_index_or_monetised_long_term_risk_weighting_gbp_at_20_21_prices_for_each_health_index_band"]),
            "HI3": float(row["hi3_risk_index_or_monetised_long_term_risk_weighting_gbp_at_20_21_prices_for_each_health_index_band"]),
            "HI4": float(row["hi4_risk_index_or_monetised_long_term_risk_weighting_gbp_at_20_21_prices_for_each_health_index_band"]),
            "HI5": float(row["hi5_risk_index_or_monetised_long_term_risk_weighting_gbp_at_20_21_prices_for_each_health_index_band"]),
        }

    return _RiskWeightTables(
        typical_cof_weight=typical_cof_weight,
        typical_in_year_pof_weight=typical_in_year_pof_weight,
        in_year_monetised_risk=in_year_monetised_risk,
        forecast_ageing_rate=forecast_ageing_rate,
        cumulative_discounted_pof_weight=cumulative_discounted_pof_weight,
        long_term_risk_index=long_term_risk_index,
    )


class RiskProfile(BaseModel):
    """Final risk profile result returned by the CNAIM domain model."""

    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(min_length=1)
    pof: float = Field(ge=0)
    chs: float = Field(ge=0.5)
    financial_cof: float = Field(ge=0)
    safety_cof: float = Field(ge=0)
    environmental_cof: float = Field(ge=0)
    network_performance_cof: float = Field(ge=0)
    total_cof: float = Field(ge=0)
    monetary_risk: float = Field(ge=0)
    risk_matrix_x: float = Field(ge=0, le=100)
    risk_matrix_y: float = Field(ge=0, le=100)
    risk_level: str

    in_year_hi_band: str | None = None
    in_year_ci_band: str | None = None
    in_year_monetised_risk: float | None = Field(default=None, ge=0)
    typical_cof_weight: float | None = Field(default=None, ge=0)
    typical_in_year_pof_weight: float | None = Field(default=None, ge=0)

    long_term_hi_band: str | None = None
    long_term_ci_band: str | None = None
    long_term_risk_index: float | None = Field(default=None, ge=0)
    forecast_ageing_rate: float | None = Field(default=None, ge=0)
    long_term_cumulative_pof_weight: float | None = Field(default=None, ge=0)

    @classmethod
    def from_results(
        cls,
        asset_id: str,
        pof_result: PoFResult,
        consequence: ConsequenceBreakdown,
        asset_category: str | None = None,
        compute_table_weights: bool = False,
    ) -> RiskProfile:
        """Build a final risk profile from PoF and CoF outputs."""
        cfg = load_lookup("risk_matrix_bands.json")
        hi_bands = [float(value) for value in cfg["hi_bands"]]
        ci_bands = [float(value) for value in cfg["ci_bands"]]

        point_x = cls._map_health_to_percent(pof_result.chs, hi_bands)
        ci = (consequence.total / consequence.reference_total_cost) * 100
        point_y = cls._map_criticality_to_percent(ci, ci_bands)

        monetary_risk = pof_result.pof * consequence.total
        thresholds = cfg["risk_level_thresholds"]
        if monetary_risk < float(thresholds["low"]):
            risk_level = "Low"
        elif monetary_risk < float(thresholds["medium"]):
            risk_level = "Medium"
        else:
            risk_level = "High"

        in_year_hi_band: str | None = None
        in_year_ci_band: str | None = None
        in_year_monetised_risk: float | None = None
        typical_cof_weight: float | None = None
        typical_in_year_pof_weight: float | None = None

        long_term_hi_band: str | None = None
        long_term_ci_band: str | None = None
        long_term_risk_index: float | None = None
        forecast_ageing_rate: float | None = None
        long_term_cumulative_pof_weight: float | None = None

        if compute_table_weights:
            if asset_category is None:
                raise ValueError("asset_category is required when compute_table_weights=True")

            category_key = _category_key(asset_category)
            tables = _risk_weight_tables()

            in_year_hi_band = cls._health_index_band(pof_result.chs)
            ci_pct = (consequence.total / consequence.reference_total_cost) * 100
            in_year_ci_band = cls._criticality_index_band(ci_pct)

            typical_cof_weight = cls._lookup_band_value(
                tables.typical_cof_weight,
                category_key,
                in_year_ci_band,
                "typ_cof_weight_risk_matrices",
            )
            typical_in_year_pof_weight = cls._lookup_band_value(
                tables.typical_in_year_pof_weight,
                category_key,
                in_year_hi_band,
                "typ_pof_weight_risk_matrices",
            )

            in_year_monetised_risk = cls._lookup_matrix_value(
                tables.in_year_monetised_risk,
                category_key,
                in_year_ci_band,
                in_year_hi_band,
                "risk_matrix_weight",
            )

            long_term_hi_band = in_year_hi_band
            long_term_ci_band = in_year_ci_band

            forecast_ageing_rate = tables.forecast_ageing_rate.get(category_key)
            if forecast_ageing_rate is None:
                raise ValueError(
                    "No forecast ageing rate entry in typ_forecast_age_rates for "
                    f"asset_category={asset_category!r}"
                )

            long_term_cumulative_pof_weight = cls._lookup_band_value(
                tables.cumulative_discounted_pof_weight,
                category_key,
                long_term_hi_band,
                "typ_cum_dis_pof_weight_health",
            )
            long_term_risk_index = cls._lookup_matrix_value(
                tables.long_term_risk_index,
                category_key,
                long_term_ci_band,
                long_term_hi_band,
                "risk_matrix_weight_long_term",
            )

        return cls(
            asset_id=asset_id,
            pof=pof_result.pof,
            chs=pof_result.chs,
            financial_cof=consequence.financial,
            safety_cof=consequence.safety,
            environmental_cof=consequence.environmental,
            network_performance_cof=consequence.network_performance,
            total_cof=consequence.total,
            monetary_risk=monetary_risk,
            risk_matrix_x=point_x,
            risk_matrix_y=point_y,
            risk_level=risk_level,
            in_year_hi_band=in_year_hi_band,
            in_year_ci_band=in_year_ci_band,
            in_year_monetised_risk=in_year_monetised_risk,
            typical_cof_weight=typical_cof_weight,
            typical_in_year_pof_weight=typical_in_year_pof_weight,
            long_term_hi_band=long_term_hi_band,
            long_term_ci_band=long_term_ci_band,
            long_term_risk_index=long_term_risk_index,
            forecast_ageing_rate=forecast_ageing_rate,
            long_term_cumulative_pof_weight=long_term_cumulative_pof_weight,
        )

    @staticmethod
    def _map_health_to_percent(chs: float, hi_bands: list[float]) -> float:
        for index, hi in enumerate(hi_bands):
            if chs < hi and index == 0:
                return ((chs - 0.5) / (hi - 0.5)) * (100 / len(hi_bands))
            if chs < hi:
                return ((chs - hi_bands[index - 1]) / (hi - hi_bands[index - 1])) * (
                    100 / len(hi_bands)
                ) + (100 / len(hi_bands)) * index

        return 100.0

    @staticmethod
    def _map_criticality_to_percent(ci: float, ci_bands: list[float]) -> float:
        for index, ci_boundary in enumerate(ci_bands):
            if ci < ci_boundary and index == 0:
                return ((ci - 0) / (ci_boundary - 0)) * (100 / len(ci_bands))
            if ci < ci_boundary:
                return ((ci - ci_bands[index - 1]) / (ci_boundary - ci_bands[index - 1])) * (
                    100 / len(ci_bands)
                ) + (100 / len(ci_bands)) * index

        return 100.0

    @staticmethod
    def _health_index_band(chs: float) -> str:
        rows = load_reference_table("health_index_banding_criteria")["rows"]
        for index, row in enumerate(rows):
            band = str(row["health_index_band"])
            lower = float(row["lower"])
            upper = float(row["upper"])

            if index < len(rows) - 1:
                if chs >= lower and chs < upper:
                    return band
            elif chs >= lower and chs <= upper:
                return band

        if chs < float(rows[0]["lower"]):
            return str(rows[0]["health_index_band"])
        return str(rows[-1]["health_index_band"])

    @staticmethod
    def _criticality_index_band(ci: float) -> str:
        cfg = load_lookup("risk_matrix_bands.json")
        ci_bands = [float(value) for value in cfg["ci_bands"]]

        if ci < ci_bands[0]:
            return "C1"
        if ci < ci_bands[1]:
            return "C2"
        if ci < ci_bands[2]:
            return "C3"
        return "C4"

    @staticmethod
    def _lookup_band_value(
        table: dict[str, dict[str, float]],
        category_key: str,
        band_key: str,
        table_name: str,
    ) -> float:
        by_category = table.get(category_key)
        if by_category is None:
            raise ValueError(
                f"No category match in {table_name} for canonical asset key {category_key!r}"
            )
        value = by_category.get(band_key)
        if value is None:
            raise ValueError(
                f"No band {band_key!r} for category key {category_key!r} in {table_name}"
            )
        return value

    @staticmethod
    def _lookup_matrix_value(
        table: dict[str, dict[str, dict[str, float]]],
        category_key: str,
        ci_band: str,
        hi_band: str,
        table_name: str,
    ) -> float:
        by_category = table.get(category_key)
        if by_category is None:
            raise ValueError(
                f"No category match in {table_name} for canonical asset key {category_key!r}"
            )

        by_ci_band = by_category.get(ci_band)
        if by_ci_band is None:
            raise ValueError(
                f"No CI band {ci_band!r} for category key {category_key!r} in {table_name}"
            )

        value = by_ci_band.get(hi_band)
        if value is None:
            raise ValueError(
                f"No HI band {hi_band!r} for category key {category_key!r} in {table_name}"
            )
        return value

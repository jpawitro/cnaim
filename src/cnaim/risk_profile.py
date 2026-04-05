"""Risk profile model that combines PoF and consequence outputs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .consequences import ConsequenceBreakdown
from .lookups import load_lookup
from .pof import PoFResult


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

    @classmethod
    def from_results(
        cls,
        asset_id: str,
        pof_result: PoFResult,
        consequence: ConsequenceBreakdown,
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

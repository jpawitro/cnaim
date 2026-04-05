"""Consequence of failure models and component breakdowns."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict, Field

from .assets import TransformerAsset
from .lookups import load_lookup


class ConsequenceBreakdown(BaseModel):
    """Consequence components and total values for an asset."""

    model_config = ConfigDict(extra="forbid")

    financial: float = Field(ge=0)
    safety: float = Field(ge=0)
    environmental: float = Field(ge=0)
    network_performance: float = Field(ge=0)
    reference_total_cost: float = Field(ge=0)

    @property
    def total(self) -> float:
        """Total consequence of failure across all components."""
        return self.financial + self.safety + self.environmental + self.network_performance


class ConsequenceModel(ABC):
    """Base contract for consequence models."""

    @abstractmethod
    def calculate(self, asset: TransformerAsset) -> ConsequenceBreakdown:
        """Calculate consequences for the provided asset."""


class Transformer11kVConsequenceModel(ConsequenceModel):
    """Consequence model for 6.6/11kV transformers."""

    def __init__(self) -> None:
        """Load transformer consequence lookup configuration."""
        self._cfg = load_lookup("transformer_11kv_consequence_lookup.json")

    def calculate(self, asset: TransformerAsset) -> ConsequenceBreakdown:
        """Calculate the four CoF components for a transformer."""
        refs = self._cfg["reference_costs_gbp"]

        financial = self._financial_component(asset, refs)
        safety = self._safety_component(asset, refs)
        environmental = self._environmental_component(asset, refs)
        network = self._network_component(asset, refs)

        return ConsequenceBreakdown(
            financial=financial,
            safety=safety,
            environmental=environmental,
            network_performance=network,
            reference_total_cost=sum(float(value) for value in refs.values()),
        )

    def _financial_component(self, asset: TransformerAsset, refs: dict[str, float]) -> float:
        financial_cfg = self._cfg["financial"]
        base = float(refs["financial"])

        type_factor = 1.0
        if asset.rated_capacity_kva is not None:
            for band in financial_cfg["type_financial_factors"]:
                lower = float(band["lower"])
                upper = float(band["upper"])
                if asset.rated_capacity_kva >= lower and asset.rated_capacity_kva < upper:
                    type_factor = float(band["factor"])
                    break

        access_factor = float(financial_cfg["access_factors"][asset.access_type.value])
        return base * type_factor * access_factor

    def _safety_component(self, asset: TransformerAsset, refs: dict[str, float]) -> float:
        safety_cfg = self._cfg["safety"]
        base = float(refs["safety"])

        location_map = safety_cfg["matrix"][asset.location_risk.value]
        factor = float(location_map[asset.type_risk.value])
        return base * factor

    def _environmental_component(self, asset: TransformerAsset, refs: dict[str, float]) -> float:
        environmental_cfg = self._cfg["environmental"]
        base = float(refs["environmental"])

        size_factor = 1.0
        if asset.rated_capacity_kva is not None:
            for band in environmental_cfg["size_factors"]:
                lower = float(band["lower"])
                upper = float(band["upper"])
                if asset.rated_capacity_kva >= lower and asset.rated_capacity_kva < upper:
                    size_factor = float(band["factor"])
                    break

        proximity_factor = 1.0
        if asset.proximity_to_water_m is not None:
            for band in environmental_cfg["proximity_factors"]:
                lower = float(band["lower"])
                upper = float(band["upper"])
                if asset.proximity_to_water_m >= lower and asset.proximity_to_water_m < upper:
                    proximity_factor = float(band["factor"])
                    break

        if asset.bunded is None:
            bunding_factor = 1.0
        else:
            bunding_factor = float(
                environmental_cfg["bunding_factors"]["Yes" if asset.bunded else "No"]
            )

        return base * size_factor * proximity_factor * bunding_factor

    def _network_component(self, asset: TransformerAsset, refs: dict[str, float]) -> float:
        network_cfg = self._cfg["network"]
        base = float(refs["network_performance"])

        kva_factor = 1.0
        if asset.kva_per_customer is not None:
            for band in network_cfg["kva_per_customer_factors"]:
                lower = float(band["lower"])
                upper = float(band["upper"])
                if asset.kva_per_customer >= lower and asset.kva_per_customer < upper:
                    kva_factor = float(band["factor"])
                    break

        reference_customers = float(network_cfg["reference_customers"])
        customer_factor = (kva_factor * float(asset.no_customers)) / reference_customers
        return base * customer_factor

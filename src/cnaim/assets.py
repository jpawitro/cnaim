"""Asset domain models and registry helpers."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .enums import (
    AccessType,
    AssetFamily,
    CableLayout,
    CombinedWaveEnergyIntensity,
    OverheadAccessType,
    RiskLevel,
    SubmarineSituation,
    SubmarineTopography,
    TransformerType,
)
from .lookups import load_lookup


class Asset(BaseModel):
    """Base asset model shared by all concrete asset families.

    `asset_category` must correspond to one value in
    `asset_type_registry.json` for the selected family. The category maps to
    the CNAIM "Asset Register Category" used by all extracted reference
    tables.
    """

    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(min_length=1)
    family: AssetFamily
    asset_name: str = Field(min_length=1)
    asset_category: str | None = Field(default=None, min_length=1)
    sub_division: str | None = Field(default=None, min_length=1)


class NetworkAsset(Asset):
    """Base class for electrical assets carrying risk and site metadata.

    These fields are intentionally shared across all families so one
    table-driven CoF implementation can evaluate every asset class/subclass.
    """

    voltage_kv: float | None = Field(default=None, gt=0)
    rated_capacity_kva: float | None = Field(default=None, gt=0)
    access_type: AccessType = AccessType.TYPE_A
    overhead_access_type: OverheadAccessType = OverheadAccessType.TYPE_A
    type_risk: RiskLevel = RiskLevel.MEDIUM
    location_risk: RiskLevel = RiskLevel.MEDIUM
    no_customers: int = Field(default=0, ge=0)
    kva_per_customer: float | None = Field(default=None, gt=0)
    bunded: bool | None = None
    proximity_to_water_m: float | None = Field(default=None, ge=0)
    safety_blanket: bool = False
    cable_layout: CableLayout = CableLayout.BURIED


class TransformerAsset(NetworkAsset):
    """Transformer asset model used by detailed and generic CNAIM engines."""

    family: AssetFamily = AssetFamily.TRANSFORMER
    transformer_type: TransformerType = TransformerType.TF_11KV_GM

    @model_validator(mode="after")
    def _default_category(self) -> TransformerAsset:
        if self.asset_category is None:
            self.asset_category = self.transformer_type.value
        return self


class CableAsset(NetworkAsset):
    """Cable asset model for all cable subclasses in the asset registry."""

    family: AssetFamily = AssetFamily.CABLE
    cable_type: str | None = Field(default=None, min_length=1)

    # Submarine-specific fields (all optional; non-submarine cables leave these as None/False)
    topography: SubmarineTopography | None = None
    situation: SubmarineSituation | None = None
    wind_wave_rating: int | None = Field(default=None, ge=1, le=3)
    combined_wave_energy_intensity: CombinedWaveEnergyIntensity | None = None
    is_landlocked: bool = False

    @model_validator(mode="after")
    def _default_category(self) -> CableAsset:
        if self.asset_category is None and self.cable_type is not None:
            self.asset_category = self.cable_type
        if self.asset_category is None:
            raise ValueError("asset_category or cable_type must be provided")
        return self


class SwitchgearAsset(NetworkAsset):
    """Switchgear asset model for all switchgear subclasses."""

    family: AssetFamily = AssetFamily.SWITCHGEAR
    switchgear_type: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _default_category(self) -> SwitchgearAsset:
        if self.asset_category is None and self.switchgear_type is not None:
            self.asset_category = self.switchgear_type
        if self.asset_category is None:
            raise ValueError("asset_category or switchgear_type must be provided")
        return self


class OverheadLineAsset(NetworkAsset):
    """Overhead line asset model for supports, conductors, and fittings."""

    family: AssetFamily = AssetFamily.OVERHEAD_LINE
    support_type: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _default_category(self) -> OverheadLineAsset:
        if self.asset_category is None and self.support_type is not None:
            self.asset_category = self.support_type
        if self.asset_category is None:
            raise ValueError("asset_category or support_type must be provided")
        return self


class LowVoltageAsset(NetworkAsset):
    """Low-voltage asset model for LV switchgear and UGB subclasses."""

    family: AssetFamily = AssetFamily.LOW_VOLTAGE
    lv_type: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _default_category(self) -> LowVoltageAsset:
        if self.asset_category is None and self.lv_type is not None:
            self.asset_category = self.lv_type
        if self.asset_category is None:
            raise ValueError("asset_category or lv_type must be provided")
        return self


class AssetCatalog:
    """Reads supported asset families and types from lookup JSON."""

    def __init__(self) -> None:
        """Load the packaged asset registry lookup into memory."""
        self._registry = load_lookup("asset_type_registry.json")

    def list_families(self) -> list[str]:
        """Return all available families in display format."""
        return sorted(self._registry["families"].keys())

    def list_asset_types(self, family: AssetFamily) -> list[str]:
        """Return configured selectable types for a given asset family."""
        entries = self._registry["families"].get(family.value, {})
        return list(entries.get("asset_types", []))

    def supports_asset_type(self, family: AssetFamily, asset_type: str) -> bool:
        """Return whether `asset_type` is configured for the family."""
        return asset_type in self.list_asset_types(family)

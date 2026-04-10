"""Installation parameter models used by PoF and consequence calculations."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .enums import Placement, SwitchgearDutyProfile
from .lookups import load_lookup


class ResolvedInstallation(BaseModel):
    """Installation parameters with defaults resolved to concrete values."""

    model_config = ConfigDict(extra="forbid")

    age_years: float = Field(ge=0)
    placement: Placement
    utilisation_pct: float = Field(ge=0)
    altitude_m: float = Field(ge=0)
    distance_from_coast_km: float = Field(ge=0)
    corrosion_category_index: int = Field(ge=1, le=5)
    reliability_factor: float = Field(ge=0.6, le=1.5)
    operating_voltage_pct: float = Field(gt=0)
    tap_operations_per_day: float = Field(ge=0)
    switchgear_duty_profile: SwitchgearDutyProfile
    location_factor: float = Field(gt=0)


class Installation(BaseModel):
    """Raw installation model accepting user input with optional defaults."""

    model_config = ConfigDict(extra="forbid")

    age_years: float = Field(ge=0)
    placement: Placement | None = None
    utilisation_pct: float | None = Field(default=None, ge=0)
    altitude_m: float | None = Field(default=None, ge=0)
    distance_from_coast_km: float | None = Field(default=None, ge=0)
    corrosion_category_index: int | None = Field(default=None, ge=1, le=5)
    reliability_factor: float | None = Field(default=None, ge=0.6, le=1.5)
    operating_voltage_pct: float | None = Field(default=None, gt=0)
    tap_operations_per_day: float | None = Field(default=None, ge=0)
    switchgear_duty_profile: SwitchgearDutyProfile | None = None
    location_factor: float | None = Field(default=None, gt=0)

    def resolve_for_transformer(self) -> ResolvedInstallation:
        """Resolve missing transformer-related fields using lookup defaults."""
        location_cfg = load_lookup("location_factor_transformer_11_20kv.json")
        duty_cfg = load_lookup("duty_factor_transformer_11_20kv.json")

        return ResolvedInstallation(
            age_years=self.age_years,
            placement=self.placement or Placement(location_cfg["default_placement"]),
            utilisation_pct=self.utilisation_pct
            if self.utilisation_pct is not None
            else float(duty_cfg["default_utilisation_pct"]),
            altitude_m=self.altitude_m
            if self.altitude_m is not None
            else float(location_cfg["default_altitude_m"]),
            distance_from_coast_km=self.distance_from_coast_km
            if self.distance_from_coast_km is not None
            else float(location_cfg["default_distance_from_coast_km"]),
            corrosion_category_index=self.corrosion_category_index
            if self.corrosion_category_index is not None
            else int(location_cfg["default_corrosion_category_index"]),
            reliability_factor=self.reliability_factor
            if self.reliability_factor is not None
            else 1.0,
            operating_voltage_pct=self.operating_voltage_pct
            if self.operating_voltage_pct is not None
            else 100.0,
            tap_operations_per_day=self.tap_operations_per_day
            if self.tap_operations_per_day is not None
            else 7.0,
            switchgear_duty_profile=self.switchgear_duty_profile
            or SwitchgearDutyProfile.NORMAL_LOW,
            location_factor=self.location_factor if self.location_factor is not None else 1.0,
        )

    def resolve_for_submarine_cable(
        self,
        topography: str = "Default",
        situation: str = "Default",
        wind_wave_rating: int | None = None,
        combined_wave_energy_intensity: str = "Default",
        is_landlocked: bool = False,
    ) -> ResolvedInstallation:
        """Resolve Installation for a submarine cable, computing location factor from Tables 27-30.

        If ``self.location_factor`` is explicitly set it takes precedence over
        the computed value. All other fields follow the same defaults as
        ``resolve_generic()``.

        Parameters
        ----------
        topography:
            Topography classification string matching Table 27.
        situation:
            Situation string matching Table 28.
        wind_wave_rating:
            Integer rating (1/2/3) matching Table 29; ``None`` = default.
        combined_wave_energy_intensity:
            Intensity string matching Table 30.
        is_landlocked:
            Selects landlocked scoring columns when ``True``.
        """
        from .submarine import submarine_location_factor

        if self.location_factor is not None:
            computed_lf = self.location_factor
        else:
            computed_lf = submarine_location_factor(
                topography=topography,
                situation=situation,
                wind_wave_rating=wind_wave_rating,
                combined_wave_energy_intensity=combined_wave_energy_intensity,
                is_landlocked=is_landlocked,
            )

        return ResolvedInstallation(
            age_years=self.age_years,
            placement=self.placement or Placement.OUTDOOR,
            utilisation_pct=self.utilisation_pct if self.utilisation_pct is not None else 100.0,
            altitude_m=self.altitude_m if self.altitude_m is not None else 0.0,
            distance_from_coast_km=self.distance_from_coast_km
            if self.distance_from_coast_km is not None
            else 100.0,
            corrosion_category_index=self.corrosion_category_index
            if self.corrosion_category_index is not None
            else 1,
            reliability_factor=self.reliability_factor
            if self.reliability_factor is not None
            else 1.0,
            operating_voltage_pct=self.operating_voltage_pct
            if self.operating_voltage_pct is not None
            else 100.0,
            tap_operations_per_day=self.tap_operations_per_day
            if self.tap_operations_per_day is not None
            else 7.0,
            switchgear_duty_profile=self.switchgear_duty_profile
            or SwitchgearDutyProfile.NORMAL_LOW,
            location_factor=computed_lf,
        )

    def resolve_generic(self) -> ResolvedInstallation:
        """Resolve generic defaults used by all-asset table-driven engines."""
        return ResolvedInstallation(
            age_years=self.age_years,
            placement=self.placement or Placement.OUTDOOR,
            utilisation_pct=self.utilisation_pct if self.utilisation_pct is not None else 100.0,
            altitude_m=self.altitude_m if self.altitude_m is not None else 0.0,
            distance_from_coast_km=self.distance_from_coast_km
            if self.distance_from_coast_km is not None
            else 100.0,
            corrosion_category_index=self.corrosion_category_index
            if self.corrosion_category_index is not None
            else 1,
            reliability_factor=self.reliability_factor
            if self.reliability_factor is not None
            else 1.0,
            operating_voltage_pct=self.operating_voltage_pct
            if self.operating_voltage_pct is not None
            else 100.0,
            tap_operations_per_day=self.tap_operations_per_day
            if self.tap_operations_per_day is not None
            else 7.0,
            switchgear_duty_profile=self.switchgear_duty_profile
            or SwitchgearDutyProfile.NORMAL_LOW,
            location_factor=self.location_factor if self.location_factor is not None else 1.0,
        )

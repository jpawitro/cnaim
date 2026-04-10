"""Enum definitions used across CNAIM domain models."""

from __future__ import annotations

from enum import StrEnum


class AssetFamily(StrEnum):
    """Top-level family used to organize asset subclasses."""

    TRANSFORMER = "Transformer"
    CABLE = "Cable"
    SWITCHGEAR = "Switchgear"
    OVERHEAD_LINE = "OverheadLine"
    LOW_VOLTAGE = "LowVoltage"
    OTHER = "Other"


class TransformerType(StrEnum):
    """Transformer types supported by the initial implementation."""

    TF_11KV_GM = "6.6/11kV Transformer (GM)"
    TF_20KV_GM = "20kV Transformer (GM)"


class Placement(StrEnum):
    """Physical installation environment."""

    INDOOR = "Indoor"
    OUTDOOR = "Outdoor"


class AccessType(StrEnum):
    """Accessibility type used by financial consequence factors."""

    TYPE_A = "Type A"
    TYPE_B = "Type B"
    TYPE_C = "Type C"


class OverheadAccessType(StrEnum):
    """Accessibility type used for overhead line consequence factors."""

    TYPE_A = "Type A"
    TYPE_B = "Type B"


class RiskLevel(StrEnum):
    """Generic risk level enum for safety-related assessments."""

    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class PartialDischargeLevel(StrEnum):
    """Measured partial discharge condition level."""

    DEFAULT = "Default"
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH_NOT_CONFIRMED = "High (Not Confirmed)"
    HIGH_CONFIRMED = "High (Confirmed)"


class TemperatureReading(StrEnum):
    """Measured thermal condition band."""

    DEFAULT = "Default"
    NORMAL = "Normal"
    MODERATELY_HIGH = "Moderately High"
    VERY_HIGH = "Very High"


class ObservedCondition(StrEnum):
    """Observed external condition band."""

    DEFAULT = "Default"
    NO_DETERIORATION = "No deterioration"
    SUPERFICIAL_MINOR = "Superficial/minor deterioration"
    SLIGHT = "Slight deterioration"
    SOME = "Some Deterioration"
    SUBSTANTIAL = "Substantial Deterioration"


class CableLayout(StrEnum):
    """Cable installation exposure used by safety consequence factors."""

    BURIED = "Buried"
    EXPOSED = "Exposed"


class SwitchgearDutyProfile(StrEnum):
    """Switchgear operation profile used by duty-factor lookup table."""

    NORMAL_LOW = "Normal/Low"
    HIGH = "High"


class SubmarineTopography(StrEnum):
    """Topography classification for submarine cable location factor (Table 27)."""

    LOW = "Low Detrimental Topography"
    MEDIUM = "Medium Detrimental Topography"
    HIGH = "High Detrimental Topography"
    VERY_HIGH = "Very High Detrimental Topography"
    DEFAULT = "Default"


class SubmarineSituation(StrEnum):
    """Physical situation/installation of submarine cable (Table 28)."""

    LAID_ON_BED = "Laid on bed"
    COVERED = "Covered"
    BURIED = "Buried"
    DEFAULT = "Default"


class CombinedWaveEnergyIntensity(StrEnum):
    """Combined wave & current energy intensity for submarine cables (Table 30)."""

    LOW = "Low"
    MODERATE = "Moderate"
    HIGH = "High"
    DEFAULT = "Default"


class SubmarineArmourCondition(StrEnum):
    """External condition of armour for submarine cable OCI (Table 107)."""

    GOOD = "Good"
    POOR = "Poor"
    CRITICAL = "Critical"
    DEFAULT = "Default"


class SheathTestResult(StrEnum):
    """Sheath test result for submarine cable MCI (Table 189)."""

    PASS = "Pass"
    FAILED_MINOR = "Failed Minor"
    FAILED_MAJOR = "Failed Major"
    DEFAULT = "Default"

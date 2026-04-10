"""Submarine cable specialisation: location factor and condition modifiers.

Implements CNAIM v2.1 equations 18/19 for the submarine location factor and
all four condition modifier tables unique to submarine cables (OCI: Table 107;
MCI: Tables 189-191).

Reference table IDs used:
- ``submarin_cable_topog_factor``     — Table 27
- ``submarin_cable_sitution_factor``  — Table 28
- ``submarin_cable_wind_wave``        — Table 29
- ``combined_wave_ct_energy_factor``  — Table 30
- ``increment_constants``             — Table 25 (column: submarine_cables)
- ``oci_submrn_cable_ext_cond_armr``  — Table 107
- ``mci_submarine_cbl_sheath_test``   — Table 189
- ``mci_submarine_cable_prtl_disc``   — Table 190
- ``mci_submarine_cable_fault_hist``  — Table 191
"""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict, Field

from .enums import (
    CombinedWaveEnergyIntensity,
    SheathTestResult,
    SubmarineArmourCondition,
    SubmarineSituation,
    SubmarineTopography,
)
from .generic_models import AssetConditionInput
from .health import ConditionModifier, mmi
from .lookups import canonical_name, coerce_numeric, load_reference_table

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_SENTINEL_NO_FAULTS = "nohistoricfaultsrecorded"  # canonical_name("no historic faults recorded")


def _find_exact(
    rows: list[dict[str, object]],
    key_field: str,
    target: str,
) -> dict[str, object] | None:
    """Return first row whose ``key_field`` matches ``target`` (case-insensitive canonical)."""
    target_canonical = canonical_name(target)
    for row in rows:
        value = row.get(key_field)
        if value is not None and canonical_name(str(value)) == target_canonical:
            return row
    return None


def _modifier_from_row(row: dict[str, object]) -> ConditionModifier:
    """Build a ``ConditionModifier`` from a standard condition input table row."""
    factor = coerce_numeric(row["condition_input_factor"])
    cap = coerce_numeric(row["condition_input_cap"])
    collar = coerce_numeric(row["condition_input_collar"])
    if factor is None or cap is None or collar is None:
        raise ValueError(f"Invalid condition modifier row: {row!r}")
    return ConditionModifier(factor=factor, cap=float(cap), collar=float(collar))


# ---------------------------------------------------------------------------
# Submarine location factor (CNAIM EQ. 18 / EQ. 19)
# ---------------------------------------------------------------------------

def submarine_location_factor(
    topography: SubmarineTopography | str = SubmarineTopography.DEFAULT,
    situation: SubmarineSituation | str = SubmarineSituation.DEFAULT,
    wind_wave_rating: int | None = None,
    combined_wave_energy_intensity: CombinedWaveEnergyIntensity | str = CombinedWaveEnergyIntensity.DEFAULT,
    is_landlocked: bool = False,
) -> float:
    r"""Compute the submarine cable location factor.

    Implements CNAIM v2.1 equations:

    - **EQ. 18** (:math:`\max > 1`):
      :math:`LF = \max(f_i) + INC \times \left(\sum_{j \neq \text{argmax}} f_j - 3\right)`
    - **EQ. 19** (:math:`\max \leq 1`):
      :math:`LF = \max(f_i) - INC \times \left(3 - \sum_{j \neq \text{argmax}} f_j\right)`

    where the four sub-factors are topography, situation, wind/wave, and
    combined wave & current energy; and INC = 0.05 (Table 25).

    Parameters
    ----------
    topography:
        Topography classification from Table 27.
    situation:
        Physical installation situation from Table 28.
    wind_wave_rating:
        Integer rating 1, 2, or 3 from Table 29; ``None`` applies the
        default row (rating=1, score=1.0).
    combined_wave_energy_intensity:
        Wave & current energy intensity category from Table 30.
    is_landlocked:
        ``True`` selects the landlocked scoring column; ``False`` (default)
        selects the sea scoring column.

    Returns
    -------
    float
        Computed location factor (≥ a practical lower bound of 0.1).
    """
    # ---- 1. Topography factor (Table 27) -----------------------------------
    topo_rows = load_reference_table("submarin_cable_topog_factor")["rows"]
    topo_key = "score_land_locked" if is_landlocked else "score_sea"
    topo_row = _find_exact(topo_rows, "topography", str(topography))
    if topo_row is None:
        topo_row = _find_exact(topo_rows, "topography", "Default")
    f_topography = float(topo_row[topo_key])  # type: ignore[index]

    # ---- 2. Situation factor (Table 28) ------------------------------------
    sit_rows = load_reference_table("submarin_cable_sitution_factor")["rows"]
    sit_row = _find_exact(sit_rows, "situation", str(situation))
    if sit_row is None:
        sit_row = _find_exact(sit_rows, "situation", "Default")
    f_situation = float(sit_row["score"])  # type: ignore[index]

    # ---- 3. Wind / wave factor (Table 29) ----------------------------------
    ww_rows = load_reference_table("submarin_cable_wind_wave")["rows"]
    f_wind_wave = 1.0  # default
    if wind_wave_rating is not None:
        for row in ww_rows:
            rating_raw = row.get("rating")
            if rating_raw is not None:
                numeric = coerce_numeric(rating_raw)
                if numeric is not None and int(numeric) == wind_wave_rating:
                    f_wind_wave = float(row["score"])
                    break
    else:
        # Use default row (null rating)
        for row in ww_rows:
            if row.get("rating") is None or canonical_name(str(row.get("description", ""))) == "default":
                f_wind_wave = float(row["score"])
                break

    # ---- 4. Combined wave & current energy factor (Table 30) ---------------
    cw_rows = load_reference_table("combined_wave_ct_energy_factor")["rows"]
    cw_key = "scoring_landlocked" if is_landlocked else "scoring_sea"
    cw_row = _find_exact(cw_rows, "intensity", str(combined_wave_energy_intensity))
    if cw_row is None:
        cw_row = _find_exact(cw_rows, "intensity", "Default")
    f_combined_wave = float(cw_row[cw_key])  # type: ignore[index]

    # ---- 5. Increment constant (Table 25) ----------------------------------
    inc_rows = load_reference_table("increment_constants")["rows"]
    inc = 0.05  # documented default; should always be present
    if inc_rows:
        raw_inc = coerce_numeric(inc_rows[0].get("submarine_cables"))
        if raw_inc is not None:
            inc = raw_inc

    # ---- 6. EQ. 18 / EQ. 19 -----------------------------------------------
    factors = [f_topography, f_situation, f_wind_wave, f_combined_wave]
    max_factor = max(factors)
    sum_others = sum(factors) - max_factor  # sum of the three non-maximum factors

    if max_factor > 1:
        # EQ. 18
        location_factor = max_factor + inc * (sum_others - 3)
    else:
        # EQ. 19
        location_factor = max_factor - inc * (3 - sum_others)

    return max(location_factor, 0.1)


# ---------------------------------------------------------------------------
# Submarine OCI modifier — armour external condition (Table 107)
# ---------------------------------------------------------------------------

def submarine_armour_condition_modifier(
    armour_condition: SubmarineArmourCondition | str = SubmarineArmourCondition.DEFAULT,
) -> ConditionModifier:
    """Return the OCI condition modifier for submarine cable armour.

    Looks up the external armour condition in Table 107 and returns the
    associated ``ConditionModifier(factor, cap, collar)``.

    Parameters
    ----------
    armour_condition:
        Observed condition of the armour (Good / Poor / Critical / Default).
    """
    rows = load_reference_table("oci_submrn_cable_ext_cond_armr")["rows"]
    row = _find_exact(rows, "condition_criteria", str(armour_condition))
    if row is None:
        row = _find_exact(rows, "condition_criteria", "Default")
    return _modifier_from_row(row)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Submarine MCI modifiers — Tables 189, 190, 191
# ---------------------------------------------------------------------------

def submarine_sheath_test_modifier(
    sheath_test_result: SheathTestResult | str = SheathTestResult.DEFAULT,
) -> ConditionModifier:
    """Return MCI modifier for submarine cable sheath test result (Table 189).

    Parameters
    ----------
    sheath_test_result:
        Test result: Pass / Failed Minor / Failed Major / Default.
    """
    rows = load_reference_table("mci_submarine_cbl_sheath_test")["rows"]
    row = _find_exact(
        rows,
        "condition_criteria_sheath_test_result",
        str(sheath_test_result),
    )
    if row is None:
        row = _find_exact(rows, "condition_criteria_sheath_test_result", "Default")
    return _modifier_from_row(row)  # type: ignore[arg-type]


def submarine_partial_discharge_modifier(
    partial_discharge_level: str = "Default",
) -> ConditionModifier:
    """Return MCI modifier for submarine cable partial discharge (Table 190).

    Parameters
    ----------
    partial_discharge_level:
        PD level: Low / Medium / High / Default.
    """
    rows = load_reference_table("mci_submarine_cable_prtl_disc")["rows"]
    row = _find_exact(
        rows,
        "condition_criteria_partial_discharge_test_result",
        partial_discharge_level,
    )
    if row is None:
        row = _find_exact(rows, "condition_criteria_partial_discharge_test_result", "Default")
    return _modifier_from_row(row)  # type: ignore[arg-type]


def submarine_fault_history_modifier(
    fault_rate: float | str = "Default",
) -> ConditionModifier:
    """Return MCI modifier for submarine cable fault history (Table 191).

    Parameters
    ----------
    fault_rate:
        Fault rate in faults per annum per km, or the string ``"Default"``
        / ``"No historic faults recorded"``.
    """
    rows = load_reference_table("mci_submarine_cable_fault_hist")["rows"]

    # String sentinel checks
    if isinstance(fault_rate, str):
        canonical = canonical_name(fault_rate)
        if canonical == "default":
            default_row = _find_exact(rows, "lower", "Default")
            if default_row is None:
                # Fall back to last row (default sentinel)
                default_row = rows[-1]
            return _modifier_from_row(default_row)
        if canonical == _SENTINEL_NO_FAULTS:
            no_fault_row = _find_exact(rows, "lower", "No historic faults recorded")
            if no_fault_row is not None:
                return _modifier_from_row(no_fault_row)
        # Try to parse as a float
        try:
            fault_rate = float(fault_rate)
        except ValueError:
            default_row = _find_exact(rows, "lower", "Default")
            return _modifier_from_row(default_row or rows[-1])

    # Numeric band lookup
    rate = float(fault_rate)
    for row in rows:
        lower_raw = row.get("lower")
        upper_raw = row.get("upper")

        # Skip text-sentinel rows (no-fault and default)
        if isinstance(lower_raw, str) and canonical_name(lower_raw) in {
            _SENTINEL_NO_FAULTS,
            "default",
        }:
            continue

        lower_str = str(lower_raw).lower() if lower_raw is not None else ""
        upper_str = str(upper_raw).lower() if upper_raw is not None else ""

        lower_value = coerce_numeric(lower_raw)
        upper_value = coerce_numeric(upper_raw)

        lower_bound = -math.inf if lower_value is None or lower_str == "-infinity" else lower_value
        upper_bound = math.inf if upper_value is None or upper_str == "infinity" else upper_value

        if rate > lower_bound and rate <= upper_bound:
            return _modifier_from_row(row)

    # Fallback to default row
    default_row = _find_exact(rows, "lower", "Default")
    return _modifier_from_row(default_row or rows[-1])


# ---------------------------------------------------------------------------
# SubmarineCableConditionInput — combined condition model
# ---------------------------------------------------------------------------

class SubmarineCableConditionInput(BaseModel):
    """Raw condition inputs for a submarine cable, combined via MMI.

    Observed condition inputs (OCI):
    - ``armour_condition`` — External condition of armour (Table 107)

    Measured condition inputs (MCI):
    - ``sheath_test_result``     — Sheath test result (Table 189)
    - ``partial_discharge_level``— Partial discharge (Table 190)
    - ``fault_rate``             — Fault rate per annum per km (Table 191)

    MMI calibration parameters (from Tables 73 & 74):
    - OCI: divider1=1.5, divider2=1.5, max_no_combined=1
    - MCI: divider1=1.5, divider2=1.5, max_no_combined=2
    """

    model_config = ConfigDict(extra="forbid")

    armour_condition: SubmarineArmourCondition = SubmarineArmourCondition.DEFAULT
    sheath_test_result: SheathTestResult = SheathTestResult.DEFAULT
    partial_discharge_level: str = Field(default="Default")
    fault_rate: float | str = Field(default="Default")

    def to_asset_condition_input(self) -> AssetConditionInput:
        """Combine all sub-modifiers via MMI into a single ``AssetConditionInput``.

        OCI combination: MMI(divider1=1.5, divider2=1.5, max_no_combined=1)
        MCI combination: MMI(divider1=1.5, divider2=1.5, max_no_combined=2)
        """
        # ---- OCI: single input — armour condition --------------------------
        oci_mod = submarine_armour_condition_modifier(self.armour_condition)
        observed_factor = oci_mod.factor
        observed_cap = oci_mod.cap
        observed_collar = oci_mod.collar

        # ---- MCI: three inputs combined via MMI ----------------------------
        mci_sheath = submarine_sheath_test_modifier(self.sheath_test_result)
        mci_pd = submarine_partial_discharge_modifier(self.partial_discharge_level)
        mci_fault = submarine_fault_history_modifier(self.fault_rate)

        mci_factors = [mci_sheath.factor, mci_pd.factor, mci_fault.factor]
        measured_factor = mmi(
            factors=mci_factors,
            factor_divider_1=1.5,
            factor_divider_2=1.5,
            max_no_combined_factors=2,
        )
        measured_cap = min(mci_sheath.cap, mci_pd.cap, mci_fault.cap)
        measured_collar = max(mci_sheath.collar, mci_pd.collar, mci_fault.collar)

        return AssetConditionInput(
            observed_condition_factor=observed_factor,
            measured_condition_factor=measured_factor,
            observed_condition_cap=observed_cap,
            measured_condition_cap=measured_cap,
            observed_condition_collar=observed_collar,
            measured_condition_collar=measured_collar,
        )

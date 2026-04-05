"""Transformer diagnostic modifier helpers derived from CNAIM tables.

These utilities mirror the CNAIM diagnostic modifier workflows used in the
reference R package, while remaining fully Python-native and table-driven.
"""

from __future__ import annotations

import math

from .health import ConditionModifier
from .lookups import canonical_name, coerce_numeric, load_reference_table


def _as_float_or_default(value: float | str, default: float) -> float:
    if isinstance(value, str):
        if canonical_name(value) == "default":
            return default
        return float(value)
    return float(value)


def _find_banded_value(
    rows: list[dict[str, object]],
    value: float,
    value_key: str,
    *,
    stretch_outer_bounds: bool = False,
) -> float:
    for index, row in enumerate(rows):
        lower_raw = row.get("lower")
        upper_raw = row.get("upper")

        lower = coerce_numeric(lower_raw)
        upper = coerce_numeric(upper_raw)

        if lower is None and upper is None:
            continue

        lower_bound = -math.inf if lower is None else lower
        upper_bound = math.inf if upper is None else upper
        if stretch_outer_bounds and index == 0:
            lower_bound = -math.inf
        if stretch_outer_bounds and index == len(rows) - 1:
            upper_bound = math.inf

        if value > lower_bound and value <= upper_bound:
            numeric = coerce_numeric(row.get(value_key))
            if numeric is None:
                raise ValueError(f"Missing numeric value for '{value_key}' in lookup row")
            return numeric

    raise ValueError(f"No matching band found for value {value!r} using '{value_key}'")


def _rows_for_transformer_type(
    table_id: str,
    transformer_type: str,
) -> list[dict[str, object]]:
    target = canonical_name(transformer_type)
    rows = load_reference_table(table_id)["rows"]

    selected: list[dict[str, object]] = []
    for row in rows:
        row_type = row.get("type")
        if row_type is None:
            continue

        normalized = canonical_name(str(row_type))
        if normalized == target:
            selected.append(row)
            continue

        # Some extracted rows contain this typo in source data.
        if target == canonical_name("132kV Transformer (GM)") and normalized == canonical_name(
            "132kV Trabsformer (GM)"
        ):
            selected.append(row)

    if not selected:
        raise ValueError(
            "No calibration rows found for transformer type "
            f"{transformer_type!r} in table {table_id!r}"
        )

    return selected


def _canonical_transformer_group(transformer_type_all: str) -> str:
    normalized = canonical_name(transformer_type_all)

    if normalized in {
        canonical_name("6.6/11kV Transformer (GM)"),
        canonical_name("20kV Transformer (GM)"),
    }:
        return "HV Transformer (GM)"

    if normalized in {
        canonical_name("33kV Transformer (GM)"),
        canonical_name("66kV Transformer (GM)"),
    }:
        return "EHV Transformer (GM)"

    if normalized == canonical_name("132kV Transformer (GM)"):
        return "132kV Transformer (GM)"

    raise ValueError(
        "Unsupported transformer_type_all. Expected one of: "
        "6.6/11kV, 20kV, 33kV, 66kV, 132kV Transformer (GM)."
    )


def ffa_test_modifier(
    furfuraldehyde_ppm: float | str = "Default",
) -> ConditionModifier:
    """Return the FFA test condition modifier.

    CNAIM mapping:
    - factor: lookup from `ffa_test_factor` by furfuraldehyde band.
    - cap: fixed at 10.
    - collar: `2.33 * furfuraldehyde^0.68`, floored to 0.5 for default,
      then capped at 7.
    """
    furfuraldehyde = _as_float_or_default(furfuraldehyde_ppm, -0.01)

    rows = load_reference_table("ffa_test_factor")["rows"]
    factor = _find_banded_value(rows, furfuraldehyde, "ffa_test_factor")

    collar = 0.5 if furfuraldehyde < 0 else 2.33 * (furfuraldehyde**0.68)
    collar = min(collar, 7.0)

    return ConditionModifier(factor=factor, cap=10.0, collar=collar)


def oil_test_modifier(
    moisture_ppm: float | str = "Default",
    acidity_mg_koh_g: float | str = "Default",
    bd_strength_kv: float | str = "Default",
    transformer_type_all: str = "20kV Transformer (GM)",
) -> ConditionModifier:
    """Return the oil test condition modifier.

    The implementation follows CNAIM section 6.11 calibration tables:
    - moisture/acidity/bd-strength -> condition scores
    - weighted oil score = `80*moisture + 125*acidity + 80*bd_strength`
    - factor/collar from dedicated oil-test calibration tables
    - cap fixed at 10
    """
    transformer_group = _canonical_transformer_group(transformer_type_all)

    moisture = _as_float_or_default(moisture_ppm, -0.1)
    acidity = _as_float_or_default(acidity_mg_koh_g, -0.1)
    bd_strength = _as_float_or_default(bd_strength_kv, 10000.0)

    moisture_rows = _rows_for_transformer_type(
        "moisture_cond_state_calib",
        transformer_group,
    )
    acidity_rows = _rows_for_transformer_type(
        "acidity_cond_state_calib",
        transformer_group,
    )
    bd_rows = _rows_for_transformer_type(
        "bd_strength_cond_state_calib",
        transformer_group,
    )

    moisture_score = _find_banded_value(
        moisture_rows,
        moisture,
        "moisture_score",
        stretch_outer_bounds=True,
    )
    acidity_score = _find_banded_value(
        acidity_rows,
        acidity,
        "acidity_score",
        stretch_outer_bounds=True,
    )
    bd_strength_score = _find_banded_value(
        bd_rows,
        bd_strength,
        "bd_strength_score",
        stretch_outer_bounds=True,
    )

    oil_condition_score = (
        (80.0 * moisture_score) + (125.0 * acidity_score) + (80.0 * bd_strength_score)
    )

    factor_rows = _rows_for_transformer_type(
        "oil_test_factor_calib",
        transformer_group,
    )
    collar_rows = _rows_for_transformer_type(
        "oil_test_collar_calib",
        transformer_group,
    )

    factor = _find_banded_value(
        factor_rows,
        oil_condition_score,
        "oil_test_factor",
        stretch_outer_bounds=True,
    )
    collar = _find_banded_value(
        collar_rows,
        oil_condition_score,
        "oil_test_collar",
        stretch_outer_bounds=True,
    )

    return ConditionModifier(factor=factor, cap=10.0, collar=collar)


def dga_test_modifier(
    hydrogen_ppm: float | str = "Default",
    methane_ppm: float | str = "Default",
    ethylene_ppm: float | str = "Default",
    ethane_ppm: float | str = "Default",
    acetylene_ppm: float | str = "Default",
    hydrogen_pre_ppm: float | str = "Default",
    methane_pre_ppm: float | str = "Default",
    ethylene_pre_ppm: float | str = "Default",
    ethane_pre_ppm: float | str = "Default",
    acetylene_pre_ppm: float | str = "Default",
) -> ConditionModifier:
    """Return the DGA test condition modifier.

    CNAIM mapping:
    - each gas level maps to a condition state score from calibration tables.
    - weighted DGA score uses coefficients 50/30/30/30/120.
    - factor comes from percentage change category calibration.
    - cap fixed at 10.
    - collar = `score/220`, lower bounded at 1 and capped at 7.
    """
    hydrogen = _as_float_or_default(hydrogen_ppm, -0.1)
    methane = _as_float_or_default(methane_ppm, -0.1)
    ethylene = _as_float_or_default(ethylene_ppm, -0.1)
    ethane = _as_float_or_default(ethane_ppm, -0.1)
    acetylene = _as_float_or_default(acetylene_ppm, -0.1)

    hydrogen_pre = _as_float_or_default(hydrogen_pre_ppm, -0.1)
    methane_pre = _as_float_or_default(methane_pre_ppm, -0.1)
    ethylene_pre = _as_float_or_default(ethylene_pre_ppm, -0.1)
    ethane_pre = _as_float_or_default(ethane_pre_ppm, -0.1)
    acetylene_pre = _as_float_or_default(acetylene_pre_ppm, -0.1)

    hydrogen_rows = load_reference_table("hydrogen_cond_state_calib")["rows"]
    methane_rows = load_reference_table("methane_cond_state_calib")["rows"]
    ethylene_rows = load_reference_table("ethylene_cond_state_calib")["rows"]
    ethane_rows = load_reference_table("ethane_cond_state_calib")["rows"]
    acetylene_rows = load_reference_table("acetylene_cond_state_calib")["rows"]

    hydrogen_score = _find_banded_value(
        hydrogen_rows,
        hydrogen,
        "hydrogen_condition_state",
        stretch_outer_bounds=True,
    )
    methane_score = _find_banded_value(
        methane_rows,
        methane,
        "methane_condition_state",
        stretch_outer_bounds=True,
    )
    ethylene_score = _find_banded_value(
        ethylene_rows,
        ethylene,
        "ethylene_condition_state",
        stretch_outer_bounds=True,
    )
    ethane_score = _find_banded_value(
        ethane_rows,
        ethane,
        "ethane_condition_state",
        stretch_outer_bounds=True,
    )
    acetylene_score = _find_banded_value(
        acetylene_rows,
        acetylene,
        "acetylene_condition_state",
        stretch_outer_bounds=True,
    )

    hydrogen_score_pre = _find_banded_value(
        hydrogen_rows,
        hydrogen_pre,
        "hydrogen_condition_state",
        stretch_outer_bounds=True,
    )
    methane_score_pre = _find_banded_value(
        methane_rows,
        methane_pre,
        "methane_condition_state",
        stretch_outer_bounds=True,
    )
    ethylene_score_pre = _find_banded_value(
        ethylene_rows,
        ethylene_pre,
        "ethylene_condition_state",
        stretch_outer_bounds=True,
    )
    ethane_score_pre = _find_banded_value(
        ethane_rows,
        ethane_pre,
        "ethane_condition_state",
        stretch_outer_bounds=True,
    )
    acetylene_score_pre = _find_banded_value(
        acetylene_rows,
        acetylene_pre,
        "acetylene_condition_state",
        stretch_outer_bounds=True,
    )

    dga_score = (
        (50.0 * hydrogen_score)
        + (30.0 * methane_score)
        + (30.0 * ethylene_score)
        + (30.0 * ethane_score)
        + (120.0 * acetylene_score)
    )

    dga_score_pre = (
        (50.0 * hydrogen_score_pre)
        + (30.0 * methane_score_pre)
        + (30.0 * ethylene_score_pre)
        + (30.0 * ethane_score_pre)
        + (120.0 * acetylene_score_pre)
    )

    if dga_score_pre == 0 and dga_score == 0:
        change_pct = 0.0
    elif dga_score_pre == 0:
        change_pct = math.inf
    else:
        change_pct = ((dga_score / dga_score_pre) - 1.0) * 100.0

    change_rows = load_reference_table("dga_change_category_calib")["rows"]
    category: str | None = None
    for index, row in enumerate(change_rows):
        lower = coerce_numeric(row.get("lower"))
        upper = coerce_numeric(row.get("upper"))

        if lower is None and upper is None:
            continue

        lower_bound = -math.inf if lower is None else lower
        upper_bound = math.inf if upper is None else upper
        if index == 0:
            lower_bound = -math.inf
        if index == len(change_rows) - 1:
            upper_bound = math.inf
        if change_pct > lower_bound and change_pct <= upper_bound:
            category = str(row["change_category"])
            break

    if category is None:
        raise ValueError(f"Unable to map DGA change percentage to category: {change_pct}")

    dga_factor_rows = load_reference_table("dga_test_factor_calib")["rows"]
    factor = 1.0
    target = canonical_name(category)
    for row in dga_factor_rows:
        if canonical_name(str(row.get("pct_change", ""))) == target:
            numeric = coerce_numeric(row.get("dga_test_factor"))
            if numeric is None:
                raise ValueError("Invalid DGA test factor calibration row")
            factor = numeric
            break

    collar = max(1.0, dga_score / 220.0)
    collar = min(collar, 7.0)

    return ConditionModifier(factor=factor, cap=10.0, collar=collar)

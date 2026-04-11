"""Table-driven location-factor utilities for CNAIM tables 22-26."""

from __future__ import annotations

from functools import cache

from .enums import Placement
from .lookups import (
    NumericBand,
    canonical_name,
    coerce_numeric,
    load_reference_table,
    lookup_factor_interval,
)

_LOCATION_COLUMNS = {
    "switchgear",
    "transformers",
    "poles_wood",
    "poles_steel",
    "poles_concrete",
    "towers_structure",
    "towers_fittings",
    "towers_conductor",
}


def _to_float(value: object, context: str) -> float:
    numeric = coerce_numeric(value)
    if numeric is None:
        raise ValueError(f"Expected numeric value for {context}, got {value!r}")
    return float(numeric)


@cache
def _category_to_generic_terms() -> dict[str, tuple[str | None, str | None]]:
    categorisation = load_reference_table("categorisation_of_assets")["rows"]
    generic_terms = load_reference_table("generic_terms_for_assets")["rows"]

    health_to_terms: dict[str, tuple[str | None, str | None]] = {}
    for row in generic_terms:
        health = row.get("health_index_asset_category")
        if health is None:
            continue
        health_to_terms[canonical_name(str(health))] = (
            str(row["generic_term"]) if row.get("generic_term") is not None else None,
            str(row["generic_term_1"]) if row.get("generic_term_1") is not None else None,
        )

    category_to_terms: dict[str, tuple[str | None, str | None]] = {}
    for row in categorisation:
        category = row.get("asset_register_category")
        health = row.get("health_index_asset_category")
        if category is None or health is None:
            continue
        category_to_terms[canonical_name(str(category))] = health_to_terms.get(
            canonical_name(str(health)),
            (None, None),
        )

    return category_to_terms


@cache
def _environment_defaults_by_category() -> dict[str, Placement | None]:
    rows = load_reference_table("environment_indoor_outdoor")["rows"]
    mapping: dict[str, Placement | None] = {}

    field = "default_environment_to_be_assumed_when_deriving_location_factor"
    for row in rows:
        category = row.get("asset_register_category")
        if category is None:
            continue

        raw_environment = row.get(field)
        key = canonical_name(str(category))
        if raw_environment is None:
            mapping[key] = None
            continue

        try:
            mapping[key] = Placement(str(raw_environment))
        except ValueError:
            mapping[key] = None

    return mapping


def default_placement_for_asset(asset_category: str | None) -> Placement | None:
    """Return Table 26 default placement for an asset category, if present."""
    if asset_category is None:
        return None
    return _environment_defaults_by_category().get(canonical_name(asset_category))


def resolve_placement(
    explicit_placement: Placement | None,
    asset_category: str | None,
    fallback: Placement,
) -> Placement:
    """Resolve placement using explicit input, then Table 26, then fallback."""
    if explicit_placement is not None:
        return explicit_placement

    from_table = default_placement_for_asset(asset_category)
    if from_table is not None:
        return from_table

    return fallback


def _pole_material_column(sub_division: str | None) -> str:
    if sub_division is None:
        return "poles_concrete"

    key = canonical_name(sub_division)
    if "wood" in key:
        return "poles_wood"
    if "steel" in key:
        return "poles_steel"
    if "concrete" in key:
        return "poles_concrete"

    return "poles_concrete"


def _fallback_column_from_category_name(asset_key: str, sub_division: str | None) -> str | None:
    if "transformer" in asset_key:
        return "transformers"
    if "switch" in asset_key or "rmu" in asset_key or "circuitbreaker" in asset_key:
        return "switchgear"
    if "pillar" in asset_key or "board" in asset_key or "ugb" in asset_key:
        return "switchgear"
    if "pole" in asset_key:
        return _pole_material_column(sub_division)
    if "tower" in asset_key:
        return "towers_structure"
    if "fitting" in asset_key:
        return "towers_fittings"
    if "conductor" in asset_key:
        return "towers_conductor"
    if "cable" in asset_key:
        return None
    return None


def location_factor_column_for_asset(
    asset_category: str | None,
    sub_division: str | None = None,
) -> str | None:
    """Map asset category to the relevant Tables 22-25 factor column.

    Returns ``None`` when the CNAIM location-factor tables 22-25 do not apply
    (for example non-submarine cable categories).
    """
    if asset_category is None:
        return None

    asset_key = canonical_name(asset_category)
    generic_term, generic_term_1 = _category_to_generic_terms().get(asset_key, (None, None))

    generic_key = canonical_name(generic_term or "")
    generic_1_key = canonical_name(generic_term_1 or "")

    if generic_key == "switchgear":
        return "switchgear"

    if generic_key == "transformers":
        return "transformers"

    if generic_key == "overheadline":
        if generic_1_key == "poles":
            return _pole_material_column(sub_division)
        if generic_1_key == "towers":
            return "towers_structure"
        if generic_1_key == "fittings":
            return "towers_fittings"
        if generic_1_key == "ohlconductor":
            return "towers_conductor"

    if generic_key == "cable":
        return None

    return _fallback_column_from_category_name(asset_key, sub_division)


@cache
def _interval_bands_and_default(
    table_id: str,
    factor_column: str,
) -> tuple[list[NumericBand], float]:
    rows = load_reference_table(table_id)["rows"]
    bands: list[NumericBand] = []
    default_factor = 1.0

    for row in rows:
        lower = row.get("lower")
        upper = row.get("upper")
        factor = _to_float(row.get(factor_column), f"{table_id}.{factor_column}")

        if (
            lower is not None
            and upper is not None
            and canonical_name(str(lower)) == "default"
            and canonical_name(str(upper)) == "default"
        ):
            default_factor = factor
            continue

        lower_value = coerce_numeric(lower)
        upper_value = coerce_numeric(upper)
        if lower_value is None or upper_value is None:
            continue

        bands.append(NumericBand(lower=float(lower_value), upper=float(upper_value), factor=factor))

    if not bands:
        raise ValueError(f"No interval rows found for {table_id}.{factor_column}")

    bands.sort(key=lambda band: band.lower)
    return bands, default_factor


@cache
def _corrosion_factors_and_default(
    factor_column: str,
) -> tuple[dict[int, float], float]:
    rows = load_reference_table("corrosion_category_factor_lut")["rows"]
    factors: dict[int, float] = {}
    default_factor = 1.0

    for row in rows:
        index_value = row.get("corrosion_category_index")
        factor = _to_float(
            row.get(factor_column),
            f"corrosion_category_factor_lut.{factor_column}",
        )
        if index_value is None:
            continue

        if canonical_name(str(index_value)) == "default":
            default_factor = factor
            continue

        numeric_index = coerce_numeric(index_value)
        if numeric_index is None:
            continue

        factors[int(numeric_index)] = factor

    return factors, default_factor


@cache
def _increment_constant_for_column(factor_column: str) -> float:
    rows = load_reference_table("increment_constants")["rows"]
    if not rows:
        return 0.0

    raw_value = rows[0].get(factor_column)
    numeric = coerce_numeric(raw_value)
    if numeric is None:
        return 0.0
    return float(numeric)


def _outdoor_location_factor(factors: list[float], increment_constant: float) -> float:
    max_factor = max(factors)
    if max_factor > 1:
        count = len([factor for factor in factors if factor > 1])
        return max_factor + ((count - 1) * increment_constant)
    return min(factors)


def _indoor_location_factor(
    factors: list[float],
    min_factors: list[float],
    increment_constant: float,
) -> float:
    initial_location = _outdoor_location_factor(factors, increment_constant)
    min_initial = _outdoor_location_factor(min_factors, increment_constant)
    return 0.25 * (initial_location - min_initial) + min_initial


def location_factor_from_tables(
    factor_column: str,
    placement: Placement,
    altitude_m: float | None,
    distance_from_coast_km: float | None,
    corrosion_category_index: int | None,
) -> float:
    """Compute location factor from CNAIM tables 22-25 for one asset column."""
    if factor_column not in _LOCATION_COLUMNS:
        raise ValueError(f"Unsupported location factor column: {factor_column}")

    altitude_bands, altitude_default = _interval_bands_and_default(
        "altitude_factor_lut",
        factor_column,
    )
    coast_bands, coast_default = _interval_bands_and_default(
        "distance_from_coast_factor_lut",
        factor_column,
    )
    corrosion_factors, corrosion_default = _corrosion_factors_and_default(factor_column)
    increment_constant = _increment_constant_for_column(factor_column)

    if altitude_m is None:
        altitude_factor = altitude_default
    else:
        altitude_factor = lookup_factor_interval(
            altitude_m,
            altitude_bands,
            default=altitude_default,
        )

    if distance_from_coast_km is None:
        coast_factor = coast_default
    else:
        coast_factor = lookup_factor_interval(
            distance_from_coast_km,
            coast_bands,
            default=coast_default,
        )

    if corrosion_category_index is None:
        corrosion_factor = corrosion_default
    else:
        corrosion_factor = corrosion_factors.get(corrosion_category_index, corrosion_default)

    factors = [coast_factor, corrosion_factor, altitude_factor]
    if placement == Placement.OUTDOOR:
        return _outdoor_location_factor(factors, increment_constant)

    min_factors = [
        min(band.factor for band in coast_bands),
        min(corrosion_factors.values(), default=corrosion_default),
        min(band.factor for band in altitude_bands),
    ]
    return _indoor_location_factor(factors, min_factors, increment_constant)

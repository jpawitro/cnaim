"""Lookup loading and utility helpers for CNAIM configuration tables."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from functools import cache
from importlib.resources import files
from typing import Any, cast


@dataclass(frozen=True)
class NumericBand:
    """Simple numeric interval with an attached factor value."""

    lower: float
    upper: float
    factor: float


@cache
def load_lookup(filename: str) -> dict[str, Any]:
    """Load a JSON lookup file from packaged CNAIM config resources."""
    resource = files("cnaim").joinpath("config", "lookups", filename)
    with resource.open("r", encoding="utf-8") as handle:
        return cast(dict[str, Any], json.load(handle))


@cache
def load_reference_table(table_id: str) -> dict[str, Any]:
    """Load one extracted CNAIM reference table by table id.

    Tables are stored under `config/lookups/reference_tables` and aligned to
    the PDF-first baseline summary in `README.md`.
    """
    resource = files("cnaim").joinpath("config", "lookups", "reference_tables", f"{table_id}.json")
    with resource.open("r", encoding="utf-8") as handle:
        return cast(dict[str, Any], json.load(handle))


def canonical_name(value: str) -> str:
    """Normalize free-text keys for tolerant table matching."""
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def coerce_numeric(value: Any) -> float | None:
    """Convert a lookup value to float, handling CNAIM infinity markers."""
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    lowered = text.lower()
    if lowered in {"infinity", "+infinity", "inf", "+inf"}:
        return math.inf
    if lowered in {"-infinity", "-inf"}:
        return -math.inf

    try:
        return float(text)
    except ValueError:
        return None


def as_bands(items: list[dict[str, float]]) -> list[NumericBand]:
    """Convert lookup dictionaries into typed NumericBand instances."""
    return [
        NumericBand(
            lower=float(item["lower"]),
            upper=float(item["upper"]),
            factor=float(item["factor"]),
        )
        for item in items
    ]


def lookup_factor_interval(
    value: float, bands: list[NumericBand], default: float | None = None
) -> float:
    """Lookup a factor using CNAIM interval semantics: (lower, upper]."""
    for band in bands:
        if value > band.lower and value <= band.upper:
            return band.factor

    if default is not None:
        return default

    if value <= bands[0].lower:
        return bands[0].factor

    return bands[-1].factor

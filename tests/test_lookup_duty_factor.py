"""Tests for lookup interval semantics used by duty-factor tables."""

from __future__ import annotations

from cnaim.lookups import as_bands, load_lookup, lookup_factor_interval


def test_duty_factor_transformer_11_20kv_lookup() -> None:
    """Verify (lower, upper] duty-factor lookup behavior and defaults."""
    cfg = load_lookup("duty_factor_transformer_11_20kv.json")
    bands = as_bands(cfg["bands"])

    assert lookup_factor_interval(45, bands, float(cfg["default_duty_factor"])) == 0.9
    assert lookup_factor_interval(50, bands, float(cfg["default_duty_factor"])) == 0.9
    assert lookup_factor_interval(65, bands, float(cfg["default_duty_factor"])) == 0.95
    assert lookup_factor_interval(70, bands, float(cfg["default_duty_factor"])) == 0.95
    assert lookup_factor_interval(75, bands, float(cfg["default_duty_factor"])) == 1.0
    assert lookup_factor_interval(100, bands, float(cfg["default_duty_factor"])) == 1.0
    assert lookup_factor_interval(1000, bands, float(cfg["default_duty_factor"])) == 1.4

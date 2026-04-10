"""Tests for the submarine cable location factor (CNAIM EQ. 18 / EQ. 19)."""

import pytest

from cnaim.enums import (
    CombinedWaveEnergyIntensity,
    SubmarineSituation,
    SubmarineTopography,
)
from cnaim.submarine import submarine_location_factor


# ---------------------------------------------------------------------------
# Default / baseline
# ---------------------------------------------------------------------------


def test_all_defaults_sea():
    """Sea defaults: topography Default=score_sea 1.25, combined_wave Default=scoring_sea 1.1."""
    lf = submarine_location_factor()
    # f_topo=1.25, f_sit=1.0, f_ww=1.0, f_cw=1.1
    # max=1.25 > 1 → EQ.18: 1.25 + 0.05*(1.0+1.0+1.1 - 3) = 1.25 + 0.005 = 1.255
    assert lf == pytest.approx(1.255, abs=1e-9)


def test_all_defaults_sea_vs_landlocked():
    """Sea and landlocked defaults differ because scoring columns are different."""
    lf_sea = submarine_location_factor(is_landlocked=False)
    lf_ll = submarine_location_factor(is_landlocked=True)
    # Sea: f_topo=1.25, f_sit=1.0, f_ww=1.0, f_cw=1.1 → EQ.18 → 1.255
    assert lf_sea == pytest.approx(1.255, abs=1e-9)
    # Landlocked: f_topo=0.5, f_sit=1.0, f_ww=1.0, f_cw=1.0 → max=1.0 → EQ.19
    # EQ.19: 1.0 - 0.05*(3 - (0.5+1.0+1.0)) = 1.0 - 0.025 = 0.975
    assert lf_ll == pytest.approx(0.975, abs=1e-9)


# ---------------------------------------------------------------------------
# Individual factor isolation
# ---------------------------------------------------------------------------


def test_topography_low_sea():
    """Low detrimental topography on sea: score_sea=1.25; others=1.0. EQ.18."""
    lf = submarine_location_factor(
        topography=SubmarineTopography.LOW,
        situation=SubmarineSituation.DEFAULT,
        wind_wave_rating=None,
        combined_wave_energy_intensity=CombinedWaveEnergyIntensity.DEFAULT,
        is_landlocked=False,
    )
    # f_topo=1.25, f_sit=1.0, f_ww=1.0, f_cw=1.1 (default sea scoring)
    # max=1.25, sum_others=1.0+1.0+1.1=3.1
    # EQ.18: 1.25 + 0.05*(3.1-3) = 1.25 + 0.05*0.1 = 1.25 + 0.005 = 1.255
    assert lf == pytest.approx(1.255, abs=1e-9)


def test_topography_very_high_sea():
    """Very high detrimental topography on sea: score_sea=3.0. EQ.18."""
    lf = submarine_location_factor(
        topography=SubmarineTopography.VERY_HIGH,
        situation=SubmarineSituation.DEFAULT,
        wind_wave_rating=None,
        combined_wave_energy_intensity=CombinedWaveEnergyIntensity.DEFAULT,
        is_landlocked=False,
    )
    # f_topo=3.0, sum_others=1.0+1.0+1.1=3.1
    # EQ.18: 3.0 + 0.05*(3.1-3) = 3.005
    assert lf == pytest.approx(3.005, abs=1e-9)


def test_topography_low_landlocked():
    """Low detrimental topography, landlocked: score_land_locked=0.5. EQ.19."""
    lf = submarine_location_factor(
        topography=SubmarineTopography.LOW,
        situation=SubmarineSituation.DEFAULT,
        wind_wave_rating=None,
        combined_wave_energy_intensity=CombinedWaveEnergyIntensity.DEFAULT,
        is_landlocked=True,
    )
    # f_topo=0.5, f_sit=1.0, f_ww=1.0, f_cw=1.0 (default landlocked scoring)
    # max=1.0, sum_others=0.5+1.0+1.0=2.5
    # EQ.19: 1.0 - 0.05*(3-2.5) = 1.0 - 0.025 = 0.975
    assert lf == pytest.approx(0.975, abs=1e-9)


def test_situation_buried():
    """Buried situation reduces factor (score=0.8). Other factors default."""
    lf = submarine_location_factor(
        topography=SubmarineTopography.DEFAULT,
        situation=SubmarineSituation.BURIED,
        wind_wave_rating=None,
        combined_wave_energy_intensity=CombinedWaveEnergyIntensity.DEFAULT,
        is_landlocked=False,
    )
    # f_topo=1.25 (default sea), f_sit=0.8, f_ww=1.0, f_cw=1.1
    # max=1.25, sum_others=0.8+1.0+1.1=2.9
    # EQ.18: 1.25 + 0.05*(2.9-3) = 1.25 - 0.005 = 1.245
    assert lf == pytest.approx(1.245, abs=1e-9)


def test_wind_wave_rating_1():
    """Wind/wave rating 1 = score 1.0."""
    lf = submarine_location_factor(
        topography=SubmarineTopography.DEFAULT,
        situation=SubmarineSituation.DEFAULT,
        wind_wave_rating=1,
        combined_wave_energy_intensity=CombinedWaveEnergyIntensity.DEFAULT,
        is_landlocked=False,
    )
    # f_topo=1.25, f_sit=1.0, f_ww=1.0, f_cw=1.1
    # Identical to LOW topography default; max=1.25, sum_others=3.1
    # EQ.18: 1.255
    assert lf == pytest.approx(1.255, abs=1e-9)


def test_wind_wave_rating_3():
    """Wind/wave rating 3 = score 1.4. Should be max when topography=DEFAULT."""
    lf = submarine_location_factor(
        topography=SubmarineTopography.DEFAULT,
        situation=SubmarineSituation.DEFAULT,
        wind_wave_rating=3,
        combined_wave_energy_intensity=CombinedWaveEnergyIntensity.DEFAULT,
        is_landlocked=False,
    )
    # f_topo=1.25, f_sit=1.0, f_ww=1.4, f_cw=1.1
    # max=1.4, sum_others=1.25+1.0+1.1=3.35
    # EQ.18: 1.4 + 0.05*(3.35-3) = 1.4 + 0.0175 = 1.4175
    assert lf == pytest.approx(1.4175, abs=1e-9)


def test_combined_wave_high_sea():
    """High combined wave energy on sea: scoring_sea=1.5."""
    lf = submarine_location_factor(
        topography=SubmarineTopography.DEFAULT,
        situation=SubmarineSituation.DEFAULT,
        wind_wave_rating=None,
        combined_wave_energy_intensity=CombinedWaveEnergyIntensity.HIGH,
        is_landlocked=False,
    )
    # f_topo=1.25, f_sit=1.0, f_ww=1.0, f_cw=1.5
    # max=1.5, sum_others=1.25+1.0+1.0=3.25
    # EQ.18: 1.5 + 0.05*(3.25-3) = 1.5 + 0.0125 = 1.5125
    assert lf == pytest.approx(1.5125, abs=1e-9)


def test_combined_wave_high_landlocked():
    """High combined wave energy landlocked: scoring_landlocked=1.4."""
    lf = submarine_location_factor(
        topography=SubmarineTopography.DEFAULT,
        situation=SubmarineSituation.DEFAULT,
        wind_wave_rating=None,
        combined_wave_energy_intensity=CombinedWaveEnergyIntensity.HIGH,
        is_landlocked=True,
    )
    # f_topo=0.5 (DEFAULT landlocked), f_sit=1.0, f_ww=1.0, f_cw=1.4
    # max=1.4, sum_others=0.5+1.0+1.0=2.5
    # EQ.18: 1.4 + 0.05*(2.5-3) = 1.4 - 0.025 = 1.375
    assert lf == pytest.approx(1.375, abs=1e-9)


# ---------------------------------------------------------------------------
# EQ. 18 vs EQ. 19 branching
# ---------------------------------------------------------------------------


def test_eq18_when_max_greater_than_one():
    """EQ. 18 fires whenever any factor > 1."""
    # f_cw = Low sea = 1.1 > 1 triggers EQ.18
    lf = submarine_location_factor(
        topography="Default",
        situation="Buried",
        wind_wave_rating=None,
        combined_wave_energy_intensity="Low",
        is_landlocked=False,
    )
    # f_topo=1.25 (Default sea), f_sit=0.8, f_ww=1.0, f_cw=1.1
    # max=1.25, sum_others=0.8+1.0+1.1=2.9
    # EQ.18: 1.25 + 0.05*(2.9-3) = 1.245
    assert lf > 1.0


def test_eq19_all_factors_at_one():
    """EQ. 19 fires when max == 1 — base case: all at exactly 1."""
    # Force all factors to 1 by using landlocked + Low topography (score 0.5)
    # combined_wave=Low landlocked=1.0, topo=Low landlocked=0.5, sit=Buried=0.8, ww=1.0
    # max=1.0, triggers EQ.19
    lf = submarine_location_factor(
        topography=SubmarineTopography.LOW,
        situation=SubmarineSituation.COVERED,
        wind_wave_rating=1,
        combined_wave_energy_intensity=CombinedWaveEnergyIntensity.LOW,
        is_landlocked=True,
    )
    # f_topo=0.5 (Low landlocked), f_sit=0.9 (Covered), f_ww=1.0 (rating=1), f_cw=1.0 (Low landlocked)
    # max=1.0, sum_others=0.5+0.9+1.0=2.4
    # EQ.19: 1.0 - 0.05*(3-2.4) = 1.0 - 0.03 = 0.97
    assert lf == pytest.approx(0.97, abs=1e-9)
    assert lf < 1.0


# ---------------------------------------------------------------------------
# String API (flexible input)
# ---------------------------------------------------------------------------


def test_accepts_string_topography():
    """Topography can be passed as a plain string."""
    lf_enum = submarine_location_factor(topography=SubmarineTopography.LOW)
    lf_str = submarine_location_factor(topography="Low Detrimental Topography")
    assert lf_enum == pytest.approx(lf_str, abs=1e-9)


def test_accepts_string_situation():
    """Situation can be passed as a plain string."""
    lf_enum = submarine_location_factor(situation=SubmarineSituation.BURIED)
    lf_str = submarine_location_factor(situation="Buried")
    assert lf_enum == pytest.approx(lf_str, abs=1e-9)


# ---------------------------------------------------------------------------
# Lower bound safeguard
# ---------------------------------------------------------------------------


def test_result_never_below_minimum():
    """Even with very low landlocked scores the result stays >= 0.1."""
    lf = submarine_location_factor(
        topography=SubmarineTopography.LOW,
        situation=SubmarineSituation.BURIED,
        wind_wave_rating=1,
        combined_wave_energy_intensity=CombinedWaveEnergyIntensity.LOW,
        is_landlocked=True,
    )
    assert lf >= 0.1

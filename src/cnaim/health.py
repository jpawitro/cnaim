"""Health-score and PoF helper formulas aligned with CNAIM equations."""

from __future__ import annotations

import math
from dataclasses import dataclass

HEALTH_NEW_ASSET = 0.5
HEALTH_AT_EXPECTED_LIFE = 5.5
HEALTH_MIN = 0.5
HEALTH_MAX = 10.0
HEALTH_FUTURE_MAX = 15.0


@dataclass(frozen=True)
class ConditionModifier:
    """Condition factor with cap and collar constraints."""

    factor: float
    cap: float
    collar: float


def beta_1(expected_life_years: float) -> float:
    r"""Return CNAIM initial ageing rate $\beta_1$.

    Equation:
    $\beta_1 = \ln(HS_{EL} / HS_{new}) / EL$

    Where:
    - $HS_{EL}=5.5$ is health score at expected life.
    - $HS_{new}=0.5$ is health score of a new asset.
    - $EL$ is expected life in years after duty/location adjustments.
    """
    if expected_life_years <= 0:
        raise ValueError("expected_life_years must be positive")

    return math.log(HEALTH_AT_EXPECTED_LIFE / HEALTH_NEW_ASSET) / expected_life_years


def beta_2(current_health_score: float, age_years: float) -> float:
    r"""Return forecast ageing rate $\beta_2$ from current condition.

    Equation:
    $\beta_2 = \ln(HS_{current} / HS_{new}) / Age$
    """
    if current_health_score <= 0:
        raise ValueError("current_health_score must be positive")
    if age_years <= 0:
        raise ValueError("age_years must be positive")

    return math.log(current_health_score / HEALTH_NEW_ASSET) / age_years


def initial_health(b1: float, age_years: float) -> float:
    r"""Return initial health score before condition modifiers.

    Equation:
    $HS_{initial}=HS_{new} \cdot e^{\beta_1\cdot Age}$

    The result is capped at $5.5$ to match CNAIM expected-life limit.
    """
    if age_years < 0:
        raise ValueError("age_years must be non-negative")

    exponent = b1 * age_years
    max_exponent = math.log(HEALTH_AT_EXPECTED_LIFE / HEALTH_NEW_ASSET)
    if exponent >= max_exponent:
        return HEALTH_AT_EXPECTED_LIFE

    return min(HEALTH_AT_EXPECTED_LIFE, HEALTH_NEW_ASSET * math.exp(exponent))


def current_health(
    initial_health_score: float,
    health_score_factor: float,
    health_score_cap: float = HEALTH_MAX,
    health_score_collar: float = HEALTH_MIN,
    reliability_factor: float = 1.0,
) -> float:
    r"""Return current health score after condition and reliability scaling.

    Computation sequence:
    - Raw score: $HS_{initial} \cdot HSF \cdot RF$
    - Apply cap and collar constraints.
    - Clamp to global range $[0.5, 10.0]$.
    """
    score = initial_health_score * health_score_factor * reliability_factor
    score = min(score, health_score_cap)
    score = max(score, health_score_collar)
    score = min(score, HEALTH_MAX)
    score = max(score, HEALTH_MIN)
    return score


def mmi(
    factors: list[float],
    factor_divider_1: float,
    factor_divider_2: float,
    max_no_combined_factors: int,
) -> float:
    """Combine multiple condition factors using CNAIM MMI technique.

    MMI applies two regimes:
    - Degraded factors (>1): use maximum factor plus scaled cumulative excess.
    - Improving factors (<=1): use minimum factor plus a smaller correction.
    """
    if not factors:
        return 1.0

    if any(factor > 1 for factor in factors):
        factors_sorted = sorted(factors, reverse=True)
        var_1 = factors_sorted[0]

        remaining = [factor - 1 for factor in factors_sorted[1:] if factor - 1 > 0]
        if max_no_combined_factors - 1 < 1 or not remaining:
            var_2 = 0.0
        else:
            cumulative = []
            total = 0.0
            for value in remaining:
                total += value
                cumulative.append(total)

            index = min(max_no_combined_factors - 2, len(cumulative) - 1)
            var_2 = cumulative[index]

        var_3 = var_2 / factor_divider_1
        return var_1 + var_3

    factors_sorted = sorted(factors)
    var_1 = factors_sorted[0]
    var_2 = factors_sorted[1] if len(factors_sorted) > 1 else 0.0
    var_3 = (var_2 - 1) / factor_divider_2
    return var_1 + var_3


def health_score_excl_ehv_132kv_tf(
    observed_condition_factor: float, measured_condition_factor: float
) -> float:
    r"""Combine observed and measured condition factors.

    This is the CNAIM non-EHV combiner used by generic assets and the
    transformer vertical slice in this package.

    Rules with divider $d=1.5$:
    - if both factors > 1: $a + (b-1)/d$
    - if only one factor > 1: return the larger factor
    - otherwise: $b + (a-1)/d$

    where $a=max(observed, measured)$ and $b=min(observed, measured)$.
    """
    factor_divider = 1.5
    a = max(observed_condition_factor, measured_condition_factor)
    b = min(observed_condition_factor, measured_condition_factor)

    if a > 1 and b > 1:
        return a + ((b - 1) / factor_divider)
    if a > 1 and b <= 1:
        return a
    return b + ((a - 1) / factor_divider)


def ageing_reduction_factor(current_health_score: float) -> float:
    r"""Return piecewise ageing reduction factor for future PoF projection.

    Piecewise definition:
    - $1.0$ for $HS<2$
    - $((HS-2)/7)+1$ for $2\le HS\le 5.5$
    - $1.5$ for $HS>5.5$
    """
    if current_health_score < 2:
        return 1.0
    if current_health_score <= 5.5:
        return ((current_health_score - 2) / 7) + 1
    return 1.5


def pof_cubic(k_value: float, c_value: float, health_score: float) -> float:
    r"""Return PoF using CNAIM cubic Taylor approximation.

    Equation:
    $PoF = K \cdot (1 + x + x^2/2! + x^3/3!)$
    where $x = C \cdot HS$.
    """
    term = c_value * health_score
    return k_value * (1 + term + (term**2) / math.factorial(2) + (term**3) / math.factorial(3))

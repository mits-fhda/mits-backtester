"""Tests for the metric calculations, using tiny examples you can check by hand."""

import math

import pandas as pd
import pytest

from mits_backtester.metrics import (
    annualized_volatility,
    cagr,
    compute_metrics,
    max_drawdown,
    sharpe_ratio,
    total_return,
)


def test_total_return_gain():
    # 100 -> 150 is a 50% gain.
    assert total_return(pd.Series([100, 120, 150])) == pytest.approx(0.50)


def test_total_return_loss():
    # 200 -> 150 is a 25% loss.
    assert total_return(pd.Series([200, 180, 150])) == pytest.approx(-0.25)


def test_cagr_one_year_equals_total_return():
    # 253 points = 252 daily steps = exactly one year, so CAGR = total return.
    equity = pd.Series([100.0] * 252 + [110.0])
    assert cagr(equity) == pytest.approx(0.10)


def test_cagr_two_years_of_doubling():
    # Doubling over two years: (2) ** (1/2) - 1 = 41.42% per year (not 50%).
    equity = pd.Series([100.0] * 504 + [200.0])
    assert cagr(equity) == pytest.approx(math.sqrt(2) - 1)


def test_cagr_with_custom_periods_per_year():
    # 2 steps with 1 step per "year" -> 2 years. 100 -> 121 means 10% per year.
    assert cagr(pd.Series([100, 110, 121]), periods_per_year=1) == pytest.approx(0.10)


def test_max_drawdown():
    # Peak 120, then falls to 90: 90 / 120 - 1 = -25%.
    # The later dip from 130 to 117 is only -10%, so -25% is the max.
    equity = pd.Series([100, 120, 90, 130, 117])
    assert max_drawdown(equity) == pytest.approx(-0.25)


def test_max_drawdown_is_zero_when_always_rising():
    assert max_drawdown(pd.Series([100, 101, 102, 103])) == 0


def test_annualized_volatility():
    # Daily returns: +10%, -10%, +10%, -10%.
    # Sample std (n-1) of [0.1, -0.1, 0.1, -0.1] = sqrt(0.04 / 3).
    equity = pd.Series([100, 110, 99, 108.9, 98.01])
    expected = math.sqrt(0.04 / 3) * math.sqrt(252)
    assert annualized_volatility(equity) == pytest.approx(expected)


def test_volatility_is_zero_for_constant_returns():
    # Grows exactly 1% every day: no variation at all.
    equity = pd.Series([100 * 1.01 ** i for i in range(10)])
    assert annualized_volatility(equity) == pytest.approx(0, abs=1e-12)


def test_sharpe_ratio():
    # Daily returns: +2%, 0%, +1%. Mean = 1%, sample std = 1%.
    # Sharpe = 0.01 / 0.01 * sqrt(252) = sqrt(252), about 15.87.
    equity = pd.Series([100, 102, 102, 103.02])
    assert sharpe_ratio(equity) == pytest.approx(math.sqrt(252))


def test_sharpe_is_nan_when_returns_never_change():
    # Sitting in cash the whole time: std = 0, so Sharpe is undefined.
    assert math.isnan(sharpe_ratio(pd.Series([100.0, 100.0, 100.0])))


def test_compute_metrics_has_all_keys():
    metrics = compute_metrics(pd.Series([100, 105, 102, 110]))
    assert set(metrics) == {
        "Total Return", "CAGR", "Max Drawdown", "Annualized Volatility", "Sharpe Ratio",
    }

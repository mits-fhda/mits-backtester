"""Tests for the parameter sweep."""

import numpy as np
import pandas as pd

from mits_backtester.sweep import parameter_sweep


def make_prices(n=60, seed=0):
    rng = np.random.default_rng(seed)
    prices = 100 * np.cumprod(1 + rng.normal(0.001, 0.01, n))
    return pd.DataFrame({"Price": prices}, index=pd.bdate_range("2024-01-01", periods=n))


def test_sweep_skips_pairs_where_short_is_not_smaller():
    table, _ = parameter_sweep(make_prices(), short_windows=[5, 10, 20], long_windows=[10, 20])
    pairs = set(zip(table["Short"], table["Long"]))
    assert pairs == {(5, 10), (5, 20), (10, 20)}


def test_sweep_matches_a_single_backtest_on_the_same_dates():
    # With only one long window, the common start is that window's own start,
    # so the sweep's result must equal a normal backtest's result.
    from mits_backtester.engine import run_backtest
    from mits_backtester.metrics import compute_metrics
    from mits_backtester.strategies import compute_signals

    prices = make_prices()
    table, buy_hold = parameter_sweep(prices, short_windows=[5], long_windows=[20])
    results = run_backtest(compute_signals(prices, 5, 20))
    expected = compute_metrics(results["Strategy_Equity"])
    assert table.loc[0, "Sharpe Ratio"] == expected["Sharpe Ratio"]
    assert buy_hold == compute_metrics(results["BuyHold_Equity"])

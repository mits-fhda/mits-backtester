"""Tests for the Monte Carlo simulation and trading costs."""

import numpy as np
import pandas as pd
import pytest

from mits_backtester.engine import run_backtest
from mits_backtester.metrics import cagr, max_drawdown
from mits_backtester.montecarlo import (
    bootstrap_indices,
    equity_paths,
    path_cagrs,
    path_max_drawdowns,
    run_monte_carlo,
    summarize_monte_carlo,
)


def make_results(market_returns, positions):
    """A hand-made run_backtest()-style table."""
    dates = pd.bdate_range("2024-01-01", periods=len(market_returns))
    market = pd.Series(market_returns, index=dates)
    position = pd.Series(positions, index=dates)
    return pd.DataFrame({
        "Market_Return": market,
        "Position": position,
        "Strategy_Return": market * position,
    })


def test_bootstrap_blocks_are_consecutive_days():
    rng = np.random.default_rng(0)
    idx = bootstrap_indices(num_history_days=100, num_paths=5, num_days=30, block_size=10, rng=rng)
    assert idx.shape == (5, 30)
    assert idx.min() >= 0 and idx.max() < 100
    # Inside each 10-day block, each day is the one right after the previous.
    for block in idx.reshape(5, 3, 10).reshape(-1, 10):
        assert list(np.diff(block)) == [1] * 9


def test_bootstrap_trims_to_exact_length():
    rng = np.random.default_rng(0)
    idx = bootstrap_indices(100, num_paths=2, num_days=25, block_size=10, rng=rng)
    assert idx.shape == (2, 25)


def test_bootstrap_rejects_bad_block_size():
    rng = np.random.default_rng(0)
    with pytest.raises(ValueError):
        bootstrap_indices(10, 1, 5, block_size=11, rng=rng)


def test_equity_paths_by_hand():
    # +10% then -10%: 100 -> 110 -> 99.
    equity = equity_paths(np.array([[0.10, -0.10]]), initial_capital=100)
    assert equity[0] == pytest.approx([100, 110, 99])


def test_vectorized_metrics_match_metrics_module():
    # The fast NumPy versions must agree with the pandas versions in metrics.py.
    path = np.array([100, 120, 90, 130, 117.0])
    assert path_max_drawdowns(path[np.newaxis, :])[0] == pytest.approx(max_drawdown(pd.Series(path)))
    assert path_cagrs(path[np.newaxis, :])[0] == pytest.approx(cagr(pd.Series(path)))


def test_strategy_always_in_cash_never_moves():
    # Position 0 every day: every simulated path stays at the starting capital.
    results = make_results([0.0, 0.01, -0.02, 0.03, 0.01, -0.01], [0, 0, 0, 0, 0, 0])
    sims = run_monte_carlo(results, num_paths=50, years=1, block_size=2, initial_capital=1000, seed=1)
    assert np.all(sims["Strategy"]["final_value"] == 1000)
    assert np.all(sims["Strategy"]["max_drawdown"] == 0)


def test_always_invested_strategy_matches_buy_and_hold():
    # Same random dates are used for both, so identical returns give identical paths.
    results = make_results([0.0, 0.01, -0.02, 0.03, 0.01, -0.01], [1, 1, 1, 1, 1, 1])
    sims = run_monte_carlo(results, num_paths=50, years=1, block_size=2, seed=1)
    assert np.allclose(sims["Strategy"]["equity"], sims["Buy & Hold"]["equity"])


def test_seed_makes_results_repeatable():
    results = make_results([0.0, 0.01, -0.02, 0.03, 0.01, -0.01], [1, 0, 1, 1, 0, 1])
    a = run_monte_carlo(results, num_paths=20, years=1, block_size=2, seed=7)
    b = run_monte_carlo(results, num_paths=20, years=1, block_size=2, seed=7)
    assert np.array_equal(a["Strategy"]["equity"], b["Strategy"]["equity"])


def test_summary_probabilities():
    # Market only goes up, strategy is always in cash:
    # buy & hold never loses money, and the strategy never beats it.
    results = make_results([0.0, 0.01, 0.02, 0.01], [0, 0, 0, 0])
    sims = run_monte_carlo(results, num_paths=30, years=1, block_size=1, initial_capital=100, seed=3)
    summary = summarize_monte_carlo(sims, initial_capital=100)
    assert summary["Buy & Hold"]["Chance of Losing Money"] == 0
    assert summary["Chance Strategy Beats Buy & Hold"] == 0


def test_trading_cost_charged_on_each_buy_and_sell():
    # Flat prices, so the only thing that changes the strategy's value is costs.
    dates = pd.bdate_range("2024-01-01", periods=5)
    signals = pd.DataFrame({"Price": [100.0] * 5, "Signal": [1, 1, 0, 0, 0]}, index=dates)
    results = run_backtest(signals, initial_capital=1000, cost_per_trade=0.01)
    # Positions: 0, 1, 1, 0, 0 -> one buy and one sell, each costing 1%.
    assert results["Strategy_Equity"].iloc[-1] == pytest.approx(1000 * 0.99 * 0.99)

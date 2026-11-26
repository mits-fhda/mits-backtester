"""Tests for the extra strategies and the strategy leaderboard, using tiny examples."""

import numpy as np
import pandas as pd
import pytest

from mits_backtester.compare import compare_strategies
from mits_backtester.strategies import (
    STRATEGIES,
    mean_reversion_signals,
    momentum_signals,
    volatility_target_signals,
)


def make_prices(values):
    return pd.DataFrame({"Price": values}, index=pd.bdate_range("2024-01-01", periods=len(values)))


def test_momentum_holds_after_a_rise_and_exits_after_a_fall():
    # lookback=3, skip=1: compare the price 1 day ago with the price 3 days ago.
    prices = make_prices([10, 11, 12, 13, 12, 11, 10])
    signals = momentum_signals(prices, lookback=3, skip=1)
    # Day 3: 12 vs 10 -> up -> 1. Day 6: 11 vs 13 -> down -> 0.
    assert signals["Signal"].iloc[3] == 1
    assert signals["Signal"].iloc[6] == 0
    assert signals["Signal"].iloc[:3].isna().all()   # warm-up


def test_mean_reversion_buys_only_when_far_below_average():
    prices = make_prices([10, 10, 10, 10, 10, 10, 10, 10, 10, 6])
    signals = mean_reversion_signals(prices, window=5, entry_z=-1.0)
    assert signals["Signal"].iloc[-1] == 1    # sudden drop -> oversold -> buy
    # Before the drop the price never moves, so std = 0 and z is undefined (no position).
    assert signals["Signal"].iloc[5] != 1


def test_volatility_target_cuts_position_when_markets_get_wild():
    rng = np.random.default_rng(0)
    calm = rng.normal(0, 0.005, 60)     # about 8% yearly volatility
    wild = rng.normal(0, 0.04, 60)      # about 63% yearly volatility
    prices = make_prices(100 * np.cumprod(1 + np.concatenate([calm, wild])))
    signals = volatility_target_signals(prices, target_vol=0.15, window=20)
    assert signals["Signal"].iloc[55] == 1.0        # calm: full position (capped at 100%)
    assert signals["Signal"].iloc[-1] < 0.5          # wild: much smaller position
    assert signals["Signal"].max() <= 1.0            # never uses leverage


@pytest.mark.parametrize("key", list(STRATEGIES))
def test_every_strategy_follows_the_contract(key):
    rng = np.random.default_rng(1)
    prices = make_prices(100 * np.cumprod(1 + rng.normal(0.0005, 0.01, 400)))
    signals = STRATEGIES[key]["function"](prices)
    valid = signals["Signal"].dropna()
    assert len(valid) > 0
    assert ((valid >= 0) & (valid <= 1)).all()


def test_leaderboard_scores_everyone_on_the_same_dates():
    rng = np.random.default_rng(2)
    prices = make_prices(100 * np.cumprod(1 + rng.normal(0.0005, 0.01, 400)))
    table, curves = compare_strategies(prices, initial_capital=1000)
    assert set(table.index) == {info["label"] for info in STRATEGIES.values()} | {"Buy & Hold"}
    assert (curves.iloc[0] == 1000).all()           # everyone starts with the same money
    assert not curves.isna().any().any()            # and covers the same dates
    assert table.loc["Buy & Hold", "Beta"] == pytest.approx(1.0)

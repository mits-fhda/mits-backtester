"""Tests for data loading, signals, and the look-ahead-safe backtest engine."""

import pandas as pd
import pytest

from mits_backtester.data import load_data
from mits_backtester.engine import count_trades, run_backtest
from mits_backtester.strategies import compute_signals


def make_signals(prices, signal):
    """Build a tiny hand-made 'signals' table without running a real strategy."""
    dates = pd.bdate_range("2024-01-01", periods=len(prices))
    return pd.DataFrame({"Price": prices, "Signal": signal}, index=dates)


def test_position_uses_previous_days_signal():
    # The signal turns on at day 1's close, so we are only invested from day 2.
    signals = make_signals([100, 110, 121, 133.1], [0, 1, 1, 1])
    results = run_backtest(signals)
    assert list(results["Position"]) == [0, 0, 1, 1]


def test_no_look_ahead_strategy_misses_the_day_the_signal_appears():
    # Price jumps +50% on day 1, and the signal also turns on at day 1's close.
    # A correct backtest has to miss that jump, since nobody could have known it was coming.
    signals = make_signals([100, 150, 150], [0, 1, 1])
    results = run_backtest(signals, initial_capital=1000)
    assert results["Strategy_Equity"].iloc[-1] == pytest.approx(1000)
    assert results["BuyHold_Equity"].iloc[-1] == pytest.approx(1500)


def test_strategy_earns_market_return_when_invested():
    signals = make_signals([100, 100, 110, 121], [1, 1, 1, 1])
    results = run_backtest(signals, initial_capital=1000)
    # Invested from day 1 onward: 100 -> 121 is +21%.
    assert results["Strategy_Equity"].iloc[-1] == pytest.approx(1210)


def test_warm_up_rows_are_dropped_so_both_start_together():
    signals = make_signals([90, 95, 100, 110], [float("nan"), float("nan"), 1, 1])
    results = run_backtest(signals, initial_capital=1000)
    assert len(results) == 2
    assert results["Strategy_Equity"].iloc[0] == results["BuyHold_Equity"].iloc[0] == 1000


def test_count_trades():
    assert count_trades(pd.Series([0, 1, 1, 0, 0, 1])) == 3


def test_moving_average_signal():
    # Prices rise steadily, so the 2-day average stays above the 3-day average.
    prices = make_signals([1, 2, 3, 4, 5], [0] * 5)[["Price"]]
    signals = compute_signals(prices, short_window=2, long_window=3)
    assert signals["Line: 2-day average"].iloc[-1] == pytest.approx(4.5)   # (4 + 5) / 2
    assert signals["Line: 3-day average"].iloc[-1] == pytest.approx(4.0)    # (3 + 4 + 5) / 3
    assert signals["Signal"].isna().sum() == 2                    # first 2 days: warm-up
    assert list(signals["Signal"].dropna()) == [1, 1, 1]


def test_short_window_must_be_smaller():
    prices = make_signals([1, 2, 3, 4, 5], [0] * 5)[["Price"]]
    with pytest.raises(ValueError):
        compute_signals(prices, short_window=3, long_window=2)


def test_load_data_sorts_and_prefers_adj_close(tmp_path):
    csv = tmp_path / "prices.csv"
    csv.write_text(
        "Date,Open,High,Low,Close,Adj Close,Volume\n"
        "2024-01-03,1,1,1,20,19,100\n"
        "2024-01-02,1,1,1,10,9,100\n"
        "2024-01-04,1,1,1,null,null,100\n"
    )
    df = load_data(csv)
    assert list(df.index.strftime("%Y-%m-%d")) == ["2024-01-02", "2024-01-03"]
    assert list(df["Price"]) == [9, 19]   # Adj Close used, "null" row dropped


def test_load_data_falls_back_to_close(tmp_path):
    csv = tmp_path / "prices.csv"
    csv.write_text("Date,Close\n2024-01-02,10\n2024-01-03,11\n")
    assert list(load_data(csv)["Price"]) == [10, 11]

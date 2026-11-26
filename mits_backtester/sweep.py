"""The luck check: is 50/200 actually special, or did it just happen to work?

This runs the moving-average strategy with lots of different window pairs and
compares them. If only one exact pair looks good and its neighbors look bad,
the result was probably luck, and it probably won't repeat. People call that
overfitting. If a whole group of similar settings all do about as well, the
idea itself is more likely to be real.
"""

import pandas as pd

from mits_backtester.engine import run_backtest
from mits_backtester.metrics import compute_metrics
from mits_backtester.strategies import compute_signals

DEFAULT_SHORT_WINDOWS = [10, 20, 30, 50, 75, 100]
DEFAULT_LONG_WINDOWS = [100, 150, 200, 250, 300]


def parameter_sweep(prices, short_windows=DEFAULT_SHORT_WINDOWS,
                    long_windows=DEFAULT_LONG_WINDOWS, cost_per_trade=0.0):
    """Backtest every (short, long) pair and score each one.

    To keep it fair, every pair is scored over the same dates, starting once
    even the longest window has enough history. Otherwise a 100-day average
    would get a 200-day head start on a 300-day one.

    Returns a table with one row per pair (Short, Long, then every metric),
    plus buy-and-hold's metrics over the same dates to compare against.
    """
    pairs = [(s, l) for s in short_windows for l in long_windows if s < l]
    if not pairs:
        raise ValueError("No valid (short, long) pairs: every short window must be < some long window")

    # The first date when even the longest moving average has a value.
    common_start = prices.index[max(long_windows) - 1]

    rows = []
    for short, long in pairs:
        signals = compute_signals(prices, short_window=short, long_window=long)
        results = run_backtest(signals, cost_per_trade=cost_per_trade)
        # The metrics only care about how the value changes, not where it
        # started, so we can just chop the curve at the shared start date.
        equity = results.loc[common_start:, "Strategy_Equity"]
        rows.append({"Short": short, "Long": long, **compute_metrics(equity)})

    buy_hold_equity = results.loc[common_start:, "BuyHold_Equity"]
    return pd.DataFrame(rows), compute_metrics(buy_hold_equity)

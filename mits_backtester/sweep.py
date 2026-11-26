"""Parameter sweep: is 50/200 actually special, or just lucky?

Run the same strategy with many different window pairs and compare. If only
one exact pair looks good and its neighbors look bad, that's a warning sign
of *overfitting*: the result is probably luck that won't repeat. If a whole
region of nearby settings performs similarly, the idea is more robust.
"""

import pandas as pd

from mits_backtester.engine import run_backtest
from mits_backtester.metrics import compute_metrics
from mits_backtester.strategies import compute_signals

DEFAULT_SHORT_WINDOWS = [10, 20, 30, 50, 75, 100]
DEFAULT_LONG_WINDOWS = [100, 150, 200, 250, 300]


def parameter_sweep(prices, short_windows=DEFAULT_SHORT_WINDOWS,
                    long_windows=DEFAULT_LONG_WINDOWS, cost_per_trade=0.0):
    """Backtest every (short, long) pair and return one row of metrics per pair.

    To compare fairly, every pair is scored over the SAME dates: starting once
    the LONGEST window has enough history. (Otherwise a 100-day average would
    get a head start of 200 extra days over a 300-day average.)

    Returns two things:
      * a DataFrame with columns Short, Long, and every metric
      * a dictionary of buy-and-hold's metrics over the same dates, as a benchmark
    """
    pairs = [(s, l) for s in short_windows for l in long_windows if s < l]
    if not pairs:
        raise ValueError("No valid (short, long) pairs: every short window must be < some long window")

    # The first date on which even the longest moving average exists.
    common_start = prices.index[max(long_windows) - 1]

    rows = []
    for short, long in pairs:
        signals = compute_signals(prices, short_window=short, long_window=long)
        results = run_backtest(signals, cost_per_trade=cost_per_trade)
        # Metrics only depend on the equity curve's shape, so we can simply
        # cut it at the common start date and score what's left.
        equity = results.loc[common_start:, "Strategy_Equity"]
        rows.append({"Short": short, "Long": long, **compute_metrics(equity)})

    buy_hold_equity = results.loc[common_start:, "BuyHold_Equity"]
    return pd.DataFrame(rows), compute_metrics(buy_hold_equity)

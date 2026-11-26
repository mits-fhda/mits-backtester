"""Trading strategies.

Every strategy follows the same simple contract, so new ones can be added
next to the existing one:

    input:  a DataFrame from load_data() (it has a "Price" column)
    output: a copy of that DataFrame with a "Signal" column added, where
              1   = we want to own the stock
              0   = we want to hold cash
              NaN = not enough history yet to decide (the "warm-up" period)

A signal on a given day uses only information available at that day's close.
The backtest engine, not the strategy, is responsible for waiting until the
next day to act on it.
"""

import pandas as pd


def compute_signals(prices, short_window=50, long_window=200):
    """Moving-average crossover strategy.

    Hold the stock while the short moving average is above the long moving
    average (an uptrend); otherwise hold cash.
    """
    if short_window < 1 or long_window < 1:
        raise ValueError("Moving-average windows must be at least 1 day")
    if short_window >= long_window:
        raise ValueError("The short window must be smaller than the long window")
    if len(prices) <= long_window:
        raise ValueError(
            f"Need more than {long_window} rows of data for a {long_window}-day average "
            f"(got {len(prices)})"
        )

    df = prices.copy()

    # Rolling mean = the average of the last N closing prices, recalculated every day.
    # The first N-1 days have no value (NaN) because there isn't enough history yet.
    df["SMA_short"] = df["Price"].rolling(window=short_window).mean()
    df["SMA_long"] = df["Price"].rolling(window=long_window).mean()

    df["Signal"] = (df["SMA_short"] > df["SMA_long"]).astype(float)

    # During warm-up the comparison above is meaningless, so mark it as "unknown".
    df.loc[df["SMA_long"].isna(), "Signal"] = float("nan")

    return df


# A lookup table of available strategies. Adding a new strategy later means
# writing a function with the same contract and registering it here.
STRATEGIES = {
    "sma_crossover": compute_signals,
}

"""Trading strategies.

Every strategy follows the same simple contract, so they're interchangeable:

    input:  a DataFrame from load_data() (it has a "Price" column),
            plus the strategy's own settings as keyword arguments
    output: a copy of that DataFrame with a "Signal" column added:
              1.0        = fully invested in the stock
              0.0        = all cash
              in between = partly invested (e.g. 0.6 = 60% stock, 40% cash)
              NaN        = not enough history yet to decide (the "warm-up")

    Optional: any column whose name starts with "Line: " is drawn on the
    price chart (e.g. "Line: 50-day average").

A signal on a given day uses only information available at that day's close.
The backtest engine, not the strategy, is responsible for waiting until the
next day to act on it.
"""

import math

TRADING_DAYS_PER_YEAR = 252


def _check_history(prices, needed):
    if len(prices) <= needed:
        raise ValueError(f"Need more than {needed} rows of price data (got {len(prices)})")


def compute_signals(prices, short_window=50, long_window=200):
    """Moving-average crossover (trend following).

    Hold the stock while the short moving average is above the long moving
    average (an uptrend); otherwise hold cash.
    """
    if short_window < 1 or long_window < 1:
        raise ValueError("Moving-average windows must be at least 1 day")
    if short_window >= long_window:
        raise ValueError("The short window must be smaller than the long window")
    _check_history(prices, long_window)

    df = prices.copy()

    # Rolling mean = the average of the last N closing prices, recalculated every day.
    # The first N-1 days have no value (NaN) because there isn't enough history yet.
    short_average = df["Price"].rolling(window=short_window).mean()
    long_average = df["Price"].rolling(window=long_window).mean()
    df[f"Line: {short_window}-day average"] = short_average
    df[f"Line: {long_window}-day average"] = long_average

    df["Signal"] = (short_average > long_average).astype(float)

    # During warm-up the comparison above is meaningless, so mark it as "unknown".
    df.loc[long_average.isna(), "Signal"] = float("nan")
    return df


def momentum_signals(prices, lookback=252, skip=21):
    """Time-series momentum, the "12-minus-1 month" signal from academic research.

    Own the stock if it went UP over the past `lookback` days (about a year),
    ignoring the most recent `skip` days (about a month); otherwise hold cash.

    Why skip the last month? Researchers found that very short-term moves tend
    to partly reverse, so the most recent month adds noise to the signal.
    """
    if lookback < 2 or skip < 0 or skip >= lookback:
        raise ValueError("Need lookback >= 2 and 0 <= skip < lookback")
    _check_history(prices, lookback)

    df = prices.copy()
    # Return from `lookback` days ago up to `skip` days ago.
    past_return = df["Price"].shift(skip) / df["Price"].shift(lookback) - 1

    df["Signal"] = (past_return > 0).astype(float)
    df.loc[past_return.isna(), "Signal"] = float("nan")
    return df


def mean_reversion_signals(prices, window=20, entry_z=-1.0):
    """Mean reversion: buy when the price is unusually far BELOW its recent average.

        z-score = (price - 20-day average) / 20-day standard deviation

    A z-score of -1 means the price is one "typical move" below its average.
    The bet is that it will snap back up, so we hold the stock while
    z < entry_z and hold cash otherwise.
    """
    if window < 2:
        raise ValueError("The window must be at least 2 days")
    if entry_z >= 0:
        raise ValueError("entry_z should be negative (how far below average to buy)")
    _check_history(prices, window)

    df = prices.copy()
    average = df["Price"].rolling(window).mean()
    std = df["Price"].rolling(window).std()
    z_score = (df["Price"] - average) / std

    df[f"Line: {window}-day average"] = average
    df[f"Line: buy zone ({entry_z:g} std)"] = average + entry_z * std

    df["Signal"] = (z_score < entry_z).astype(float)
    df.loc[z_score.isna(), "Signal"] = float("nan")
    return df


def volatility_target_signals(prices, target_vol=0.15, window=20):
    """Volatility targeting: always invested, but sized to keep risk steady.

        recent volatility = std of the last 20 daily returns * sqrt(252)
        position          = target volatility / recent volatility  (max 100%)

    When markets are calm we hold the full position; when they get wild
    (volatility doubles) we cut the position in half. This works because
    volatility clusters: wild days tend to be followed by more wild days,
    which is exactly when crashes happen. Scaling positions by volatility is
    a building block of many hedge-fund strategies (e.g. "risk parity").
    """
    if target_vol <= 0:
        raise ValueError("target_vol must be positive, e.g. 0.15 for 15%")
    if window < 2:
        raise ValueError("The window must be at least 2 days")
    _check_history(prices, window)

    df = prices.copy()
    recent_vol = df["Price"].pct_change().rolling(window).std() * math.sqrt(TRADING_DAYS_PER_YEAR)

    # No leverage: never invest more than 100% of the portfolio.
    df["Signal"] = (target_vol / recent_vol).clip(upper=1.0)
    return df


# Every available strategy. To add one: write a function that follows the
# contract at the top of this file, then add it here.
STRATEGIES = {
    "sma": {"label": "Moving-average crossover", "function": compute_signals},
    "momentum": {"label": "Time-series momentum", "function": momentum_signals},
    "mean_reversion": {"label": "Mean reversion", "function": mean_reversion_signals},
    "vol_target": {"label": "Volatility targeting", "function": volatility_target_signals},
}

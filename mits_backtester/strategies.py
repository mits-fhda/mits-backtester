"""The trading strategies.

Every strategy works the same way, which is what lets you swap one for
another. It takes the price table from load_data() plus its own settings, and
hands back a copy of the table with a "Signal" column added. The signal says
how much of the stock to own each day:

    1.0         all in
    0.0         all cash
    in between  partly invested, so 0.6 means 60% stock and 40% cash
    NaN         not enough history to decide yet

A strategy can also add columns whose names start with "Line: ", like
"Line: 50-day average". Those get drawn on the price chart.

A strategy should only ever use prices up to the day it's deciding on. It
doesn't need to worry about waiting a day before trading, because the engine
handles that.
"""

import math

TRADING_DAYS_PER_YEAR = 252


def _check_history(prices, needed):
    if len(prices) <= needed:
        raise ValueError(f"Need more than {needed} rows of price data (got {len(prices)})")


def compute_signals(prices, short_window=50, long_window=200):
    """Moving-average crossover, the classic trend-following rule.

    Own the stock while the short-term average price is above the long-term
    one, which usually means prices are trending up. Otherwise, sit in cash.
    """
    if short_window < 1 or long_window < 1:
        raise ValueError("Moving-average windows must be at least 1 day")
    if short_window >= long_window:
        raise ValueError("The short window must be smaller than the long window")
    _check_history(prices, long_window)

    df = prices.copy()

    # A rolling mean is the average of the last N prices, recalculated every day.
    # It's NaN for the first N-1 days, since there aren't N prices to average yet.
    short_average = df["Price"].rolling(window=short_window).mean()
    long_average = df["Price"].rolling(window=long_window).mean()
    df[f"Line: {short_window}-day average"] = short_average
    df[f"Line: {long_window}-day average"] = long_average

    df["Signal"] = (short_average > long_average).astype(float)

    # Before the long average exists, the comparison above doesn't mean anything.
    df.loc[long_average.isna(), "Signal"] = float("nan")
    return df


def momentum_signals(prices, lookback=252, skip=21):
    """Time-series momentum, often called "12 minus 1" in the research.

    Own the stock if it went up over roughly the past year (`lookback` days),
    leaving out the most recent month or so (`skip` days). Otherwise, sit in
    cash. The last month gets left out because researchers found that very
    short-term moves tend to partly reverse, so including it adds noise.
    """
    if lookback < 2 or skip < 0 or skip >= lookback:
        raise ValueError("Need lookback >= 2 and 0 <= skip < lookback")
    _check_history(prices, lookback)

    df = prices.copy()
    # The return from `lookback` days ago up to `skip` days ago.
    past_return = df["Price"].shift(skip) / df["Price"].shift(lookback) - 1

    df["Signal"] = (past_return > 0).astype(float)
    df.loc[past_return.isna(), "Signal"] = float("nan")
    return df


def mean_reversion_signals(prices, window=20, entry_z=-1.0):
    """Mean reversion: buy when the price drops unusually far below its recent average.

    "Unusually far" is measured with a z-score:

        z-score = (price - 20-day average) / 20-day standard deviation

    A z-score of -1 means the price is one typical day-to-day swing below its
    average. The bet is that it bounces back, so we own the stock while the
    z-score is below `entry_z` and sit in cash the rest of the time.
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
    """Volatility targeting: always invested, but own less when the market gets jumpy.

        recent volatility = std of the last 20 daily returns * sqrt(252)
        position          = target volatility / recent volatility, capped at 100%

    In calm markets this holds the full position. If volatility doubles, it
    holds half. The idea works because wild days tend to come in clusters,
    and crashes happen during those clusters. Sizing positions by volatility
    shows up in a lot of hedge-fund strategies, "risk parity" being a famous one.
    """
    if target_vol <= 0:
        raise ValueError("target_vol must be positive, e.g. 0.15 for 15%")
    if window < 2:
        raise ValueError("The window must be at least 2 days")
    _check_history(prices, window)

    df = prices.copy()
    recent_vol = df["Price"].pct_change().rolling(window).std() * math.sqrt(TRADING_DAYS_PER_YEAR)

    # Never go above 100%. Investing more than you have would mean borrowing.
    df["Signal"] = (target_vol / recent_vol).clip(upper=1.0)
    return df


# Every strategy the backtester knows about. To add your own, write a function
# that works like the ones above and add a line for it here.
STRATEGIES = {
    "sma": {"label": "Moving-average crossover", "function": compute_signals},
    "momentum": {"label": "Time-series momentum", "function": momentum_signals},
    "mean_reversion": {"label": "Mean reversion", "function": mean_reversion_signals},
    "vol_target": {"label": "Volatility targeting", "function": volatility_target_signals},
}

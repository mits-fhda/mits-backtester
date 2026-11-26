"""Performance metrics.

Every function takes an *equity curve*: a pandas Series of portfolio values,
one per trading day (e.g. 10000, 10050, 9980, ...). Working from the equity
curve means the same functions score any strategy, including buy-and-hold.
"""

import math

TRADING_DAYS_PER_YEAR = 252


def daily_returns(equity):
    """Percentage change from one day to the next (the first day has none)."""
    return equity.pct_change().dropna()


def total_return(equity):
    """Total return = ending value / starting value - 1."""
    return equity.iloc[-1] / equity.iloc[0] - 1


def cagr(equity, periods_per_year=TRADING_DAYS_PER_YEAR):
    """Compound annual growth rate: the steady yearly return that would turn
    the starting value into the ending value.

        CAGR = (ending / starting) ** (1 / years) - 1
        years = number of daily steps / 252
    """
    years = (len(equity) - 1) / periods_per_year
    if years <= 0:
        raise ValueError("Need at least two data points to compute CAGR")
    return (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1


def max_drawdown(equity):
    """Largest peak-to-trough drop, as a negative number (e.g. -0.34 = -34%).

        drawdown on each day = value / highest value so far - 1
        max drawdown         = the most negative of those
    """
    running_peak = equity.cummax()
    drawdowns = equity / running_peak - 1
    return drawdowns.min()


def annualized_volatility(equity, periods_per_year=TRADING_DAYS_PER_YEAR):
    """How much returns bounce around, scaled to a year.

        volatility = standard deviation of daily returns * sqrt(252)

    We multiply by sqrt(252), not 252, because variance (not standard
    deviation) grows in proportion to time.
    """
    return daily_returns(equity).std() * math.sqrt(periods_per_year)


def sharpe_ratio(equity, risk_free_rate=0.0, periods_per_year=TRADING_DAYS_PER_YEAR):
    """Return per unit of risk (annualized).

        Sharpe = mean(daily excess return) / std(daily return) * sqrt(252)

    With a 0% risk-free rate the excess return is just the daily return.
    Returns NaN if returns never change (std = 0), since the ratio is undefined.
    """
    returns = daily_returns(equity)
    excess = returns - risk_free_rate / periods_per_year
    std = returns.std()
    if std == 0 or math.isnan(std):
        return float("nan")
    return excess.mean() / std * math.sqrt(periods_per_year)


def compute_metrics(equity):
    """All the metrics for one equity curve, as a dictionary."""
    return {
        "Total Return": total_return(equity),
        "CAGR": cagr(equity),
        "Max Drawdown": max_drawdown(equity),
        "Annualized Volatility": annualized_volatility(equity),
        "Sharpe Ratio": sharpe_ratio(equity),
    }

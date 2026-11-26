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


def sortino_ratio(equity, periods_per_year=TRADING_DAYS_PER_YEAR):
    """Like Sharpe, but only counts DOWNSIDE volatility as risk.

        downside deviation = sqrt(mean(min(daily return, 0) ** 2))
        Sortino = mean(daily return) / downside deviation * sqrt(252)

    Investors don't mind big UP days, so this punishes only the bad bumps.
    """
    returns = daily_returns(equity)
    downside_deviation = math.sqrt((returns.clip(upper=0) ** 2).mean())
    if downside_deviation == 0:
        return float("nan")
    return returns.mean() / downside_deviation * math.sqrt(periods_per_year)


def calmar_ratio(equity, periods_per_year=TRADING_DAYS_PER_YEAR):
    """Yearly return per unit of worst-case pain: CAGR / |max drawdown|."""
    drawdown = max_drawdown(equity)
    if drawdown == 0:
        return float("nan")
    return cagr(equity, periods_per_year) / abs(drawdown)


def value_at_risk(equity, confidence=0.95):
    """1-day historical Value-at-Risk (VaR), as a negative number.

    "On 95% of days, we lost less than this." It is simply the 5th percentile
    of all the daily returns. E.g. -0.02 means a 1-in-20 bad day loses 2%+.
    """
    return daily_returns(equity).quantile(1 - confidence)


def conditional_value_at_risk(equity, confidence=0.95):
    """CVaR, also called Expected Shortfall: the AVERAGE loss on the worst 5% of days.

    VaR tells you where the bad tail starts; CVaR tells you how bad it gets
    once you're in it, which is why regulators now prefer it.
    """
    returns = daily_returns(equity)
    var = returns.quantile(1 - confidence)
    return returns[returns <= var].mean()


def beta_and_alpha(equity, benchmark_equity, periods_per_year=TRADING_DAYS_PER_YEAR):
    """How much of the strategy is just the market (beta), and what's left (alpha).

        beta  = covariance(strategy, market) / variance(market)
        alpha = (mean strategy return - beta * mean market return) * 252

    Beta 0.5 means the strategy tends to move half as much as the market.
    Alpha is the yearly return NOT explained by riding the market: the part
    a quant fund gets paid for. (Simple version, 0% risk-free rate.)
    """
    returns = daily_returns(equity)
    market = daily_returns(benchmark_equity)
    beta = returns.cov(market) / market.var()
    alpha = (returns.mean() - beta * market.mean()) * periods_per_year
    return beta, alpha


# Metrics shown as plain numbers; every other metric is shown as a percentage.
RATIO_METRICS = {"Sharpe Ratio", "Sortino Ratio", "Calmar Ratio", "Beta"}


def compute_metrics(equity, benchmark_equity=None):
    """All the metrics for one equity curve, as a dictionary.

    Pass `benchmark_equity` (e.g. buy-and-hold) to also get beta and alpha.
    """
    metrics = {
        "Total Return": total_return(equity),
        "CAGR": cagr(equity),
        "Max Drawdown": max_drawdown(equity),
        "Annualized Volatility": annualized_volatility(equity),
        "Sharpe Ratio": sharpe_ratio(equity),
        "Sortino Ratio": sortino_ratio(equity),
        "Calmar Ratio": calmar_ratio(equity),
        "Daily VaR (95%)": value_at_risk(equity),
        "Daily CVaR (95%)": conditional_value_at_risk(equity),
    }
    if benchmark_equity is not None:
        metrics["Beta"], metrics["Alpha"] = beta_and_alpha(equity, benchmark_equity)
    return metrics

"""Performance metrics.

Every function here takes an equity curve, which is just the portfolio's value
on each trading day (10000, 10050, 9980, and so on). Since everything works off
that one series, the same functions can score any strategy, buy-and-hold included.
"""

import math

TRADING_DAYS_PER_YEAR = 252


def daily_returns(equity):
    """How much the portfolio changed each day, as a fraction (0.01 means up 1%)."""
    return equity.pct_change().dropna()


def total_return(equity):
    """How much the money grew overall: ending value / starting value - 1."""
    return equity.iloc[-1] / equity.iloc[0] - 1


def cagr(equity, periods_per_year=TRADING_DAYS_PER_YEAR):
    """Compound annual growth rate, or the average yearly return.

    It's the steady yearly growth rate that would get you from the starting
    value to the ending value:

        CAGR = (ending / starting) ** (1 / years) - 1
        years = number of trading days / 252
    """
    years = (len(equity) - 1) / periods_per_year
    if years <= 0:
        raise ValueError("Need at least two data points to compute CAGR")
    return (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1


def max_drawdown(equity):
    """The worst drop from a high point, as a negative number (-0.34 means -34%).

    For each day, compare the value with the highest it's been so far. The
    max drawdown is the biggest gap you'd have seen:

        drawdown on a day = value / highest value so far - 1
    """
    running_peak = equity.cummax()
    drawdowns = equity / running_peak - 1
    return drawdowns.min()


def annualized_volatility(equity, periods_per_year=TRADING_DAYS_PER_YEAR):
    """How bumpy the ride was, scaled up to a year.

        volatility = standard deviation of daily returns * sqrt(252)

    It's sqrt(252) and not 252 because it's the variance that grows in step
    with time, and standard deviation is the square root of variance.
    """
    return daily_returns(equity).std() * math.sqrt(periods_per_year)


def sharpe_ratio(equity, risk_free_rate=0.0, periods_per_year=TRADING_DAYS_PER_YEAR):
    """How much return you got for each unit of bumpiness, scaled to a year.

        Sharpe = mean(daily excess return) / std(daily return) * sqrt(252)

    "Excess" means above what cash would have earned. We assume cash earns 0%,
    so it's just the daily return. If the returns never change at all (say,
    the strategy sat in cash the whole time), the ratio can't be calculated
    and we return NaN.
    """
    returns = daily_returns(equity)
    excess = returns - risk_free_rate / periods_per_year
    std = returns.std()
    if std == 0 or math.isnan(std):
        return float("nan")
    return excess.mean() / std * math.sqrt(periods_per_year)


def sortino_ratio(equity, periods_per_year=TRADING_DAYS_PER_YEAR):
    """Like the Sharpe ratio, except only the down days count as risk.

        downside deviation = sqrt(mean(min(daily return, 0) ** 2))
        Sortino = mean(daily return) / downside deviation * sqrt(252)

    Nobody complains about a big up day, so it makes sense to only penalize
    the bad ones.
    """
    returns = daily_returns(equity)
    downside_deviation = math.sqrt((returns.clip(upper=0) ** 2).mean())
    if downside_deviation == 0:
        return float("nan")
    return returns.mean() / downside_deviation * math.sqrt(periods_per_year)


def calmar_ratio(equity, periods_per_year=TRADING_DAYS_PER_YEAR):
    """Average yearly return divided by the worst drop: CAGR / |max drawdown|."""
    drawdown = max_drawdown(equity)
    if drawdown == 0:
        return float("nan")
    return cagr(equity, periods_per_year) / abs(drawdown)


def value_at_risk(equity, confidence=0.95):
    """One-day Value-at-Risk (VaR), as a negative number.

    On 19 days out of 20, the loss was smaller than this. It's just the 5th
    percentile of the daily returns, so -0.02 means a 1-in-20 bad day loses
    2% or more.
    """
    return daily_returns(equity).quantile(1 - confidence)


def conditional_value_at_risk(equity, confidence=0.95):
    """CVaR, also called Expected Shortfall: the average loss on the worst 5% of days.

    VaR tells you where the bad days start. CVaR tells you how bad they
    actually get, which is why bank regulators have moved toward using it.
    """
    returns = daily_returns(equity)
    var = returns.quantile(1 - confidence)
    return returns[returns <= var].mean()


def beta_and_alpha(equity, benchmark_equity, periods_per_year=TRADING_DAYS_PER_YEAR):
    """Split a strategy's return into the part that's just the market and the part that isn't.

        beta  = covariance(strategy, market) / variance(market)
        alpha = (mean strategy return - beta * mean market return) * 252

    A beta of 0.5 means the strategy tends to move half as much as the market.
    Alpha is the yearly return left over once you account for that, which is
    the part a fund manager would actually get credit for. This is the simple
    version, with cash earning 0%.
    """
    returns = daily_returns(equity)
    market = daily_returns(benchmark_equity)
    beta = returns.cov(market) / market.var()
    alpha = (returns.mean() - beta * market.mean()) * periods_per_year
    return beta, alpha


# These are shown as plain numbers. Everything else is shown as a percentage.
RATIO_METRICS = {"Sharpe Ratio", "Sortino Ratio", "Calmar Ratio", "Beta"}


def compute_metrics(equity, benchmark_equity=None):
    """Every metric for one equity curve, as a dictionary.

    Beta and alpha need something to compare against, so they're only
    included if you pass `benchmark_equity` (usually buy-and-hold).
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

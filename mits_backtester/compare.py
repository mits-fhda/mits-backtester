"""Strategy leaderboard: run every strategy on the same data and compare them."""

import pandas as pd

from mits_backtester.engine import run_backtest
from mits_backtester.metrics import compute_metrics
from mits_backtester.strategies import STRATEGIES


def compare_strategies(prices, cost_per_trade=0.0, initial_capital=10_000):
    """Backtest every strategy (with its default settings) over the SAME dates.

    Each strategy needs a different amount of warm-up history (momentum needs
    a year, mean reversion only 20 days), so we start them all on the latest
    of their start dates. Otherwise they'd be scored on different periods.

    Returns:
      * table: one row per strategy (plus buy-and-hold), one column per metric
      * equity_curves: one column per strategy, all starting at initial_capital
    """
    backtests = {}
    for info in STRATEGIES.values():
        signals = info["function"](prices)
        backtests[info["label"]] = run_backtest(signals, initial_capital, cost_per_trade)

    common_start = max(results.index[0] for results in backtests.values())

    equity_curves = {}
    exposures = {}
    for label, results in backtests.items():
        equity_curves[label] = results.loc[common_start:, "Strategy_Equity"]
        exposures[label] = results.loc[common_start:, "Position"].mean()
    any_results = next(iter(backtests.values()))
    equity_curves["Buy & Hold"] = any_results.loc[common_start:, "BuyHold_Equity"]
    exposures["Buy & Hold"] = 1.0

    # Rescale so every curve starts at exactly initial_capital on the common date.
    equity_curves = pd.DataFrame(equity_curves)
    equity_curves = equity_curves / equity_curves.iloc[0] * initial_capital

    buy_hold = equity_curves["Buy & Hold"]
    table = pd.DataFrame({
        label: {**compute_metrics(equity_curves[label], benchmark_equity=buy_hold),
                "Avg Exposure": exposures[label]}
        for label in equity_curves.columns
    }).T
    return table, equity_curves

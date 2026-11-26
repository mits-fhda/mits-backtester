"""Monte Carlo risk simulation using a block bootstrap.

A backtest shows ONE path: the one history actually took. Monte Carlo asks
"what else could plausibly have happened?" by building thousands of
alternative histories out of pieces of the real one.

How we build one simulated path (a "block bootstrap"):
  1. Cut the historical daily returns into random chunks ("blocks") of,
     say, 20 consecutive trading days.
  2. Glue randomly chosen blocks end to end until the path is long enough.

Why blocks instead of single days? Markets have streaks: calm periods and
panicky periods cluster together. Picking single days at random would
shuffle that away and understate how bad a crash can get. Keeping 20-day
chunks preserves some of that clustering. (block_size=1 gives the simple
version where every day is drawn independently.)

Strategy and buy-and-hold are resampled with the SAME random dates, so in
every simulated history they face exactly the same market.
"""

import numpy as np

from mits_backtester.metrics import TRADING_DAYS_PER_YEAR


def bootstrap_indices(num_history_days, num_paths, num_days, block_size, rng):
    """Return a (num_paths x num_days) array of row numbers into the history.

    Each row is one simulated path made of random blocks of consecutive days.
    """
    if block_size < 1 or block_size > num_history_days:
        raise ValueError("block_size must be between 1 and the number of historical days")

    blocks_per_path = int(np.ceil(num_days / block_size))
    # Random starting day for every block of every path.
    starts = rng.integers(0, num_history_days - block_size + 1,
                          size=(num_paths, blocks_per_path))
    # Expand each start into block_size consecutive days: start, start+1, ...
    offsets = np.arange(block_size)
    indices = starts[:, :, np.newaxis] + offsets            # shape: paths x blocks x block_size
    indices = indices.reshape(num_paths, -1)                # glue blocks end to end
    return indices[:, :num_days]                            # trim to exact length


def equity_paths(returns, initial_capital):
    """Turn a (paths x days) array of daily returns into portfolio values.

    The first column is the starting capital, so the result has days + 1 columns.
    """
    growth = np.cumprod(1 + returns, axis=1)
    start = np.ones((returns.shape[0], 1))
    return initial_capital * np.hstack([start, growth])


def path_max_drawdowns(equity):
    """Max drawdown of every path (same formula as metrics.max_drawdown)."""
    running_peak = np.maximum.accumulate(equity, axis=1)
    return (equity / running_peak - 1).min(axis=1)


def path_cagrs(equity, periods_per_year=TRADING_DAYS_PER_YEAR):
    """CAGR of every path (same formula as metrics.cagr)."""
    years = (equity.shape[1] - 1) / periods_per_year
    return (equity[:, -1] / equity[:, 0]) ** (1 / years) - 1


def run_monte_carlo(results, num_paths=1000, years=10, block_size=20,
                    initial_capital=10_000, seed=None):
    """Simulate many alternative histories for the strategy and buy-and-hold.

    `results` is the output of run_backtest(). Returns a dictionary:
        {"Strategy": {...}, "Buy & Hold": {...}}
    where each inner dict holds "equity" (paths x days array), "final_value",
    "cagr" and "max_drawdown" (one number per path).
    """
    # Skip the first row: its return is a placeholder 0, not a real day.
    history = results.iloc[1:]
    num_days = int(years * TRADING_DAYS_PER_YEAR)

    rng = np.random.default_rng(seed)  # a fixed seed makes results repeatable
    idx = bootstrap_indices(len(history), num_paths, num_days, block_size, rng)

    simulations = {}
    for name, column in [("Strategy", "Strategy_Return"), ("Buy & Hold", "Market_Return")]:
        sampled_returns = history[column].to_numpy()[idx]
        equity = equity_paths(sampled_returns, initial_capital)
        simulations[name] = {
            "equity": equity,
            "final_value": equity[:, -1],
            "cagr": path_cagrs(equity),
            "max_drawdown": path_max_drawdowns(equity),
        }
    return simulations


def summarize_monte_carlo(simulations, initial_capital, drawdown_threshold=-0.30):
    """Key statistics for each simulated strategy, as a dictionary of dictionaries.

    Percentiles: the 5th percentile is a "bad but not worst-case" outcome
    (95% of paths did better); the 50th is the median, a typical outcome.
    """
    summary = {}
    for name, sim in simulations.items():
        summary[name] = {
            "Final Value (5th pct)": np.percentile(sim["final_value"], 5),
            "Final Value (median)": np.percentile(sim["final_value"], 50),
            "Final Value (95th pct)": np.percentile(sim["final_value"], 95),
            "CAGR (5th pct)": np.percentile(sim["cagr"], 5),
            "CAGR (median)": np.percentile(sim["cagr"], 50),
            "Max Drawdown (median)": np.percentile(sim["max_drawdown"], 50),
            "Max Drawdown (5th pct)": np.percentile(sim["max_drawdown"], 5),
            "Chance of Losing Money": np.mean(sim["final_value"] < initial_capital),
            f"Chance of {drawdown_threshold:.0%} Drawdown": np.mean(
                sim["max_drawdown"] <= drawdown_threshold
            ),
        }

    strategy_final = simulations["Strategy"]["final_value"]
    buyhold_final = simulations["Buy & Hold"]["final_value"]
    summary["Chance Strategy Beats Buy & Hold"] = float(np.mean(strategy_final > buyhold_final))
    return summary

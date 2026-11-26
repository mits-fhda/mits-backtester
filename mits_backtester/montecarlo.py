"""Monte Carlo risk simulation.

A backtest only shows the one way history actually played out. This module
asks what else could reasonably have happened, by building thousands of
made-up histories out of pieces of the real one.

To build one made-up history, we pick random 20-day stretches of real daily
returns and glue them end to end until it's long enough. (The technical name
is a "block bootstrap".)

We use 20-day stretches instead of single days because markets have moods.
Calm weeks and panicky weeks come in runs, and if you shuffled individual days
you'd break those runs up and make crashes look milder than they are. Setting
block_size=1 gives you the single-day version if you want to compare.

The strategy and buy-and-hold are always built from the same random stretches,
so in every made-up history they face exactly the same market.
"""

import numpy as np

from mits_backtester.metrics import TRADING_DAYS_PER_YEAR


def bootstrap_indices(num_history_days, num_paths, num_days, block_size, rng):
    """Pick which historical days go into each made-up history.

    Returns a grid of row numbers with one row per history. Each row is made
    of random blocks of consecutive days.
    """
    if block_size < 1 or block_size > num_history_days:
        raise ValueError("block_size must be between 1 and the number of historical days")

    blocks_per_path = int(np.ceil(num_days / block_size))
    # Pick a random starting day for every block in every history.
    starts = rng.integers(0, num_history_days - block_size + 1,
                          size=(num_paths, blocks_per_path))
    # Turn each starting day into a run of consecutive days: start, start+1, start+2, ...
    offsets = np.arange(block_size)
    indices = starts[:, :, np.newaxis] + offsets            # shape: paths x blocks x block_size
    indices = indices.reshape(num_paths, -1)                # put the blocks end to end
    return indices[:, :num_days]                            # cut off any extra days


def equity_paths(returns, initial_capital):
    """Turn each history's daily returns into its portfolio value over time.

    The first column is the starting amount, so there's one more column than
    there are days.
    """
    growth = np.cumprod(1 + returns, axis=1)
    start = np.ones((returns.shape[0], 1))
    return initial_capital * np.hstack([start, growth])


def path_max_drawdowns(equity):
    """The worst drop in every history. Same formula as metrics.max_drawdown, just faster."""
    running_peak = np.maximum.accumulate(equity, axis=1)
    return (equity / running_peak - 1).min(axis=1)


def path_cagrs(equity, periods_per_year=TRADING_DAYS_PER_YEAR):
    """The average yearly return of every history. Same formula as metrics.cagr."""
    years = (equity.shape[1] - 1) / periods_per_year
    return (equity[:, -1] / equity[:, 0]) ** (1 / years) - 1


def run_monte_carlo(results, num_paths=1000, years=10, block_size=20,
                    initial_capital=10_000, seed=None):
    """Build lots of made-up histories and run the strategy and buy-and-hold through them.

    `results` is what run_backtest() returned. You get back a dictionary with
    a "Strategy" entry and a "Buy & Hold" entry. Each one holds the portfolio
    value over time for every history ("equity"), plus one final value, CAGR
    and max drawdown per history.
    """
    # Skip the first row. Its return is a placeholder 0, not a real day.
    history = results.iloc[1:]
    num_days = int(years * TRADING_DAYS_PER_YEAR)

    rng = np.random.default_rng(seed)  # the same seed always gives the same "random" results
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
    """Boil the simulation down to a handful of numbers for each side.

    The 5th percentile is a bad but realistic outcome, since only 1 history
    in 20 did worse. The median (50th percentile) is a typical outcome.
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

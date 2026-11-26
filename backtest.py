"""MITS Backtester: command-line entry point.

Examples:
    python backtest.py --csv data/SPY.csv --short 50 --long 200
    python backtest.py --csv data/SPY.csv --strategy momentum
    python backtest.py --csv data/SPY.csv --cost-bps 5 --monte-carlo 1000
    python backtest.py --csv data/SPY.csv --sweep
    python backtest.py --csv data/SPY.csv --compare
"""

import argparse
import math
from pathlib import Path

import matplotlib.pyplot as plt

from mits_backtester.compare import compare_strategies
from mits_backtester.data import load_data
from mits_backtester.engine import count_trades, run_backtest, time_in_market
from mits_backtester.metrics import RATIO_METRICS, compute_metrics
from mits_backtester.montecarlo import run_monte_carlo, summarize_monte_carlo
from mits_backtester.plotting import (
    plot_monte_carlo,
    plot_results,
    plot_strategy_comparison,
    plot_sweep_heatmap,
)
from mits_backtester.strategies import STRATEGIES
from mits_backtester.sweep import parameter_sweep


def parse_args():
    parser = argparse.ArgumentParser(
        description="Backtest a trading strategy against buy-and-hold."
    )
    parser.add_argument("--csv", required=True, help="Path to a Yahoo Finance-style CSV file")
    parser.add_argument("--strategy", choices=STRATEGIES, default="sma",
                        help="Which strategy to test (default: sma)")
    parser.add_argument("--capital", type=float, default=10_000, help="Starting capital in dollars (default: 10000)")
    parser.add_argument("--output-dir", default="output", help="Folder for the PNG charts (default: output)")
    parser.add_argument("--cost-bps", type=float, default=0.0,
                        help="Trading cost per buy or sell, in basis points (1 bp = 0.01%%; default: 0)")
    parser.add_argument("--compare", action="store_true",
                        help="Also run every strategy on the same dates and print a leaderboard")

    sma = parser.add_argument_group("sma: moving-average crossover")
    sma.add_argument("--short", type=int, default=50, help="Short moving-average window in days (default: 50)")
    sma.add_argument("--long", type=int, default=200, help="Long moving-average window in days (default: 200)")
    sma.add_argument("--sweep", action="store_true",
                     help="Also test a grid of short/long windows and save a Sharpe-ratio heatmap")

    mom = parser.add_argument_group("momentum: time-series momentum")
    mom.add_argument("--lookback", type=int, default=252, help="Days of past return to look at (default: 252)")
    mom.add_argument("--skip", type=int, default=21, help="Most recent days to ignore (default: 21)")

    mr = parser.add_argument_group("mean_reversion: buy when oversold")
    mr.add_argument("--window", type=int, default=20, help="Days for the average and std (default: 20)")
    mr.add_argument("--entry-z", type=float, default=-1.0, help="Buy below this z-score (default: -1.0)")

    vt = parser.add_argument_group("vol_target: volatility targeting")
    vt.add_argument("--target-vol", type=float, default=0.15, help="Target yearly volatility (default: 0.15)")
    vt.add_argument("--vol-window", type=int, default=20, help="Days used to measure volatility (default: 20)")

    mc = parser.add_argument_group("Monte Carlo risk simulation")
    mc.add_argument("--monte-carlo", type=int, default=0, metavar="PATHS",
                    help="Number of simulated paths, e.g. 1000 (default: 0 = off)")
    mc.add_argument("--mc-years", type=int, default=10, help="Length of each simulated path in years (default: 10)")
    mc.add_argument("--block-size", type=int, default=20,
                    help="Days per resampled block; 1 = independent days (default: 20)")
    mc.add_argument("--seed", type=int, default=42, help="Random seed for repeatable results (default: 42)")
    return parser.parse_args()


def strategy_settings(args):
    """Pick out the command-line settings that belong to the chosen strategy."""
    settings = {
        "sma": {"short_window": args.short, "long_window": args.long},
        "momentum": {"lookback": args.lookback, "skip": args.skip},
        "mean_reversion": {"window": args.window, "entry_z": args.entry_z},
        "vol_target": {"target_vol": args.target_vol, "window": args.vol_window},
    }
    return settings[args.strategy]


def format_metric(name, value):
    """Show ratios as plain numbers and everything else as percentages."""
    if math.isnan(value):
        return "n/a"
    if abs(value) < 1e-12:   # tiny rounding errors like -0.0000000001 would print as "-0.00%"
        value = 0.0
    if name in RATIO_METRICS:
        return f"{value:.2f}"
    return f"{value * 100:.2f}%"


def print_report(name, label, results, strategy_metrics, buyhold_metrics):
    start = results.index[0].date()
    end = results.index[-1].date()
    print(f"\nMITS Backtester: {name}, {label}")
    print(f"Period: {start} to {end} ({len(results)} trading days)\n")

    print(f"{'Metric':<24}{'Strategy':>12}{'Buy & Hold':>14}")
    print("-" * 50)
    for metric in strategy_metrics:
        strategy_text = format_metric(metric, strategy_metrics[metric])
        buyhold_text = format_metric(metric, buyhold_metrics.get(metric, float("nan")))
        print(f"{metric:<24}{strategy_text:>12}{buyhold_text:>14}")
    print("-" * 50)

    positions = results["Position"]
    print(f"Position changes: {count_trades(positions)}   "
          f"Average exposure: {time_in_market(positions) * 100:.1f}%")
    print(f"Final value: strategy ${results['Strategy_Equity'].iloc[-1]:,.2f}, "
          f"buy & hold ${results['BuyHold_Equity'].iloc[-1]:,.2f}\n")


def print_monte_carlo_report(summary, num_paths, years, block_size):
    print(f"Monte Carlo: {num_paths:,} simulated {years}-year paths "
          f"(block bootstrap, {block_size}-day blocks)\n")
    print(f"{'Statistic':<28}{'Strategy':>12}{'Buy & Hold':>14}")
    print("-" * 54)
    for stat in summary["Strategy"]:
        values = []
        for name in ("Strategy", "Buy & Hold"):
            value = summary[name][stat]
            values.append(f"${value:,.0f}" if stat.startswith("Final Value") else f"{value * 100:.1f}%")
        print(f"{stat:<28}{values[0]:>12}{values[1]:>14}")
    print("-" * 54)
    print(f"Chance strategy ends ahead of buy & hold: "
          f"{summary['Chance Strategy Beats Buy & Hold'] * 100:.1f}%\n")


def run_sweep(prices, args, name):
    """Run the parameter sweep, print the top results, save the heatmap."""
    try:
        table, buy_hold = parameter_sweep(prices, cost_per_trade=args.cost_bps / 10_000)
    except (IndexError, ValueError):
        raise SystemExit("Error: not enough data for the parameter sweep (needs > 300 days)")

    start = prices.index[table["Long"].max() - 1].date()
    print(f"Parameter sweep: {len(table)} window pairs, all scored from {start}")
    print(f"Buy & hold Sharpe over the same dates: {buy_hold['Sharpe Ratio']:.2f}")
    beat = (table["Sharpe Ratio"] > buy_hold["Sharpe Ratio"]).sum()
    print(f"Pairs with a higher Sharpe than buy & hold: {beat} of {len(table)}\n")
    top = table.sort_values("Sharpe Ratio", ascending=False).head(5)
    print(top[["Short", "Long", "CAGR", "Max Drawdown", "Sharpe Ratio"]]
          .to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print()

    path = Path(args.output_dir) / f"{name}_parameter_sweep.png"
    fig = plot_sweep_heatmap(
        table, buy_hold["Sharpe Ratio"], highlight=(args.short, args.long),
        title=f"{name}: Sharpe ratio for each moving-average window pair", path=path,
    )
    plt.close(fig)
    return path


LEADERBOARD_COLUMNS = ["CAGR", "Max Drawdown", "Annualized Volatility", "Sharpe Ratio",
                       "Sortino Ratio", "Calmar Ratio", "Beta", "Alpha", "Avg Exposure"]


def run_comparison(prices, args, name):
    """Run every strategy on the same dates, print a leaderboard, save a chart."""
    try:
        table, equity_curves = compare_strategies(
            prices, cost_per_trade=args.cost_bps / 10_000, initial_capital=args.capital,
        )
    except ValueError as error:
        raise SystemExit(f"Error: {error}")

    start, end = equity_curves.index[0].date(), equity_curves.index[-1].date()
    print(f"Strategy leaderboard (default settings), {start} to {end}, sorted by Sharpe ratio\n")
    table = table.sort_values("Sharpe Ratio", ascending=False)
    shown = table[LEADERBOARD_COLUMNS].copy()
    for col in shown.columns:
        shown[col] = [format_metric(col, value) for value in shown[col]]
    shown.columns = ["CAGR", "MaxDD", "Vol", "Sharpe", "Sortino", "Calmar", "Beta", "Alpha", "Exposure"]
    print(shown.to_string())
    print()

    path = Path(args.output_dir) / f"{name}_strategy_comparison.png"
    fig = plot_strategy_comparison(
        equity_curves, title=f"{name}: growth of ${args.capital:,.0f} by strategy (log scale)",
        path=path,
    )
    plt.close(fig)
    return path


def main():
    args = parse_args()
    name = Path(args.csv).stem  # "data/SPY.csv" -> "SPY"
    strategy = STRATEGIES[args.strategy]

    try:
        prices = load_data(args.csv)
        signals = strategy["function"](prices, **strategy_settings(args))
    except (FileNotFoundError, ValueError) as error:
        raise SystemExit(f"Error: {error}")

    results = run_backtest(signals, initial_capital=args.capital,
                           cost_per_trade=args.cost_bps / 10_000)

    buyhold_metrics = compute_metrics(results["BuyHold_Equity"],
                                      benchmark_equity=results["BuyHold_Equity"])
    strategy_metrics = compute_metrics(results["Strategy_Equity"],
                                       benchmark_equity=results["BuyHold_Equity"])
    print_report(name, strategy["label"], results, strategy_metrics, buyhold_metrics)
    if args.cost_bps:
        print(f"(Strategy returns include a trading cost of {args.cost_bps:g} bps per trade.)\n")

    chart_paths = list(plot_results(
        signals, results, args.capital, strategy_label=strategy["label"],
        name=name, output_dir=args.output_dir,
    ))

    if args.monte_carlo > 0:
        try:
            simulations = run_monte_carlo(
                results, num_paths=args.monte_carlo, years=args.mc_years,
                block_size=args.block_size, initial_capital=args.capital, seed=args.seed,
            )
        except ValueError as error:
            raise SystemExit(f"Error: {error}")
        summary = summarize_monte_carlo(simulations, args.capital)
        print_monte_carlo_report(summary, args.monte_carlo, args.mc_years, args.block_size)
        chart_paths += plot_monte_carlo(
            simulations, args.capital, args.mc_years, args.monte_carlo,
            name=name, output_dir=args.output_dir,
        )

    if args.sweep:
        chart_paths.append(run_sweep(prices, args, name))

    if args.compare:
        chart_paths.append(run_comparison(prices, args, name))

    for path in chart_paths:
        print(f"Saved chart: {path}")


if __name__ == "__main__":
    main()

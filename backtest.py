"""MITS Backtester: command-line entry point.

Example:
    python backtest.py --csv data/SPY.csv --short 50 --long 200
    python backtest.py --csv data/SPY.csv --cost-bps 5 --monte-carlo 1000
"""

import argparse
import math
from pathlib import Path

from mits_backtester.data import load_data
from mits_backtester.engine import count_trades, run_backtest, time_in_market
from mits_backtester.metrics import compute_metrics
from mits_backtester.montecarlo import run_monte_carlo, summarize_monte_carlo
from mits_backtester.plotting import plot_monte_carlo, plot_results
from mits_backtester.strategies import compute_signals


def parse_args():
    parser = argparse.ArgumentParser(
        description="Backtest a moving-average crossover strategy against buy-and-hold."
    )
    parser.add_argument("--csv", required=True, help="Path to a Yahoo Finance-style CSV file")
    parser.add_argument("--short", type=int, default=50, help="Short moving-average window in days (default: 50)")
    parser.add_argument("--long", type=int, default=200, help="Long moving-average window in days (default: 200)")
    parser.add_argument("--capital", type=float, default=10_000, help="Starting capital in dollars (default: 10000)")
    parser.add_argument("--output-dir", default="output", help="Folder for the PNG charts (default: output)")
    parser.add_argument("--cost-bps", type=float, default=0.0,
                        help="Trading cost per buy or sell, in basis points (1 bp = 0.01%%; default: 0)")

    mc = parser.add_argument_group("Monte Carlo risk simulation")
    mc.add_argument("--monte-carlo", type=int, default=0, metavar="PATHS",
                    help="Number of simulated paths, e.g. 1000 (default: 0 = off)")
    mc.add_argument("--mc-years", type=int, default=10, help="Length of each simulated path in years (default: 10)")
    mc.add_argument("--block-size", type=int, default=20,
                    help="Days per resampled block; 1 = independent days (default: 20)")
    mc.add_argument("--seed", type=int, default=42, help="Random seed for repeatable results (default: 42)")
    return parser.parse_args()


def format_metric(name, value):
    """Show ratios as plain numbers and everything else as percentages."""
    if math.isnan(value):
        return "n/a"
    if name == "Sharpe Ratio":
        return f"{value:.2f}"
    return f"{value * 100:.2f}%"


def print_report(name, results, strategy_metrics, buyhold_metrics):
    start = results.index[0].date()
    end = results.index[-1].date()
    print(f"\nMITS Backtester: {name}")
    print(f"Period: {start} to {end} ({len(results)} trading days)\n")

    print(f"{'Metric':<24}{'Strategy':>12}{'Buy & Hold':>14}")
    print("-" * 50)
    for metric in strategy_metrics:
        strategy_text = format_metric(metric, strategy_metrics[metric])
        buyhold_text = format_metric(metric, buyhold_metrics[metric])
        print(f"{metric:<24}{strategy_text:>12}{buyhold_text:>14}")
    print("-" * 50)

    positions = results["Position"]
    print(f"Trades: {count_trades(positions)}   "
          f"Time in market: {time_in_market(positions) * 100:.1f}%")
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


def main():
    args = parse_args()
    name = Path(args.csv).stem  # "data/SPY.csv" -> "SPY"

    try:
        prices = load_data(args.csv)
        signals = compute_signals(prices, short_window=args.short, long_window=args.long)
    except (FileNotFoundError, ValueError) as error:
        raise SystemExit(f"Error: {error}")

    results = run_backtest(signals, initial_capital=args.capital,
                           cost_per_trade=args.cost_bps / 10_000)

    strategy_metrics = compute_metrics(results["Strategy_Equity"])
    buyhold_metrics = compute_metrics(results["BuyHold_Equity"])
    print_report(name, results, strategy_metrics, buyhold_metrics)
    if args.cost_bps:
        print(f"(Strategy returns include a trading cost of {args.cost_bps:g} bps per trade.)\n")

    chart_paths = plot_results(
        signals, results, args.short, args.long, args.capital,
        name=name, output_dir=args.output_dir,
    )

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

    for path in chart_paths:
        print(f"Saved chart: {path}")


if __name__ == "__main__":
    main()

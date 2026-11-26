"""MITS Backtester: command-line entry point.

Example:
    python backtest.py --csv data/SPY.csv --short 50 --long 200
"""

import argparse
import math
from pathlib import Path

from mits_backtester.data import load_data
from mits_backtester.engine import count_trades, run_backtest, time_in_market
from mits_backtester.metrics import compute_metrics
from mits_backtester.plotting import plot_results
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


def main():
    args = parse_args()
    name = Path(args.csv).stem  # "data/SPY.csv" -> "SPY"

    try:
        prices = load_data(args.csv)
        signals = compute_signals(prices, short_window=args.short, long_window=args.long)
    except (FileNotFoundError, ValueError) as error:
        raise SystemExit(f"Error: {error}")

    results = run_backtest(signals, initial_capital=args.capital)

    strategy_metrics = compute_metrics(results["Strategy_Equity"])
    buyhold_metrics = compute_metrics(results["BuyHold_Equity"])
    print_report(name, results, strategy_metrics, buyhold_metrics)

    chart_paths = plot_results(
        signals, results, args.short, args.long, args.capital,
        name=name, output_dir=args.output_dir,
    )
    for path in chart_paths:
        print(f"Saved chart: {path}")


if __name__ == "__main__":
    main()

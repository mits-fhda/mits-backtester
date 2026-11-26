"""MITS Backtester: interactive web app.

Run it with:
    streamlit run app.py

Streamlit re-runs this whole script from top to bottom every time a control
changes, so the script reads like a simple recipe: read the controls, run the
backtest, show the results. It reuses exactly the same functions as the
command-line tool; this file only handles the display.
"""

import math
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from mits_backtester.compare import compare_strategies
from mits_backtester.data import download_data, load_data
from mits_backtester.engine import count_trades, run_backtest, time_in_market
from mits_backtester.metrics import RATIO_METRICS, compute_metrics
from mits_backtester.montecarlo import run_monte_carlo, summarize_monte_carlo
from mits_backtester.plotting import (
    plot_equity_curves,
    plot_monte_carlo_drawdowns,
    plot_monte_carlo_paths,
    plot_price_and_signals,
    plot_strategy_comparison,
    plot_sweep_heatmap,
)
from mits_backtester.strategies import STRATEGIES
from mits_backtester.sweep import parameter_sweep

SAMPLE_CSV = Path(__file__).parent / "data" / "sample.csv"

st.set_page_config(page_title="MITS Backtester", layout="wide")


# ---------- Cached helpers (so moving a slider doesn't redo slow work) ----------

@st.cache_data(ttl=3600, show_spinner="Downloading prices from Yahoo Finance...")
def cached_download(ticker, start):
    return download_data(ticker, start=start)


@st.cache_data(show_spinner="Running Monte Carlo simulation...")
def cached_monte_carlo(results, num_paths, years, capital):
    return run_monte_carlo(results, num_paths=num_paths, years=years,
                           initial_capital=capital, seed=42)


@st.cache_data(show_spinner="Testing every window pair...")
def cached_sweep(prices, cost):
    return parameter_sweep(prices, cost_per_trade=cost)


@st.cache_data(show_spinner="Running every strategy...")
def cached_comparison(prices, cost, capital):
    return compare_strategies(prices, cost_per_trade=cost, initial_capital=capital)


def show(fig):
    """Display a matplotlib figure, then free its memory."""
    st.pyplot(fig)
    plt.close(fig)


def format_value(metric, value):
    """Ratios as plain numbers, everything else as a percentage."""
    if isinstance(value, float) and math.isnan(value):
        return "n/a"
    if abs(value) < 1e-12:   # tiny rounding errors would otherwise show as "-0.00%"
        value = 0.0
    return f"{value:.2f}" if metric in RATIO_METRICS else f"{value:.2%}"


def format_table(table):
    """Format a table whose COLUMNS are metric names."""
    return table.apply(lambda col: col.map(lambda v: format_value(col.name, v)))


# ---------- Sidebar: all the controls ----------

st.sidebar.title("Settings")

source = st.sidebar.radio("Price data", ["Yahoo Finance ticker", "Upload a CSV", "Sample data"],
                          key="source")
if source == "Yahoo Finance ticker":
    ticker = st.sidebar.text_input("Ticker", "SPY").strip().upper()
    start_year = st.sidebar.number_input("Start year", 1980, 2025, 2000)
elif source == "Upload a CSV":
    uploaded = st.sidebar.file_uploader("Yahoo Finance CSV", type="csv")

st.sidebar.subheader("Strategy")
strategy_key = st.sidebar.selectbox(
    "Strategy", list(STRATEGIES), format_func=lambda key: STRATEGIES[key]["label"], key="strategy",
)
if strategy_key == "sma":
    settings = {
        "short_window": st.sidebar.slider("Short moving average (days)", 5, 150, 50),
        "long_window": st.sidebar.slider("Long moving average (days)", 20, 400, 200),
    }
elif strategy_key == "momentum":
    settings = {
        "lookback": st.sidebar.slider("Lookback (days)", 20, 504, 252,
                                      help="252 trading days = about 1 year"),
        "skip": st.sidebar.slider("Skip most recent (days)", 0, 63, 21,
                                  help="21 trading days = about 1 month"),
    }
elif strategy_key == "mean_reversion":
    settings = {
        "window": st.sidebar.slider("Window (days)", 5, 100, 20),
        "entry_z": st.sidebar.slider("Buy below z-score", -3.0, -0.25, -1.0, step=0.25),
    }
else:
    settings = {
        "target_vol": st.sidebar.slider("Target volatility", 0.05, 0.40, 0.15, step=0.01,
                                        format="%.2f", help="0.15 = 15% per year"),
        "window": st.sidebar.slider("Volatility window (days)", 5, 100, 20),
    }

cost_bps = st.sidebar.number_input("Trading cost per trade (basis points)", 0.0, 100.0, 5.0, step=1.0,
                                   help="1 basis point = 0.01%. Covers commissions, spreads and slippage.")
capital = st.sidebar.number_input("Starting capital ($)", 1_000, 10_000_000, 10_000, step=1_000)


# ---------- Load the data and run the backtest ----------

st.title("MITS Backtester")
st.caption("Test quant trading strategies against buy-and-hold, with professional risk "
           "metrics and Monte Carlo analysis. Built for the Mathematical Investment and "
           "Trading Society.")

strategy = STRATEGIES[strategy_key]
try:
    if source == "Yahoo Finance ticker":
        if not ticker:
            st.info("Enter a ticker symbol in the sidebar.")
            st.stop()
        prices = cached_download(ticker, f"{start_year}-01-01")
        name = ticker
    elif source == "Upload a CSV":
        if uploaded is None:
            st.info("Upload a CSV with at least Date and Close columns.")
            st.stop()
        prices = load_data(uploaded)
        name = Path(uploaded.name).stem
    else:
        prices = load_data(SAMPLE_CSV)
        name = "Sample (synthetic)"

    signals = strategy["function"](prices, **settings)
except Exception as error:  # show any data problem as a friendly message
    st.error(f"Couldn't run the backtest: {error}")
    st.stop()

cost = cost_bps / 10_000
results = run_backtest(signals, initial_capital=capital, cost_per_trade=cost)
buy_hold_equity = results["BuyHold_Equity"]
strategy_metrics = compute_metrics(results["Strategy_Equity"], benchmark_equity=buy_hold_equity)
buy_hold_metrics = compute_metrics(buy_hold_equity, benchmark_equity=buy_hold_equity)


# ---------- Headline numbers ----------

st.subheader(f"{name}: {strategy['label']}, "
             f"{results.index[0]:%b %Y} to {results.index[-1]:%b %Y}")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Final value (strategy)", f"${results['Strategy_Equity'].iloc[-1]:,.0f}",
            f"Buy & hold: ${buy_hold_equity.iloc[-1]:,.0f}", delta_color="off")
col2.metric("CAGR", format_value("CAGR", strategy_metrics["CAGR"]),
            f"{(strategy_metrics['CAGR'] - buy_hold_metrics['CAGR']) * 100:+.2f} pts vs. buy & hold")
col3.metric("Max drawdown", format_value("Max Drawdown", strategy_metrics["Max Drawdown"]),
            f"{(strategy_metrics['Max Drawdown'] - buy_hold_metrics['Max Drawdown']) * 100:+.1f} pts "
            "vs. buy & hold")
col4.metric("Sharpe ratio", f"{strategy_metrics['Sharpe Ratio']:.2f}",
            f"{strategy_metrics['Sharpe Ratio'] - buy_hold_metrics['Sharpe Ratio']:+.2f} vs. buy & hold")

tab_backtest, tab_leaderboard, tab_mc, tab_sweep, tab_about = st.tabs(
    ["Backtest", "Strategy leaderboard", "Monte Carlo risk", "Parameter robustness", "How it works"]
)


# ---------- Tab: the backtest ----------

with tab_backtest:
    table = pd.DataFrame({"Strategy": strategy_metrics, "Buy & Hold": buy_hold_metrics})
    left, right = st.columns([1, 2])
    left.dataframe(format_table(table.T).T, width="stretch")
    left.write(f"**{count_trades(results['Position'])}** position changes, "
               f"**{time_in_market(results['Position']):.0%}** average exposure.")
    with right:
        show(plot_equity_curves(results, capital,
                                title=f"Growth of ${capital:,.0f}, strategy vs. buy and hold"))
    show(plot_price_and_signals(signals, results,
                                title=f"Price, signals and position: {strategy['label']}"))


# ---------- Tab: strategy leaderboard ----------

with tab_leaderboard:
    st.write("Every strategy, with its default settings, on exactly the same dates. "
             "Sorted by Sharpe ratio. **Beta** is how much of the result just comes from "
             "riding the market; **alpha** is the yearly return left over after that.")
    try:
        board, curves = cached_comparison(prices, cost, capital)
    except ValueError as error:
        st.warning(f"Couldn't run every strategy on this data: {error}")
    else:
        columns = ["CAGR", "Max Drawdown", "Annualized Volatility", "Sharpe Ratio",
                   "Sortino Ratio", "Calmar Ratio", "Beta", "Alpha", "Avg Exposure"]
        board = board.sort_values("Sharpe Ratio", ascending=False)[columns]
        st.dataframe(format_table(board), width="stretch")
        show(plot_strategy_comparison(curves, title=f"Growth of ${capital:,.0f} by strategy (log scale)"))


# ---------- Tab: Monte Carlo ----------

with tab_mc:
    st.write("Builds thousands of alternative histories by stitching together random "
             "20-day chunks of the real daily returns, to show the **range** of outcomes "
             "instead of just the one path history took.")
    c1, c2 = st.columns(2)
    num_paths = c1.select_slider("Simulated paths", [250, 500, 1000, 2000, 5000], 1000)
    years = c2.slider("Years per path", 1, 30, 10)

    sims = cached_monte_carlo(results, num_paths, years, capital)
    summary = summarize_monte_carlo(sims, capital)
    rows = {}
    for stat in summary["Strategy"]:
        is_money = stat.startswith("Final Value")
        rows[stat] = [f"${summary[n][stat]:,.0f}" if is_money else f"{summary[n][stat]:.1%}"
                      for n in ("Strategy", "Buy & Hold")]
    st.dataframe(pd.DataFrame(rows, index=["Strategy", "Buy & Hold"]).T, width="stretch")
    st.write(f"The strategy ends ahead of buy-and-hold in "
             f"**{summary['Chance Strategy Beats Buy & Hold']:.0%}** of simulations.")
    show(plot_monte_carlo_paths(sims, capital, years,
                                title=f"{num_paths:,} simulated {years}-year paths"))
    show(plot_monte_carlo_drawdowns(sims, title="Worst drawdown in each simulated path"))
    st.caption("Limitation: this resamples the strategy's realized returns; it does not "
               "re-run the strategy on new simulated prices.")


# ---------- Tab: parameter sweep ----------

with tab_sweep:
    st.write("Is a moving-average window pair genuinely good, or just lucky? This tests 29 "
             "pairs over the same dates. A robust strategy looks good across a whole "
             "**region** of settings; a lucky one only at a single cell.")
    try:
        sweep_table, sweep_bh = cached_sweep(prices, cost)
    except (IndexError, ValueError):
        st.warning("Not enough data: the sweep needs more than 300 trading days.")
    else:
        beat = (sweep_table["Sharpe Ratio"] > sweep_bh["Sharpe Ratio"]).sum()
        st.write(f"**{beat} of {len(sweep_table)}** pairs had a higher Sharpe ratio than "
                 f"buy-and-hold ({sweep_bh['Sharpe Ratio']:.2f}).")
        highlight = ((settings["short_window"], settings["long_window"])
                     if strategy_key == "sma" else None)
        show(plot_sweep_heatmap(sweep_table, sweep_bh["Sharpe Ratio"], highlight=highlight,
                                title="Moving-average crossover: Sharpe ratio by window pair"))


# ---------- Tab: explanations ----------

with tab_about:
    st.markdown("""
### The strategies

| Strategy | Rule | Idea behind it |
|---|---|---|
| Moving-average crossover | Own it while the 50-day average is above the 200-day | Ride long trends, step aside in downtrends |
| Time-series momentum | Own it if the past 12 months (skipping the last 1) went up | Winners tend to keep winning for a while |
| Mean reversion | Own it when the price is 1+ std below its 20-day average | Sharp drops tend to partly bounce back |
| Volatility targeting | Always invested, sized to target 15% yearly volatility | Cut risk when markets get wild, since wild days cluster |

**No look-ahead bias.** A signal uses the day's closing price, so it only affects the
position from the *next* trading day. Otherwise the backtest would profit from moves it
couldn't have known about in advance.

### The metrics

| Metric | Formula | Meaning |
|---|---|---|
| Total return | end / start − 1 | Overall growth |
| CAGR | (end / start)^(1/years) − 1 | Steady yearly growth rate with the same result |
| Max drawdown | min(value / running peak − 1) | Worst fall from a high point |
| Volatility | std(daily returns) × √252 | How bumpy the ride is |
| Sharpe ratio | mean / std of daily returns × √252 | Return per unit of risk (0% risk-free rate) |
| Sortino ratio | mean / downside deviation × √252 | Like Sharpe, but only bad days count as risk |
| Calmar ratio | CAGR / \\|max drawdown\\| | Yearly return per unit of worst-case pain |
| Daily VaR (95%) | 5th percentile of daily returns | "On 19 days out of 20, we lose less than this" |
| Daily CVaR (95%) | average of the worst 5% of days | How bad the bad days get (Expected Shortfall) |
| Beta | cov(strategy, market) / var(market) | How much it moves with the market |
| Alpha | (mean − beta × market mean) × 252 | Yearly return not explained by the market |

Source code and tests: [github.com/mamoonrkhan/mits-backtester](https://github.com/mamoonrkhan/mits-backtester).
Educational project, not investment advice.
""")

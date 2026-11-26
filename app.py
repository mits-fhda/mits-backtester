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

from mits_backtester.data import download_data, load_data
from mits_backtester.engine import count_trades, run_backtest, time_in_market
from mits_backtester.metrics import compute_metrics
from mits_backtester.montecarlo import run_monte_carlo, summarize_monte_carlo
from mits_backtester.plotting import (
    plot_equity_curves,
    plot_monte_carlo_drawdowns,
    plot_monte_carlo_paths,
    plot_price_and_signals,
    plot_sweep_heatmap,
)
from mits_backtester.strategies import compute_signals
from mits_backtester.sweep import parameter_sweep

SAMPLE_CSV = Path(__file__).parent / "data" / "sample.csv"

st.set_page_config(page_title="MITS Backtester", layout="wide")


# ---------- Cached helpers (so moving a slider doesn't re-download data) ----------

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


def show(fig):
    """Display a matplotlib figure, then free its memory."""
    st.pyplot(fig)
    plt.close(fig)


def percent(value):
    return "n/a" if math.isnan(value) else f"{value:.2%}"


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
short_window = st.sidebar.slider("Short moving average (days)", 5, 150, 50)
long_window = st.sidebar.slider("Long moving average (days)", 20, 400, 200)
cost_bps = st.sidebar.number_input("Trading cost per trade (basis points)", 0.0, 100.0, 5.0, step=1.0,
                                   help="1 basis point = 0.01%. Covers commissions, spreads and slippage.")
capital = st.sidebar.number_input("Starting capital ($)", 1_000, 10_000_000, 10_000, step=1_000)


# ---------- Load the data ----------

st.title("MITS Backtester")
st.caption("Moving-average crossover vs. buy-and-hold, with Monte Carlo risk analysis. "
           "Built for the Mathematical Investment and Trading Society.")

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

    signals = compute_signals(prices, short_window=short_window, long_window=long_window)
except Exception as error:  # show any data problem as a friendly message
    st.error(f"Couldn't run the backtest: {error}")
    st.stop()

results = run_backtest(signals, initial_capital=capital, cost_per_trade=cost_bps / 10_000)
strategy = compute_metrics(results["Strategy_Equity"])
buy_hold = compute_metrics(results["BuyHold_Equity"])


# ---------- Headline numbers ----------

st.subheader(f"{name}: {short_window}/{long_window}-day crossover, "
             f"{results.index[0]:%b %Y} to {results.index[-1]:%b %Y}")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Final value (strategy)", f"${results['Strategy_Equity'].iloc[-1]:,.0f}",
            f"Buy & hold: ${results['BuyHold_Equity'].iloc[-1]:,.0f}", delta_color="off")
col2.metric("CAGR", percent(strategy["CAGR"]),
            f"{(strategy['CAGR'] - buy_hold['CAGR']) * 100:+.2f} pts vs. buy & hold")
col3.metric("Max drawdown", percent(strategy["Max Drawdown"]),
            f"{(strategy['Max Drawdown'] - buy_hold['Max Drawdown']) * 100:+.1f} pts vs. buy & hold")
col4.metric("Sharpe ratio", f"{strategy['Sharpe Ratio']:.2f}",
            f"{strategy['Sharpe Ratio'] - buy_hold['Sharpe Ratio']:+.2f} vs. buy & hold")

tab_backtest, tab_mc, tab_sweep, tab_about = st.tabs(
    ["Backtest", "Monte Carlo risk", "Parameter robustness", "How it works"]
)


# ---------- Tab 1: the backtest ----------

with tab_backtest:
    table = pd.DataFrame({"Strategy": strategy, "Buy & Hold": buy_hold})
    formatted = table.apply(lambda row: row.map(
        (lambda v: f"{v:.2f}") if row.name == "Sharpe Ratio" else percent), axis=1)
    left, right = st.columns([1, 2])
    left.dataframe(formatted, width="stretch")
    left.write(f"**{count_trades(results['Position'])}** trades, in the market "
               f"**{time_in_market(results['Position']):.0%}** of the time.")
    with right:
        show(plot_equity_curves(results, capital,
                                title=f"Growth of ${capital:,.0f}, strategy vs. buy and hold"))
    show(plot_price_and_signals(signals, results, short_window, long_window,
                                title="Price and moving averages (shaded = strategy holds the stock)"))


# ---------- Tab 2: Monte Carlo ----------

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
               "re-run the moving-average rule on new simulated prices.")


# ---------- Tab 3: parameter sweep ----------

with tab_sweep:
    st.write("Is your window pair genuinely good, or just lucky? This tests 29 pairs over "
             "the same dates. A robust strategy looks good across a whole **region** of "
             "settings; a lucky one only at a single cell.")
    try:
        sweep_table, sweep_bh = cached_sweep(prices, cost_bps / 10_000)
    except (IndexError, ValueError):
        st.warning("Not enough data: the sweep needs more than 300 trading days.")
    else:
        beat = (sweep_table["Sharpe Ratio"] > sweep_bh["Sharpe Ratio"]).sum()
        st.write(f"**{beat} of {len(sweep_table)}** pairs had a higher Sharpe ratio than "
                 f"buy-and-hold ({sweep_bh['Sharpe Ratio']:.2f}).")
        show(plot_sweep_heatmap(sweep_table, sweep_bh["Sharpe Ratio"],
                                highlight=(short_window, long_window),
                                title="Sharpe ratio by window pair (outlined = your settings)"))


# ---------- Tab 4: explanations ----------

with tab_about:
    st.markdown("""
**The strategy.** Hold the stock while the short moving average is above the long one
(an uptrend); otherwise hold cash.

**No look-ahead bias.** A signal uses the day's closing price, so it only affects the
position from the *next* trading day. Otherwise the backtest would profit from moves it
couldn't have known about in advance.

| Metric | Formula | Meaning |
|---|---|---|
| Total return | end / start − 1 | Overall growth |
| CAGR | (end / start)^(1/years) − 1 | Steady yearly growth rate with the same result |
| Max drawdown | min(value / running peak − 1) | Worst fall from a high point |
| Volatility | std(daily returns) × √252 | How bumpy the ride is |
| Sharpe ratio | mean / std of daily returns × √252 | Return per unit of risk (0% risk-free rate) |

Source code and tests: [github.com/mamoonrkhan/mits-backtester](https://github.com/mamoonrkhan/mits-backtester).
Educational project, not investment advice.
""")

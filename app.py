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
LOGO = Path(__file__).parent / "docs" / "images" / "mits-logo.png"

st.set_page_config(page_title="MITS Backtester", page_icon=str(LOGO), layout="wide")
st.logo(str(LOGO), size="large")


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

st.sidebar.title("Set up your test")

source = st.sidebar.radio("Where should the prices come from?",
                          ["Look up a ticker", "Upload a CSV file", "Sample data"], key="source",
                          help="Sample data is made-up prices that always work, even offline.")
if source == "Look up a ticker":
    ticker = st.sidebar.text_input("Ticker", "SPY",
                                   help="SPY is a fund that tracks the S&P 500. Try AAPL, QQQ or anything else.")
    ticker = ticker.strip().upper()
    start_year = st.sidebar.number_input("Start from year", 1980, 2025, 2000)
elif source == "Upload a CSV file":
    uploaded = st.sidebar.file_uploader("Price file from Yahoo Finance", type="csv")

st.sidebar.subheader("Pick a strategy")
strategy_key = st.sidebar.selectbox(
    "Strategy", list(STRATEGIES), format_func=lambda key: STRATEGIES[key]["label"], key="strategy",
)
if strategy_key == "sma":
    settings = {
        "short_window": st.sidebar.slider("Short average (days)", 5, 150, 50),
        "long_window": st.sidebar.slider("Long average (days)", 20, 400, 200),
    }
elif strategy_key == "momentum":
    settings = {
        "lookback": st.sidebar.slider("Look back over (days)", 20, 504, 252,
                                      help="252 trading days is about a year."),
        "skip": st.sidebar.slider("Ignore the most recent (days)", 0, 63, 21,
                                  help="21 trading days is about a month. Very recent moves tend to reverse, "
                                       "so momentum strategies usually skip them."),
    }
elif strategy_key == "mean_reversion":
    settings = {
        "window": st.sidebar.slider("Average over (days)", 5, 100, 20),
        "entry_z": st.sidebar.slider("How big a drop before buying", -3.0, -0.25, -1.0, step=0.25,
                                     help="Measured in standard deviations below the average. -1 means "
                                          "one typical move below it; -2 means a much rarer, bigger drop."),
    }
elif strategy_key == "vol_target":
    settings = {
        "target_vol": st.sidebar.slider("Target risk level", 0.05, 0.40, 0.15, step=0.01, format="%.2f",
                                        help="Yearly volatility to aim for. 0.15 means 15%. The S&P 500 "
                                             "has averaged somewhere around 15-20%."),
        "window": st.sidebar.slider("Measure risk over (days)", 5, 100, 20),
    }
else:
    settings = {}   # a newly added strategy without sliders yet: use its default settings

st.sidebar.subheader("Fine print")
cost_bps = st.sidebar.number_input("Cost per trade (basis points)", 0.0, 100.0, 5.0, step=1.0,
                                   help="Every buy or sell loses a little to fees and the bid/ask spread. "
                                        "1 basis point is 0.01%, so 5 means 0.05% per trade.")
capital = st.sidebar.number_input("Starting amount ($)", 1_000, 10_000_000, 10_000, step=1_000)


# ---------- Load the data and run the backtest ----------

st.title("MITS Backtester")
st.caption("Pick a stock and a trading strategy, and see how it would have done compared with "
           "just buying and holding. Made by the Mathematical Investment and Trading Society.")

with st.expander("New here? Start with this"):
    st.markdown("""
A *backtest* answers one question: **if I had followed this rule in the past, how would it
have gone?**

Pick a ticker and a strategy on the left. The app goes back in time and pretends you
followed that strategy every single day, then compares it with someone who bought on day
one and never sold.

The four numbers just below are the quick summary:

- **Final value** is what your starting amount grew into.
- **Return per year** is the average yearly growth.
- **Worst drop** is the biggest fall from a high point that you'd have had to sit through.
- **Sharpe ratio** is return per unit of stress. Higher is better.

The small numbers under each one show how the strategy did *compared with buy-and-hold*.
Green means better. The tabs below go deeper, and **How it works** explains everything.
""")

strategy = STRATEGIES[strategy_key]
try:
    if source == "Look up a ticker":
        if not ticker:
            st.info("Type a ticker in the sidebar to get started, for example SPY, AAPL or QQQ.")
            st.stop()
        prices = cached_download(ticker, f"{start_year}-01-01")
        name = ticker
    elif source == "Upload a CSV file":
        if uploaded is None:
            st.info("Upload a price file from Yahoo Finance. It needs at least a Date and a Close column.")
            st.stop()
        prices = load_data(uploaded)
        name = Path(uploaded.name).stem
    else:
        prices = load_data(SAMPLE_CSV)
        name = "Sample data (made-up prices)"

    signals = strategy["function"](prices, **settings)
except Exception as error:  # show any data problem as a friendly message
    st.error(f"Couldn't run the test: {error}")
    if source == "Look up a ticker":
        st.caption("Check the ticker's spelling. Yahoo also blocks downloads now and then for a few "
                   "minutes. If that happens, Sample data in the sidebar always works.")
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
col1.metric("Final value", f"${results['Strategy_Equity'].iloc[-1]:,.0f}",
            f"Buy & hold: ${buy_hold_equity.iloc[-1]:,.0f}", delta_color="off")
col2.metric("Return per year", format_value("CAGR", strategy_metrics["CAGR"]),
            f"{(strategy_metrics['CAGR'] - buy_hold_metrics['CAGR']) * 100:+.2f} pts vs. buy & hold")
col3.metric("Worst drop", format_value("Max Drawdown", strategy_metrics["Max Drawdown"]),
            f"{(strategy_metrics['Max Drawdown'] - buy_hold_metrics['Max Drawdown']) * 100:+.1f} pts "
            "vs. buy & hold")
col4.metric("Sharpe ratio", f"{strategy_metrics['Sharpe Ratio']:.2f}",
            f"{strategy_metrics['Sharpe Ratio'] - buy_hold_metrics['Sharpe Ratio']:+.2f} vs. buy & hold")

tab_backtest, tab_leaderboard, tab_mc, tab_sweep, tab_about = st.tabs(
    ["Results", "Compare strategies", "What could happen", "Luck check", "How it works"]
)


# ---------- Tab: the backtest ----------

with tab_backtest:
    table = pd.DataFrame({"Strategy": strategy_metrics, "Buy & Hold": buy_hold_metrics})
    left, right = st.columns([1, 2])
    left.dataframe(format_table(table.T).T, width="stretch")
    left.write(f"The strategy changed its position **{count_trades(results['Position'])}** times "
               f"and was **{time_in_market(results['Position']):.0%}** invested on average.")
    with right:
        show(plot_equity_curves(results, capital,
                                title=f"Growth of ${capital:,.0f}, strategy vs. buy and hold"))
    st.write("The top chart shows the price and any lines the strategy uses. The bottom strip "
             "shows how much of the money was invested each day.")
    show(plot_price_and_signals(signals, results, title=f"What {strategy['label'].lower()} did"))


# ---------- Tab: strategy leaderboard ----------

with tab_leaderboard:
    st.write("Here's every strategy, each with its default settings, over exactly the same "
             "dates, with the best Sharpe ratio first. **Beta** shows how closely a strategy "
             "follows the market (1 means exactly), and **alpha** is the extra yearly return "
             "it earned on top of that.")
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
    st.write("History only happened once, and a different order of good and bad years could "
             "have changed everything. So here we cut the real daily returns into 20-day "
             "chunks, shuffle them into thousands of new histories, and run both approaches "
             "through each one. That shows the range of things that *could* have happened, "
             "not just the one that did.")
    c1, c2 = st.columns(2)
    num_paths = c1.select_slider("How many histories", [250, 500, 1000, 2000, 5000], 1000)
    years = c2.slider("Years in each one", 1, 30, 10)

    sims = cached_monte_carlo(results, num_paths, years, capital)
    summary = summarize_monte_carlo(sims, capital)
    rows = {}
    for stat in summary["Strategy"]:
        is_money = stat.startswith("Final Value")
        rows[stat] = [f"${summary[n][stat]:,.0f}" if is_money else f"{summary[n][stat]:.1%}"
                      for n in ("Strategy", "Buy & Hold")]
    st.dataframe(pd.DataFrame(rows, index=["Strategy", "Buy & Hold"]).T, width="stretch")
    st.write(f"The strategy finished ahead of buy-and-hold in "
             f"**{summary['Chance Strategy Beats Buy & Hold']:.0%}** of these histories. "
             "(The 5th percentile is a bad but realistic outcome: only 1 in 20 histories did worse.)")
    show(plot_monte_carlo_paths(sims, capital, years,
                                title=f"{num_paths:,} possible {years}-year histories"))
    show(plot_monte_carlo_drawdowns(sims, title="The worst drop in each history"))
    st.caption("One catch: this reshuffles the strategy's actual past returns. It doesn't re-run "
               "the strategy on brand-new prices, so it can't tell you whether the rule would "
               "still work in a totally different kind of market.")


# ---------- Tab: parameter sweep ----------

with tab_sweep:
    st.write("Maybe 50 and 200 just happened to work. To check, this tries 29 different pairs "
             "of moving-average lengths over the same dates. If the good results are bunched "
             "together, the idea is probably real. If only one square looks good, it was "
             "probably luck.")
    if strategy_key != "sma":
        st.caption("This check is for the moving-average strategy, so it shows the same thing "
                   "whichever strategy you picked.")
    try:
        sweep_table, sweep_bh = cached_sweep(prices, cost)
    except (IndexError, ValueError):
        st.warning("There isn't enough data for this check. It needs more than 300 trading days.")
    else:
        beat = (sweep_table["Sharpe Ratio"] > sweep_bh["Sharpe Ratio"]).sum()
        st.write(f"**{beat} of {len(sweep_table)}** pairs had a better Sharpe ratio than "
                 f"buy-and-hold ({sweep_bh['Sharpe Ratio']:.2f}). Blue squares beat it, gray ones roughly tied, "
                 "and orange ones did worse.")
        highlight = ((settings["short_window"], settings["long_window"])
                     if strategy_key == "sma" else None)
        show(plot_sweep_heatmap(sweep_table, sweep_bh["Sharpe Ratio"], highlight=highlight,
                                title="Sharpe ratio for each pair (outlined = your settings)"))


# ---------- Tab: explanations ----------

with tab_about:
    st.markdown("""
### The strategies

**Moving-average crossover.** Compare the average price over the last 50 days with the
average over the last 200. When the short one is higher, prices are trending up, so own
the stock. Otherwise, sit in cash.

**Time-series momentum.** If the stock went up over the past year, own it. The most
recent month is ignored, because very short-term moves tend to reverse.

**Mean reversion.** When the price suddenly falls well below its recent average, buy it
and bet on a bounce.

**Volatility targeting.** Always stay invested, but own less when the market gets jumpy.
Wild days tend to come in clusters, and crashes happen during those clusters.

### Why you can trust the results (mostly)

Each signal is based on a day's closing price, so in real life you couldn't act on it
until after the market closed. The app only lets a signal change your position starting
the *next* day. Without that, a backtest quietly "buys" right before the rallies that
caused its own buy signals, and looks far better than it ever could in real life.

That said, everything here is a look back at history. A rule that worked for 30 years
can still stop working.

### What the numbers mean

| Number | What it tells you | Formula |
|---|---|---|
| Total return | How much the money grew overall | end / start − 1 |
| CAGR | The average yearly growth | (end / start)^(1/years) − 1 |
| Max drawdown | The worst drop you'd have had to sit through | min(value / previous peak − 1) |
| Volatility | How bumpy the ride was | std(daily returns) × √252 |
| Sharpe ratio | Return for each unit of bumpiness | mean / std of daily returns × √252 |
| Sortino ratio | Like Sharpe, but only down days count as risk | mean / downside deviation × √252 |
| Calmar ratio | Yearly return for each unit of worst-case pain | CAGR / \\|max drawdown\\| |
| Daily VaR (95%) | On 19 days out of 20, you lose less than this | 5th percentile of daily returns |
| Daily CVaR (95%) | How bad those 1-in-20 days get on average | average of the worst 5% of days |
| Beta | How closely it follows the market (1 = exactly) | cov(strategy, market) / var(market) |
| Alpha | Extra yearly return beyond what the market explains | (mean − beta × market mean) × 252 |

The code is open source at
[github.com/mits-fhda/mits-backtester](https://github.com/mits-fhda/mits-backtester), and
club members are welcome to add their own strategies. This is a student project for
learning, not investment advice.
""")

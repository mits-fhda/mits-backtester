# MITS Backtester

[![tests](https://github.com/mamoonrkhan/mits-backtester/actions/workflows/tests.yml/badge.svg)](https://github.com/mamoonrkhan/mits-backtester/actions/workflows/tests.yml)

A small, readable Python tool for **backtesting** trading strategies, built for the
Mathematical Investment and Trading Society (MITS). A backtest asks: *if I had followed
this rule in the past, how would it have done?*

It tests a classic **moving-average crossover** strategy, compares it with simply
buying and holding the stock over the same period, and uses a **Monte Carlo
simulation** to estimate the range of outcomes and drawdowns you could face going forward.
A **parameter sweep** checks whether the result is robust or just lucky, and an
**interactive web app** lets anyone try it on any ticker without touching the code.

## Example: SPY, 1993–2026

`python backtest.py --csv data/SPY.csv --short 50 --long 200 --cost-bps 5 --monte-carlo 2000`

| Metric                | 50/200 Crossover | Buy & Hold |
|-----------------------|-----------------:|-----------:|
| Total Return          |        1,989.1%  |   2,672.7% |
| CAGR                  |           9.65%  |     10.59% |
| Max Drawdown          |         -33.72%  |    -55.19% |
| Annualized Volatility |          13.87%  |     18.72% |
| Sharpe Ratio          |            0.73  |       0.63 |

*31 trades, invested 77% of the time, 5 bps (0.05%) trading cost per trade. Data: Yahoo
Finance (dividend-adjusted), 1993-11-11 to 2026-11-25.*

**Takeaway:** the crossover strategy ended with less money than buy-and-hold, but it
avoided most of the 2008 crash, so its worst drawdown was much smaller and its
return *per unit of risk* (Sharpe) was higher. This is typical of trend-following rules:
they trade some return for a smoother ride.

![Price with moving averages](docs/images/SPY_price_moving_averages.png)
![Growth of $10,000](docs/images/SPY_equity_curve.png)

## Monte Carlo risk simulation

A backtest shows only **one** path: the one history happened to take. A different
sequence of good and bad years could have produced very different results. The Monte Carlo
simulation builds thousands of alternative 10-year histories out of pieces of the real
one and asks what range of outcomes is plausible.

**How it works (block bootstrap):** chop the historical daily returns into random
20-day chunks and glue them together into new 10-year paths. Chunks are used instead of
single days because markets have streaks: crashes and calm periods cluster, and
shuffling individual days would make crashes look milder than they really are. The
strategy and buy-and-hold are resampled with the **same random dates**, so in every
simulated history they face exactly the same market.

| 2,000 simulated 10-year paths, $10,000 start | Strategy | Buy & Hold |
|---|---:|---:|
| Final value: 5th percentile (a bad outcome)  | $13,549 | $11,800 |
| Final value: median                           | $25,575 | $28,204 |
| Final value: 95th percentile (a great outcome) | $46,493 | $62,518 |
| Max drawdown: median                          | -22.1% | -31.8% |
| Max drawdown: 5th percentile (a bad outcome)  | -38.3% | -50.0% |
| Chance of losing money after 10 years         | 0.9% | 2.8% |
| Chance of a drawdown of 30% or worse          | 20.4% | 57.9% |

The strategy ended ahead of buy-and-hold in 38.9% of simulations. The simulation confirms
the single backtest: buy-and-hold has the higher typical return, but the crossover
strategy narrows the range of outcomes, so its bad cases are less bad and deep drawdowns
are about a third as likely.

![Monte Carlo paths](docs/images/SPY_monte_carlo_paths.png)
![Monte Carlo drawdowns](docs/images/SPY_monte_carlo_drawdowns.png)

**A limitation to keep in mind:** the simulation resamples the strategy's *realized*
daily returns. It does not re-run the moving-average rule on new simulated prices. So it
measures how sensitive the results are to the *order* of good and bad periods, not
whether the rule itself would keep working in a different kind of market.

## Is 50/200 special, or just lucky?

`python backtest.py --csv data/SPY.csv --cost-bps 5 --sweep`

Picking the best-looking settings after the fact is the most common way backtests fool
people (*overfitting*). The sweep tests 29 short/long window pairs over the same dates.
**25 of 29 beat buy-and-hold's Sharpe ratio**, and the good results form a broad region
instead of a single lucky cell. The only pairs that did worse all used a 100-day long window. So
the trend-following effect looks robust on SPY, and 50/200 (outlined) isn't a cherry-picked
outlier.

![Parameter sweep](docs/images/SPY_parameter_sweep.png)

## Interactive web app

```bash
streamlit run app.py
```

This opens a page in your browser where you can type any ticker, move sliders for the
windows and trading cost, and see the backtest, Monte Carlo and parameter sweep update
live. You can also upload your own CSV. The app ([`app.py`](app.py)) contains only display
code. It calls the same tested functions as the command-line tool.

**Share it with the club for free:** push to GitHub, sign in at
[share.streamlit.io](https://share.streamlit.io) with your GitHub account, click
"Create app", choose this repo and `app.py`, and deploy. You get a public link anyone can
open.

## How the strategy works

1. Compute the average closing price over the last **50** days (short) and the last
   **200** days (long).
2. If the short average is **above** the long one, the trend is up: **hold the stock**.
3. Otherwise, **hold cash** (earning 0%).

Both window lengths can be changed from the command line.

### Avoiding look-ahead bias

A signal is calculated from a day's *closing* price, so in real life you could only act
on it **after** the market closed. The backtester therefore applies each signal starting
the **next** trading day (`Position = Signal.shift(1)` in
[`engine.py`](mits_backtester/engine.py)).

Without this one-day delay, the backtest would quietly use information it couldn't have
had at the time. For example, it would "buy" on the same day a big rally pushes the
short average above the long one, and so capture the rally that caused the signal.
Results like that look great on paper and can't be reproduced in real trading. A test
in [`tests/test_backtest.py`](tests/test_backtest.py) checks this rule.

## Installation

Requires Python 3.10 or newer.

```bash
git clone https://github.com/mamoonrkhan/mits-backtester.git
cd mits-backtester
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

Run on the included sample data (synthetic prices, so it works right away):

```bash
python backtest.py --csv data/sample.csv
```

Download real data from Yahoo Finance and run on it:

```bash
python scripts/download_data.py SPY --start 1993-01-01
python backtest.py --csv data/SPY.csv --short 50 --long 200
```

You can also use a CSV downloaded by hand from the Yahoo Finance website. It needs at
least `Date` and `Close` columns. `Adj Close` is used when it is present.

| Option         | Default  | Meaning                               |
|----------------|----------|---------------------------------------|
| `--csv`        | required | Path to the price CSV                 |
| `--short`      | 50       | Short moving-average window (days)    |
| `--long`       | 200      | Long moving-average window (days)     |
| `--capital`    | 10000    | Starting amount in dollars            |
| `--output-dir` | output   | Where the PNG charts are saved        |
| `--cost-bps`   | 0        | Trading cost per buy/sell in basis points (5 = 0.05%) |
| `--monte-carlo`| 0 (off)  | Number of Monte Carlo paths, e.g. 1000 |
| `--mc-years`   | 10       | Length of each simulated path (years) |
| `--block-size` | 20       | Days per resampled block (1 = independent days) |
| `--seed`       | 42       | Random seed, so results are repeatable |
| `--sweep`      | off      | Test 29 window pairs and save a Sharpe heatmap |

Run the tests with:

```bash
pytest
```

## What each metric means

All metrics are calculated from the daily portfolio value ("equity curve"). Annualized
figures assume **252 trading days per year**.

| Metric | Formula | In plain words |
|---|---|---|
| **Total Return** | `end / start - 1` | How much the money grew overall. |
| **CAGR** (compound annual growth rate) | `(end / start) ^ (1 / years) - 1` | The steady yearly growth rate that would produce the same result. Lets you compare periods of different lengths. |
| **Max Drawdown** | `min(value / running peak - 1)` | The worst drop from a high point to a later low. It shows how much pain you'd have had to sit through. |
| **Annualized Volatility** | `std(daily returns) × √252` | How much returns jump around. Higher means a bumpier ride. It's scaled by √252 because variance grows in proportion to time. |
| **Sharpe Ratio** | `mean(daily returns) / std(daily returns) × √252` | Return earned per unit of volatility (with a 0% risk-free rate). Higher is better. It's useful for comparing strategies that take different amounts of risk. |

## Project structure

```
backtest.py               Command-line entry point
mits_backtester/
    data.py               load_data(): read and clean the CSV
    strategies.py         compute_signals(): the moving-average crossover
    engine.py             run_backtest(): signals -> daily returns -> equity curves
    metrics.py            compute_metrics() and the individual metric functions
    montecarlo.py         run_monte_carlo(): block-bootstrap risk simulation
    sweep.py              parameter_sweep(): test many window pairs on the same dates
app.py                    Streamlit web app (display only; reuses the functions above)
    plotting.py           plot_results(): saves the two PNG charts
scripts/
    download_data.py      Download prices from Yahoo Finance
    make_sample_data.py   Regenerate the synthetic data/sample.csv
tests/                    pytest tests with small, hand-checkable examples
```

Every strategy follows the same contract. It takes the price table and returns it with a
`Signal` column (1 = own the stock, 0 = hold cash). So a new strategy is just a new
function in `strategies.py`.

## Limitations

The backtester makes some simplifying assumptions:

- Trading costs are a flat percentage per trade (`--cost-bps`). Taxes are ignored.
- Trades are assumed to fill at the closing price of the signal day, so the new position
  earns the *next* day's return. In practice that means trading right at the close
  (e.g. a market-on-close order). Trading at the next morning's open would give slightly
  different results because of overnight price gaps.
- Cash earns 0% interest.
- The portfolio is either 100% in the stock or 100% in cash.
- A single backtest on one historical path. Past performance doesn't guarantee future
  results, and choosing parameters that worked best in the past can overfit.

## Future work

- ~~**Monte Carlo risk simulation**~~: done in v1.1 (see above).
- **User-defined strategies:** choose or plug in strategies (e.g. RSI, momentum) from the
  command line without editing the engine.
- **Multiple tickers:** backtest a portfolio of several stocks, or compare one strategy
  across many tickers at once.
- ~~**Simple web interface**~~: done in v1.2 (`streamlit run app.py`).
- **Out-of-sample testing:** choose windows on one period (e.g. 1994–2010) and check
  them on a later one (2011–today), a stricter guard against overfitting than the sweep.
- A non-zero risk-free rate, so cash earns interest.

## Disclaimer

Educational project. This is not investment advice.

# Contributing to the MITS Backtester

Thanks for helping build the club's backtester! You don't need to be an expert.
If you can write a Python function, you can add a strategy.

## 1. Get the code running

```bash
git clone https://github.com/mits-fhda/mits-backtester.git
cd mits-backtester
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest                           # every test should pass before you change anything
```

Not a club org member yet? Ask an officer to invite you, or
[fork the repo](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/fork-a-repo)
and work on your own copy.

## 2. Make a branch

```bash
git checkout -b add-rsi-strategy
```

## 3. Add a strategy (the most common contribution)

Open [`mits_backtester/strategies.py`](mits_backtester/strategies.py). Every strategy
is one function with the same contract:

- **Input:** the price table (it has a `Price` column), plus your own settings.
- **Output:** a copy of the table with a `Signal` column added:
  `1` = fully invested, `0` = all cash, in between = partly invested, `NaN` = not enough
  history yet.
- **Optional:** columns named `"Line: something"` are drawn on the price chart.

Here's a template:

```python
def my_strategy_signals(prices, window=20):
    """One or two sentences: what the rule is and why it might work."""
    _check_history(prices, window)
    df = prices.copy()

    average = df["Price"].rolling(window).mean()
    df[f"Line: {window}-day average"] = average          # optional: show on the chart

    df["Signal"] = (df["Price"] > average).astype(float)  # your rule goes here
    df.loc[average.isna(), "Signal"] = float("nan")       # warm-up period
    return df
```

Then register it at the bottom of the same file:

```python
STRATEGIES = {
    ...
    "my_strategy": {"label": "My strategy", "function": my_strategy_signals},
}
```

That's it. It now shows up everywhere automatically, using its default settings:

- the command line: `python backtest.py --csv data/SPY.csv --strategy my_strategy`
- the strategy leaderboard: `--compare`
- the web app's strategy menu and leaderboard tab
- the test that checks every strategy follows the contract

Optional: to make its settings adjustable, add them to `strategy_settings()` in
`backtest.py` and add sliders in the sidebar section of `app.py`. Copy how the other
strategies do it.

### The one rule: no peeking into the future

A signal on day *t* may only use prices up to and including day *t*. The engine already
waits until the next day to act on it. So never use `.shift(-1)` or anything else that
looks at future rows. If a backtest looks too good to be true, check this first.

## 4. Add a test

Add a small test to [`tests/test_strategies.py`](tests/test_strategies.py) using a tiny
price series where you can work out the right answer by hand. Look at the existing tests
for examples. Then run:

```bash
pytest
```

## 5. Open a pull request

```bash
git add -A
git commit -m "Add RSI strategy"
git push -u origin add-rsi-strategy
```

Then open the link GitHub prints and create a pull request. Describe what your strategy
does and paste its leaderboard row (`python backtest.py --csv data/SPY.csv --compare`).
GitHub runs all the tests automatically. A green check means they passed.

## Ideas to work on

- New strategies: RSI, Bollinger band breakouts, dual momentum, combining trend + volatility targeting
- Out-of-sample testing (pick settings on old data, test on newer data)
- A non-zero risk-free rate for Sharpe, Sortino and alpha
- Portfolios of several tickers

Have an idea but not sure how to start? Post it in
[Discussions](https://github.com/mits-fhda/mits-backtester/discussions).

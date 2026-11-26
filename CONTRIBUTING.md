# Contributing

So you want to add something to the backtester. Nice! You don't need to be a great
programmer for this. Most contributions are a new strategy, and a strategy is just one
Python function. This guide walks you through adding one from start to finish.

If you get stuck anywhere, post in
[Discussions](https://github.com/mits-fhda/mits-backtester/discussions) or ask someone
at a meeting. Nobody expects you to figure out git alone.

## Getting set up

First, get the code onto your computer and make sure it runs:

```bash
git clone https://github.com/mits-fhda/mits-backtester.git
cd mits-backtester
python3 -m venv .venv
source .venv/bin/activate        # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest
```

That last command runs the tests. They should all pass before you change anything, so
if something fails here, it's a setup problem and not your fault. Ask for help.

You'll also want real data to try your strategy on:

```bash
python scripts/download_data.py SPY --start 1993-01-01
```

If you aren't in the MITS GitHub organization yet, ask an officer for an invite. In the
meantime you can [fork the repo](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/fork-a-repo)
and work on your own copy.

Before you start writing code, make a branch for your work so it stays separate from
everyone else's:

```bash
git checkout -b add-my-strategy
```

## Writing a strategy

All the strategies live in [`mits_backtester/strategies.py`](mits_backtester/strategies.py).
Each one gets a table of daily prices and adds a `Signal` column that says how much of the
stock to own on each day:

- `1` means all in
- `0` means all cash
- something in between, like `0.6`, means partly invested
- `NaN` means "not enough history to decide yet" (for example, the first few weeks of a
  20-day average)

Here's a simple example you can copy and change. It owns the stock whenever the price is
above its 20-day average:

```python
def my_strategy_signals(prices, window=20):
    """Own the stock while the price is above its recent average."""
    _check_history(prices, window)
    df = prices.copy()

    average = df["Price"].rolling(window).mean()
    df[f"Line: {window}-day average"] = average

    df["Signal"] = (df["Price"] > average).astype(float)
    df.loc[average.isna(), "Signal"] = float("nan")
    return df
```

The `Line:` column is optional. Any column whose name starts with `Line: ` gets drawn on
the price chart, which helps people see what your strategy is doing.

Then add your strategy to the `STRATEGIES` list at the bottom of the same file:

```python
STRATEGIES = {
    ...
    "my_strategy": {"label": "My strategy", "function": my_strategy_signals},
}
```

And that's it. Your strategy now shows up in the command line, in the web app's menu,
and in the leaderboard, using its default settings. Try it:

```bash
python backtest.py --csv data/SPY.csv --strategy my_strategy
python backtest.py --csv data/SPY.csv --compare
```

If you want people to be able to adjust your strategy's settings, add them to
`strategy_settings()` in `backtest.py` and add sliders to the sidebar in `app.py`. Copy
whatever the existing strategies do. This step is optional.

## Don't peek at the future

This is the one rule that really matters. On any given day, your strategy can only use
prices from that day or earlier. The backtester already waits until the next day before
acting on a signal, so you don't need to handle that yourself. Just never look at future
rows, for example with `.shift(-1)`.

It's an easy mistake to make, and it makes results look incredible. If your strategy
suddenly crushes the market, check for this first.

## Adding a test

There's already a test that checks every strategy returns signals between 0 and 1, and
it covers yours automatically. It's still worth writing one test of your own: make up a
tiny price series where you know what your strategy should do, and check that it does
it. There are examples in [`tests/test_strategies.py`](tests/test_strategies.py).

Run the tests again when you're done:

```bash
pytest
```

## Sharing your work

Save your changes and push them to GitHub:

```bash
git add -A
git commit -m "Add my strategy"
git push -u origin add-my-strategy
```

GitHub will print a link. Open it and create a pull request. In the description, say what
your strategy does and why you think it might work, and paste its row from the
`--compare` leaderboard. GitHub runs all the tests automatically. A green check means
everything passed, and then someone from the club will look it over.

## Looking for an idea?

Here are a few things we'd love to see:

- more strategies, like RSI, Bollinger band breakouts, or combining a trend rule with
  volatility targeting
- out-of-sample testing: pick the best settings using older data, then see how they do
  on newer data the strategy has never seen
- letting cash earn a realistic interest rate
- testing a portfolio of several tickers at once

If you have a different idea, post it in
[Discussions](https://github.com/mits-fhda/mits-backtester/discussions) first so others
can weigh in.

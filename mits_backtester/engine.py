"""The engine: turns a strategy's daily signals into what the portfolio was worth each day."""


def run_backtest(signals, initial_capital=10_000, cost_per_trade=0.0):
    """Run the strategy and buy-and-hold side by side over the same dates.

    `signals` comes from one of the strategy functions, so it has a "Price"
    column and a "Signal" column.

    The important detail is timing. A signal is worked out from a day's closing
    price, which means in real life you could only act on it once the market
    had closed. So the signal from one day sets the position for the next day.
    Without that delay, the backtest would get to trade on information it
    couldn't have had yet, and the results would look better than they really
    were.

    Both portfolios start on the first day the strategy has a signal, so
    they're compared over exactly the same stretch of time.

    `cost_per_trade` is the slice of the portfolio you lose every time you buy
    or sell, to cover fees and the bid/ask spread. 0.0005 is 0.05%, which
    traders call "5 basis points".

    To keep things simple, cash doesn't earn any interest.
    """
    # Skip the first few rows where the strategy doesn't have enough history to decide.
    df = signals.dropna(subset=["Signal"]).copy()

    # How much the stock moved each day, e.g. 0.01 for a 1% gain.
    # The first day has nothing to compare against, so we call it 0.
    df["Market_Return"] = df["Price"].pct_change().fillna(0.0)

    # This is the line that prevents look-ahead bias: yesterday's signal sets today's position.
    df["Position"] = df["Signal"].shift(1).fillna(0.0)

    # Fully invested earns the whole day's move, half invested earns half, cash earns nothing.
    df["Strategy_Return"] = df["Position"] * df["Market_Return"]

    # Any day the position changes, we bought or sold something, so we pay the trading cost.
    trades = df["Position"].diff().abs().fillna(0.0)
    df["Strategy_Return"] -= trades * cost_per_trade

    # Compound the daily returns to get the portfolio's value each day.
    df["BuyHold_Equity"] = initial_capital * (1 + df["Market_Return"]).cumprod()
    df["Strategy_Equity"] = initial_capital * (1 + df["Strategy_Return"]).cumprod()

    return df


def count_trades(positions):
    """How many times the position changed. Every buy or sell counts as one."""
    return int((positions.diff().abs() > 0).sum())


def time_in_market(positions):
    """How invested the strategy was on average, from 0 (always cash) to 1 (always all in)."""
    return float(positions.mean())

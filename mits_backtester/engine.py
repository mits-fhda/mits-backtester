"""The backtest engine: turns daily signals into portfolio value over time."""


def run_backtest(signals, initial_capital=10_000, cost_per_trade=0.0):
    """Simulate the strategy and buy-and-hold over the same period.

    `signals` is the output of a strategy function (it has "Price" and "Signal").

    Avoiding look-ahead bias:
        A signal is computed from day t's closing price, so in real life we
        could only trade on it AFTER the close. We therefore shift the signal
        forward by one day: the position we hold on day t+1 is the signal from
        day t. The strategy then earns day t+1's return (close t -> close t+1)
        only if the signal said "own it" at close t.

    Both portfolios start on the first day the strategy has a valid signal,
    so they cover exactly the same dates.

    Trading costs: `cost_per_trade` is the fraction of the portfolio lost each
    time we buy or sell (commissions + bid/ask spread + slippage). For example
    0.0005 means 0.05%, often written "5 basis points".

    Simplifications: cash earns 0%, and the whole portfolio is either fully
    invested or fully in cash.
    """
    # Drop the warm-up period where the strategy can't make a decision yet.
    df = signals.dropna(subset=["Signal"]).copy()

    # Daily return of the stock: today's price / yesterday's price - 1.
    # The first day has no "yesterday", so its return is set to 0.
    df["Market_Return"] = df["Price"].pct_change().fillna(0.0)

    # THE KEY LINE: yesterday's signal decides today's position.
    df["Position"] = df["Signal"].shift(1).fillna(0.0)

    # If we're in the market we earn the market's return, otherwise 0 (cash).
    df["Strategy_Return"] = df["Position"] * df["Market_Return"]

    # On days the position changes (a buy or a sell), pay the trading cost.
    trades = df["Position"].diff().abs().fillna(0.0)
    df["Strategy_Return"] -= trades * cost_per_trade

    # Growth of the starting capital: multiply together (1 + return) for every day.
    df["BuyHold_Equity"] = initial_capital * (1 + df["Market_Return"]).cumprod()
    df["Strategy_Equity"] = initial_capital * (1 + df["Strategy_Return"]).cumprod()

    return df


def count_trades(positions):
    """Number of times the position changed (each buy or sell counts as one trade)."""
    return int((positions.diff().abs() > 0).sum())


def time_in_market(positions):
    """Fraction of days the strategy held the stock (between 0 and 1)."""
    return float(positions.mean())

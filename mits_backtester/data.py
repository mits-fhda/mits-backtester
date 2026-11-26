"""Loading historical price data from CSV files."""

import pandas as pd


def load_data(csv_path):
    """Read a Yahoo Finance-style CSV and return a clean DataFrame.

    Expected columns: Date, Open, High, Low, Close, Adj Close, Volume.
    Only Date and Close are strictly required. `csv_path` can also be an
    open file (that's how the web app passes uploaded files).

    The returned DataFrame:
      * is indexed by date, sorted from oldest to newest
      * has a "Price" column that every other part of the backtester uses.
        It is "Adj Close" when available (it accounts for dividends and
        stock splits), otherwise "Close".
    """
    return clean_prices(pd.read_csv(csv_path))


def download_data(ticker, start="2000-01-01", end=None):
    """Download daily prices from Yahoo Finance, cleaned the same way as load_data.

    Needs the optional `yfinance` package and an internet connection.
    """
    import yfinance as yf  # imported here so the rest of the tool works without it

    raw = yf.Ticker(ticker).history(start=start, end=end, auto_adjust=False)
    if raw.empty:
        raise ValueError(f"No data returned for '{ticker}'. Check the ticker symbol.")
    raw.index = raw.index.tz_localize(None)  # plain dates, no timezone
    return clean_prices(raw.reset_index())   # turns the Date index back into a column


def clean_prices(df):
    """Shared cleaning steps for prices from a CSV or from a download."""
    df = df.copy()

    # Some exports have stray spaces in the header, e.g. " Close".
    df.columns = [col.strip() for col in df.columns]

    for required in ("Date", "Close"):
        if required not in df.columns:
            raise ValueError(f"CSV is missing the required '{required}' column")

    # Turn the Date text into real dates and use them as the row labels.
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.set_index("Date").sort_index()

    # Drop accidental duplicate dates, keeping the first one.
    df = df[~df.index.duplicated(keep="first")]

    price_column = "Adj Close" if "Adj Close" in df.columns else "Close"

    # errors="coerce" turns bad values (Yahoo sometimes writes "null") into NaN,
    # and then we drop those rows.
    df["Price"] = pd.to_numeric(df[price_column], errors="coerce")
    df = df.dropna(subset=["Price"])

    if len(df) < 2:
        raise ValueError("Need at least two rows of valid price data")

    return df

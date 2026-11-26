"""Getting price data into the backtester, either from a CSV file or straight from Yahoo Finance."""

import pandas as pd


def load_data(csv_path):
    """Read a CSV in Yahoo Finance's format and return a clean table of prices.

    Yahoo's files have Date, Open, High, Low, Close, Adj Close and Volume
    columns, but we only really need Date and Close. You can also pass an
    open file instead of a path, which is what the web app does with uploads.

    The table that comes back is sorted from oldest to newest, with the dates
    as row labels. It also gets a "Price" column, which is what the rest of
    the backtester uses. That's the Adj Close column when there is one,
    because it accounts for dividends and stock splits, and Close otherwise.
    """
    return clean_prices(pd.read_csv(csv_path))


def download_data(ticker, start="2000-01-01", end=None):
    """Download daily prices from Yahoo Finance and clean them up the same way load_data does.

    This needs the `yfinance` package and an internet connection.
    """
    import yfinance as yf  # imported in here so the rest of the tool still works without yfinance

    raw = yf.Ticker(ticker).history(start=start, end=end, auto_adjust=False)
    if raw.empty:
        raise ValueError(f"No data returned for '{ticker}'. Check the ticker symbol.")
    raw.index = raw.index.tz_localize(None)  # we just want plain dates, without timezones
    return clean_prices(raw.reset_index())   # make Date a normal column again, like in a CSV


def clean_prices(df):
    """The cleanup steps that both load_data and download_data need."""
    df = df.copy()

    # Some files have stray spaces in the column names, like " Close".
    df.columns = [col.strip() for col in df.columns]

    for required in ("Date", "Close"):
        if required not in df.columns:
            raise ValueError(f"CSV is missing the required '{required}' column")

    # Turn the date text into real dates, use them as row labels, and put them in order.
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.set_index("Date").sort_index()

    # If a date shows up twice, keep the first one.
    df = df[~df.index.duplicated(keep="first")]

    price_column = "Adj Close" if "Adj Close" in df.columns else "Close"

    # Yahoo sometimes writes "null" instead of a price. errors="coerce" turns
    # anything that isn't a number into NaN, and then we drop those rows.
    df["Price"] = pd.to_numeric(df[price_column], errors="coerce")
    df = df.dropna(subset=["Price"])

    if len(df) < 2:
        raise ValueError("Need at least two rows of valid price data")

    return df

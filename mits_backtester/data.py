"""Loading historical price data from CSV files."""

import pandas as pd


def load_data(csv_path):
    """Read a Yahoo Finance-style CSV and return a clean DataFrame.

    Expected columns: Date, Open, High, Low, Close, Adj Close, Volume.
    Only Date and Close are strictly required.

    The returned DataFrame:
      * is indexed by date, sorted from oldest to newest
      * has a "Price" column that every other part of the backtester uses.
        It is "Adj Close" when available (it accounts for dividends and
        stock splits), otherwise "Close".
    """
    df = pd.read_csv(csv_path)

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

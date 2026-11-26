"""Download daily price data from Yahoo Finance into a CSV the backtester can read.

Requires the optional `yfinance` package (included in requirements.txt).

Usage:
    python scripts/download_data.py SPY
    python scripts/download_data.py AAPL --start 2010-01-01
"""

import argparse
from pathlib import Path

import yfinance as yf

COLUMNS = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]


def main():
    parser = argparse.ArgumentParser(description="Download daily prices from Yahoo Finance.")
    parser.add_argument("ticker", help="Ticker symbol, e.g. SPY")
    parser.add_argument("--start", default="2000-01-01", help="First date (YYYY-MM-DD)")
    parser.add_argument("--end", default=None, help="Last date (YYYY-MM-DD), default: today")
    args = parser.parse_args()

    ticker = args.ticker.upper()
    # auto_adjust=False keeps both "Close" and "Adj Close", matching Yahoo's CSV format.
    df = yf.Ticker(ticker).history(start=args.start, end=args.end, auto_adjust=False)
    if df.empty:
        raise SystemExit(f"No data returned for {ticker}. Check the symbol and dates.")

    df = df[COLUMNS]
    df.index = df.index.tz_localize(None)  # drop the timezone so dates are plain YYYY-MM-DD
    df.index.name = "Date"

    out_path = Path(__file__).resolve().parent.parent / "data" / f"{ticker}.csv"
    out_path.parent.mkdir(exist_ok=True)
    df.to_csv(out_path, date_format="%Y-%m-%d")
    print(f"Saved {len(df)} rows for {ticker} to {out_path}")


if __name__ == "__main__":
    main()

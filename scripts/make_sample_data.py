"""Make data/sample.csv, a made-up stock price series for demos and testing.

The prices are random. Each day moves up or down by a random amount, with a
slight upward drift so it looks roughly like a real stock. Shipping made-up
data means anyone can try the tool right after downloading it, and we don't
have to share anyone else's data. The random seed is fixed, so this script
makes exactly the same file every time.

Usage:
    python scripts/make_sample_data.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
NUM_DAYS = 252 * 8          # about 8 years of trading days
START_PRICE = 100.0
DAILY_DRIFT = 0.0003        # average daily return (about 7.5% per year)
DAILY_VOLATILITY = 0.012    # typical size of a daily move (about 19% per year)


def main():
    rng = np.random.default_rng(SEED)
    dates = pd.bdate_range("2016-01-04", periods=NUM_DAYS)  # weekdays only

    daily_returns = rng.normal(DAILY_DRIFT, DAILY_VOLATILITY, NUM_DAYS)
    close = START_PRICE * np.cumprod(1 + daily_returns)

    # Make up believable Open/High/Low prices around each close so the file looks like Yahoo's.
    open_ = close * (1 + rng.normal(0, 0.003, NUM_DAYS))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.004, NUM_DAYS)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.004, NUM_DAYS)))
    volume = rng.integers(1_000_000, 5_000_000, NUM_DAYS)

    df = pd.DataFrame(
        {
            "Date": dates.strftime("%Y-%m-%d"),
            "Open": open_.round(2),
            "High": high.round(2),
            "Low": low.round(2),
            "Close": close.round(2),
            "Adj Close": close.round(2),
            "Volume": volume,
        }
    )

    out_path = Path(__file__).resolve().parent.parent / "data" / "sample.csv"
    out_path.parent.mkdir(exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"Wrote {len(df)} rows of synthetic data to {out_path}")


if __name__ == "__main__":
    main()

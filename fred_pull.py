"""
FRED macro data pull script.

Fetches a starter set of macro series from the FRED API and stores them
as parquet — one long-format master file, plus individual per-series files.

Requires the FRED_API_KEY environment variable to be set.
Get a free key at: https://fredaccount.stlouisfed.org/apikeys

Usage:
    set FRED_API_KEY=your_key_here   (Windows cmd)
    $env:FRED_API_KEY="your_key_here"  (PowerShell)
    python fred_pull.py
"""

import os
import sys
import time
import requests
import pandas as pd
from pathlib import Path

# Read API key from env var, or Streamlit secrets if running in Cloud
def get_api_key():
    key = os.environ.get("FRED_API_KEY")
    if not key:
        try:
            import streamlit as st
            key = st.secrets.get("FRED_API_KEY")
        except Exception:
            pass
    return key

BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

# Starter "broader" series set: rates/curve, inflation, labor, growth, Fed,
# consumer, housing. (Note: ISM PMI is not freely available via FRED — it's
# a proprietary ISM data product. INDPRO is included as a free proxy for
# manufacturing activity.)
SERIES = {
    # Rates / curve
    "DGS2":     "2-Year Treasury Yield",
    "DGS10":    "10-Year Treasury Yield",
    "DGS30":    "30-Year Treasury Yield",
    "T10Y2Y":   "10Y-2Y Treasury Spread",
    "T10Y3M":   "10Y-3M Treasury Spread",
    "FEDFUNDS": "Effective Federal Funds Rate",
    # Inflation
    "CPIAUCSL": "CPI All Items (SA)",
    "CPILFESL": "Core CPI (ex Food & Energy, SA)",
    "PCEPI":    "PCE Price Index",
    "PCEPILFE": "Core PCE Price Index",
    # Labor
    "UNRATE":   "Unemployment Rate",
    "PAYEMS":   "Nonfarm Payrolls",
    "ICSA":     "Initial Jobless Claims",
    # Growth
    "GDP":      "Nominal GDP",
    "GDPC1":    "Real GDP",
    "INDPRO":   "Industrial Production Index",
    # Consumer
    "RSAFS":    "Retail Sales",
    "UMCSENT":  "U. Michigan Consumer Sentiment",
    # Housing
    "HOUST":        "Housing Starts",
    "MORTGAGE30US": "30-Year Fixed Mortgage Rate",
}

OUTPUT_DIR = Path("data")
RAW_DIR = OUTPUT_DIR / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)


def fetch_series(series_id: str) -> pd.DataFrame:
    api_key = get_api_key()
    resp = requests.get(
        BASE_URL,
        params={
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
        },
        timeout=20,
    )
    resp.raise_for_status()
    obs = resp.json().get("observations", [])
    df = pd.DataFrame(obs)[["date", "value"]]
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")  # '.' -> NaN for missing
    df["series_id"] = series_id
    return df.dropna(subset=["value"])


def main():
    api_key = get_api_key()
    if not api_key:
        sys.exit("ERROR: Set the FRED_API_KEY environment variable before running this script.")
    all_frames = []
    print(f"Pulling {len(SERIES)} series from FRED...\n")

    for series_id, label in SERIES.items():
        try:
            df = fetch_series(series_id)
            df.to_parquet(RAW_DIR / f"{series_id}.parquet", index=False)
            all_frames.append(df)
            latest = df.iloc[-1]
            print(f"  {series_id:12s} {label:35s} latest: {latest['date'].date()} = {latest['value']}")
        except Exception as e:
            print(f"  {series_id:12s} FAILED: {e}")
        time.sleep(0.2)  # be polite to the API

    master = pd.concat(all_frames, ignore_index=True)
    master = master[["series_id", "date", "value"]].sort_values(["series_id", "date"])
    master.to_parquet(OUTPUT_DIR / "fred_master.parquet", index=False)

    print(f"\nSaved master file: {OUTPUT_DIR / 'fred_master.parquet'} ({len(master):,} rows)")
    print(f"Saved {len(all_frames)} individual series files in {RAW_DIR}/")


if __name__ == "__main__":
    main()

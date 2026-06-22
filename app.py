"""
Macro Dashboard — Streamlit app.
Reads data/fred_master.parquet (produced by fred_pull.py).
On first load, auto-pulls from FRED if data is missing.
Sidebar has a manual Refresh button.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path
import fred_pull

st.set_page_config(page_title="Macro Dashboard", layout="wide")

SERIES_LABELS = {
    # Rates / curve
    "DGS2":         "2-Year Treasury Yield",
    "DGS10":        "10-Year Treasury Yield",
    "DGS30":        "30-Year Treasury Yield",
    "T10Y2Y":       "10Y-2Y Treasury Spread",
    "T10Y3M":       "10Y-3M Treasury Spread",
    "FEDFUNDS":     "Effective Federal Funds Rate",
    # Inflation
    "CPIAUCSL":     "CPI All Items (SA)",
    "CPILFESL":     "Core CPI (ex Food & Energy, SA)",
    "PCEPI":        "PCE Price Index",
    "PCEPILFE":     "Core PCE Price Index",
    "T10YIE":       "10-Year Breakeven Inflation Rate",
    # Labor
    "UNRATE":       "Unemployment Rate",
    "PAYEMS":       "Nonfarm Payrolls",
    "ICSA":         "Initial Jobless Claims",
    # Growth
    "GDP":          "Nominal GDP",
    "GDPC1":        "Real GDP",
    "INDPRO":       "Industrial Production Index",
    # Consumer
    "RSAFS":        "Retail Sales",
    "UMCSENT":      "U. Michigan Consumer Sentiment",
    # Housing
    "HOUST":        "Housing Starts",
    "MORTGAGE30US": "30-Year Fixed Mortgage Rate",
    # Risk / markets
    "VIXCLS":       "VIX (CBOE Volatility Index)",
    "DCOILWTICO":   "WTI Crude Oil Price",
    "DTWEXBGS":     "Trade-Weighted US Dollar Index",
    "BAMLH0A0HYM2": "HY Credit Spread (OAS)",
    "BAMLC0A0CM":   "IG Credit Spread (OAS)",
}

DATA_PATH = Path("data/fred_master.parquet")


@st.cache_data
def load_data():
    df = pd.read_parquet(DATA_PATH)
    df["date"] = pd.to_datetime(df["date"])
    return df


def main():
    st.title("Macro Dashboard")

    # Auto-pull on first load if no data exists
    if not DATA_PATH.exists():
        with st.spinner("Pulling data from FRED — this takes ~30 seconds on first load..."):
            fred_pull.main()
        st.cache_data.clear()

    # Sidebar
    with st.sidebar:
        st.header("Data")
        if st.button("🔄 Refresh from FRED"):
            with st.spinner("Pulling latest data from FRED..."):
                fred_pull.main()
            st.cache_data.clear()
            st.rerun()

    df = load_data()
    last_updated = df["date"].max().date()
    st.caption(f"Data through {last_updated} — source: FRED")

    available = [s for s in SERIES_LABELS if s in df["series_id"].unique()]

    col_picker, col_range = st.columns([2, 1])
    with col_picker:
        series_id = st.selectbox(
            "Series",
            options=available,
            format_func=lambda s: f"{SERIES_LABELS.get(s, s)} ({s})",
        )
    with col_range:
        years_back = st.selectbox("Range", [1, 3, 5, 10, 20, "All"], index=2)

    sdf = df[df["series_id"] == series_id].sort_values("date")

    if years_back != "All":
        cutoff = sdf["date"].max() - pd.DateOffset(years=years_back)
        sdf = sdf[sdf["date"] >= cutoff]

    latest = sdf.iloc[-1]
    prior = sdf.iloc[-2] if len(sdf) > 1 else latest
    delta = latest["value"] - prior["value"]

    m1, m2, m3 = st.columns(3)
    m1.metric("Latest value", f"{latest['value']:,.2f}", f"{delta:+.2f}")
    m2.metric("As of", str(latest["date"].date()))
    m3.metric("Observations shown", f"{len(sdf):,}")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=sdf["date"], y=sdf["value"],
        mode="lines", line=dict(width=2, color="#2962ff"),
        name=series_id,
    ))
    fig.update_layout(
        height=480,
        margin=dict(l=20, r=20, t=20, b=20),
        xaxis_title=None,
        yaxis_title=SERIES_LABELS.get(series_id, series_id),
        template="plotly_white",
    )
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Raw data"):
        st.dataframe(sdf[["date", "value"]].sort_values("date", ascending=False), use_container_width=True)


if __name__ == "__main__":
    main()

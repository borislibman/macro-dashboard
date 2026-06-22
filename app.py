"""
Macro Dashboard — Streamlit app.
Reads data/fred_master.parquet (produced by fred_pull.py).
On first load, auto-pulls from FRED if data is missing.
Sidebar: manual Refresh button.
Tabs: Single Series | Overlay
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import fred_pull

st.set_page_config(page_title="Macro Dashboard", layout="wide")

SERIES_LABELS = {
    "DGS2":         "2-Year Treasury Yield",
    "DGS10":        "10-Year Treasury Yield",
    "DGS30":        "30-Year Treasury Yield",
    "T10Y2Y":       "10Y-2Y Treasury Spread",
    "T10Y3M":       "10Y-3M Treasury Spread",
    "FEDFUNDS":     "Effective Federal Funds Rate",
    "CPIAUCSL":     "CPI All Items (SA)",
    "CPILFESL":     "Core CPI (ex Food & Energy, SA)",
    "PCEPI":        "PCE Price Index",
    "PCEPILFE":     "Core PCE Price Index",
    "T10YIE":       "10-Year Breakeven Inflation Rate",
    "UNRATE":       "Unemployment Rate",
    "PAYEMS":       "Nonfarm Payrolls",
    "ICSA":         "Initial Jobless Claims",
    "GDP":          "Nominal GDP",
    "GDPC1":        "Real GDP",
    "INDPRO":       "Industrial Production Index",
    "RSAFS":        "Retail Sales",
    "UMCSENT":      "U. Michigan Consumer Sentiment",
    "HOUST":        "Housing Starts",
    "MORTGAGE30US": "30-Year Fixed Mortgage Rate",
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


def series_label(s):
    return f"{SERIES_LABELS.get(s, s)} ({s})"


def get_sdf(df, sid, years_back):
    sdf = df[df["series_id"] == sid].sort_values("date")
    if years_back != "All":
        cutoff = sdf["date"].max() - pd.DateOffset(years=years_back)
        sdf = sdf[sdf["date"] >= cutoff]
    return sdf


def single_chart_tab(df, available):
    col_picker, col_range = st.columns([2, 1])
    with col_picker:
        series_id = st.selectbox("Series", options=available, format_func=series_label, key="single_series")
    with col_range:
        years_back = st.selectbox("Range", [1, 3, 5, 10, 20, "All"], index=2, key="single_range")

    sdf = get_sdf(df, series_id, years_back)
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
        yaxis_title=SERIES_LABELS.get(series_id, series_id),
        template="plotly_white",
    )
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Raw data"):
        st.dataframe(sdf[["date", "value"]].sort_values("date", ascending=False), use_container_width=True)


def overlay_chart_tab(df, available):
    st.subheader("Overlay two series")
    col1, col2, col_range = st.columns([2, 2, 1])
    with col1:
        s1 = st.selectbox("Series 1", options=available, format_func=series_label, index=1, key="overlay_s1")
    with col2:
        s2 = st.selectbox("Series 2", options=available, format_func=series_label, index=6, key="overlay_s2")
    with col_range:
        years_back = st.selectbox("Range", [1, 3, 5, 10, 20, "All"], index=2, key="overlay_range")

    sdf1 = get_sdf(df, s1, years_back)
    sdf2 = get_sdf(df, s2, years_back)

    m1, m2 = st.columns(2)
    for col, sdf, sid in [(m1, sdf1, s1), (m2, sdf2, s2)]:
        latest = sdf.iloc[-1]
        prior = sdf.iloc[-2] if len(sdf) > 1 else latest
        col.metric(SERIES_LABELS.get(sid, sid), f"{latest['value']:,.2f}", f"{latest['value'] - prior['value']:+.2f}")

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(x=sdf1["date"], y=sdf1["value"], mode="lines",
                   line=dict(width=2, color="#2962ff"), name=SERIES_LABELS.get(s1, s1)),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(x=sdf2["date"], y=sdf2["value"], mode="lines",
                   line=dict(width=2, color="#e53935"), name=SERIES_LABELS.get(s2, s2)),
        secondary_y=True,
    )
    fig.update_yaxes(title_text=SERIES_LABELS.get(s1, s1), title_font=dict(color="#2962ff"),
                     tickfont=dict(color="#2962ff"), secondary_y=False)
    fig.update_yaxes(title_text=SERIES_LABELS.get(s2, s2), title_font=dict(color="#e53935"),
                     tickfont=dict(color="#e53935"), secondary_y=True)
    fig.update_layout(
        height=500,
        margin=dict(l=20, r=60, t=20, b=20),
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    st.plotly_chart(fig, use_container_width=True)


def main():
    st.title("Macro Dashboard")

    if not DATA_PATH.exists():
        with st.spinner("Pulling data from FRED — this takes ~30 seconds on first load..."):
            fred_pull.main()
        st.cache_data.clear()

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

    tab1, tab2 = st.tabs(["Single Series", "Overlay"])
    with tab1:
        single_chart_tab(df, available)
    with tab2:
        overlay_chart_tab(df, available)


if __name__ == "__main__":
    main()

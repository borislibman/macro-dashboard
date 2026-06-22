"""
Macro Dashboard — Bloomberg-style Streamlit app.
Tabs: Overview (scoreboard + chart) | Overlay | News & Calendar
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import fred_pull
import news_feed

st.set_page_config(page_title="Macro Dashboard", layout="wide", initial_sidebar_state="collapsed")

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  /* Global */
  html, body, [class*="css"] { font-family: 'Inter', 'Helvetica Neue', Arial, sans-serif; }
  .block-container { padding-top: 1.2rem; padding-bottom: 1rem; max-width: 1400px; }

  /* Hide default Streamlit chrome */
  #MainMenu, footer, header { visibility: hidden; }

  /* Title */
  h1 { font-size: 1.4rem !important; font-weight: 700 !important;
       letter-spacing: -0.02em; color: #0d1117; margin-bottom: 0 !important; }

  /* Tab styling */
  .stTabs [data-baseweb="tab-list"] { gap: 0; border-bottom: 2px solid #e2e8f0; }
  .stTabs [data-baseweb="tab"] {
    font-size: 0.78rem; font-weight: 600; letter-spacing: 0.04em;
    text-transform: uppercase; padding: 0.5rem 1.2rem;
    color: #64748b; border-bottom: 2px solid transparent; margin-bottom: -2px;
  }
  .stTabs [aria-selected="true"] { color: #0f172a !important; border-bottom-color: #0f172a !important; }

  /* Metric cards */
  .metric-card {
    background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px;
    padding: 0.7rem 1rem; margin-bottom: 0.5rem;
  }
  .metric-label { font-size: 0.68rem; font-weight: 600; letter-spacing: 0.05em;
                  text-transform: uppercase; color: #64748b; margin-bottom: 0.1rem; }
  .metric-value { font-size: 1.5rem; font-weight: 700; color: #0f172a; line-height: 1.1; }
  .metric-delta-pos { font-size: 0.75rem; font-weight: 600; color: #16a34a; }
  .metric-delta-neg { font-size: 0.75rem; font-weight: 600; color: #dc2626; }
  .metric-date { font-size: 0.68rem; color: #94a3b8; margin-top: 0.1rem; }

  /* Scoreboard table */
  .score-table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
  .score-table th {
    text-align: left; font-size: 0.68rem; font-weight: 700; letter-spacing: 0.06em;
    text-transform: uppercase; color: #64748b; padding: 0.4rem 0.6rem;
    border-bottom: 2px solid #e2e8f0; background: #f8fafc;
  }
  .score-table td { padding: 0.38rem 0.6rem; border-bottom: 1px solid #f1f5f9; color: #0f172a; }
  .score-table tr:hover td { background: #f0f9ff; cursor: pointer; }
  .score-table .cat-badge {
    display: inline-block; font-size: 0.62rem; font-weight: 700; letter-spacing: 0.05em;
    text-transform: uppercase; padding: 0.1rem 0.4rem; border-radius: 3px;
    background: #f1f5f9; color: #475569;
  }
  .val-pos { color: #16a34a; font-weight: 600; }
  .val-neg { color: #dc2626; font-weight: 600; }
  .val-neu { color: #64748b; }

  /* Section headers */
  .section-header {
    font-size: 0.68rem; font-weight: 700; letter-spacing: 0.08em;
    text-transform: uppercase; color: #64748b;
    border-bottom: 1px solid #e2e8f0; padding-bottom: 0.3rem; margin: 1rem 0 0.5rem;
  }

  /* Divider */
  hr { border: none; border-top: 1px solid #e2e8f0; margin: 0.8rem 0; }
</style>
""", unsafe_allow_html=True)

# ── Constants ──────────────────────────────────────────────────────────────────
CATEGORIES = {
    "Rates":    ["DGS2", "DGS10", "DGS30", "T10Y2Y", "T10Y3M", "FEDFUNDS"],
    "Inflation":["CPIAUCSL", "CPILFESL", "PCEPI", "PCEPILFE", "T10YIE"],
    "Labor":    ["UNRATE", "PAYEMS", "ICSA"],
    "Growth":   ["GDP", "GDPC1", "INDPRO", "RSAFS"],
    "Consumer": ["UMCSENT", "HOUST", "MORTGAGE30US"],
    "Risk":     ["VIXCLS", "DCOILWTICO", "DTWEXBGS", "BAMLH0A0HYM2", "BAMLC0A0CM"],
}

SERIES_LABELS = {
    "DGS2": "2Y Treasury", "DGS10": "10Y Treasury", "DGS30": "30Y Treasury",
    "T10Y2Y": "10Y-2Y Spread", "T10Y3M": "10Y-3M Spread", "FEDFUNDS": "Fed Funds Rate",
    "CPIAUCSL": "CPI All Items", "CPILFESL": "Core CPI", "PCEPI": "PCE Index",
    "PCEPILFE": "Core PCE", "T10YIE": "10Y Breakeven",
    "UNRATE": "Unemployment", "PAYEMS": "Nonfarm Payrolls", "ICSA": "Jobless Claims",
    "GDP": "Nominal GDP", "GDPC1": "Real GDP", "INDPRO": "Industrial Production",
    "RSAFS": "Retail Sales", "UMCSENT": "Consumer Sentiment",
    "HOUST": "Housing Starts", "MORTGAGE30US": "30Y Mortgage Rate",
    "VIXCLS": "VIX", "DCOILWTICO": "WTI Crude", "DTWEXBGS": "Dollar Index",
    "BAMLH0A0HYM2": "HY Spread", "BAMLC0A0CM": "IG Spread",
}

# Series where higher = bad (red) vs higher = good (green)
INVERSE = {"UNRATE", "ICSA", "VIXCLS", "BAMLH0A0HYM2", "BAMLC0A0CM",
           "CPIAUCSL", "CPILFESL", "PCEPI", "PCEPILFE"}

def fmt_value(sid, val):
    pct_series = {"DGS2","DGS10","DGS30","T10Y2Y","T10Y3M","FEDFUNDS",
                  "UNRATE","T10YIE","MORTGAGE30US","BAMLH0A0HYM2","BAMLC0A0CM"}
    if sid in pct_series:        return f"{val:.2f}%"
    if sid == "PAYEMS":          return f"{val/1000:.1f}M"
    if sid == "ICSA":            return f"{val:,.0f}"
    if sid in {"GDP","GDPC1"}:   return f"${val/1000:.1f}T"
    if sid == "RSAFS":           return f"${val/1000:.0f}B"
    if sid == "HOUST":           return f"{val:,.0f}K"
    if sid == "DCOILWTICO":      return f"${val:.2f}"
    if sid == "VIXCLS":          return f"{val:.2f}"
    return f"{val:,.2f}"

DATA_PATH = Path("data/fred_master.parquet")

@st.cache_data
def load_data():
    df = pd.read_parquet(DATA_PATH)
    df["date"] = pd.to_datetime(df["date"])
    return df

@st.cache_data(ttl=3600)
def load_news():
    return news_feed.fetch_all_news()

def get_sdf(df, sid, years_back="All"):
    sdf = df[df["series_id"] == sid].sort_values("date")
    if years_back != "All":
        cutoff = sdf["date"].max() - pd.DateOffset(years=years_back)
        sdf = sdf[sdf["date"] >= cutoff]
    return sdf

def get_recessions(df):
    rec = df[df["series_id"] == "USREC"].sort_values("date").copy()
    if rec.empty:
        return []
    rec["start"] = (rec["value"] == 1) & (rec["value"].shift(1) != 1)
    rec["end"]   = (rec["value"] == 1) & (rec["value"].shift(-1) != 1)
    starts = rec[rec["start"]]["date"].tolist()
    ends   = rec[rec["end"]]["date"].tolist()
    return list(zip(starts, ends))

def add_recession_shading(fig, recessions, secondary_y=False):
    for s, e in recessions:
        fig.add_vrect(x0=s, x1=e, fillcolor="#94a3b8", opacity=0.12,
                      layer="below", line_width=0)

def build_chart(df, sid, years_back=5, show_yoy=False):
    sdf = get_sdf(df, sid, years_back)
    recessions = get_recessions(df)

    if show_yoy and len(sdf) > 52:
        sdf = sdf.copy()
        sdf["yoy"] = sdf["value"].pct_change(periods=12 if sdf["date"].diff().median().days < 10 else 4) * 100
        sdf = sdf.dropna(subset=["yoy"])
        y_col, y_label = "yoy", f"{SERIES_LABELS.get(sid,sid)} — YoY %"
    else:
        y_col, y_label = "value", SERIES_LABELS.get(sid, sid)

    fig = go.Figure()
    add_recession_shading(fig, recessions)
    fig.add_trace(go.Scatter(
        x=sdf["date"], y=sdf[y_col], mode="lines",
        line=dict(width=2, color="#2563eb"), name=y_label,
        hovertemplate="%{x|%b %d, %Y}<br>%{y:.2f}<extra></extra>",
    ))
    if show_yoy:
        fig.add_hline(y=0, line=dict(color="#94a3b8", width=1, dash="dash"))
    fig.update_layout(
        height=340, margin=dict(l=10, r=10, t=10, b=10),
        plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
        xaxis=dict(showgrid=False, zeroline=False, tickfont=dict(size=10, color="#64748b"),
                   showline=True, linecolor="#e2e8f0"),
        yaxis=dict(gridcolor="#f1f5f9", zeroline=False, tickfont=dict(size=10, color="#64748b"),
                   title=dict(text=y_label, font=dict(size=10, color="#64748b")),
                   showline=False),
        showlegend=False,
        hovermode="x unified",
    )
    return fig

# ── Scoreboard ─────────────────────────────────────────────────────────────────
def build_scoreboard(df):
    rows = []
    for cat, series_list in CATEGORIES.items():
        for sid in series_list:
            sdf = df[df["series_id"] == sid].sort_values("date")
            if sdf.empty:
                continue
            latest = sdf.iloc[-1]
            prior  = sdf.iloc[-2] if len(sdf) > 1 else latest
            delta  = latest["value"] - prior["value"]
            rows.append({
                "sid": sid, "cat": cat,
                "name": SERIES_LABELS.get(sid, sid),
                "value": latest["value"],
                "fmt": fmt_value(sid, latest["value"]),
                "date": latest["date"].strftime("%b %d"),
                "delta": delta,
                "delta_pct": (delta / prior["value"] * 100) if prior["value"] != 0 else 0,
                "inverse": sid in INVERSE,
            })
    return rows

def render_scoreboard(rows, selected_sid):
    # Group by category
    by_cat = {}
    for r in rows:
        by_cat.setdefault(r["cat"], []).append(r)

    html = ['<table class="score-table"><thead><tr>',
            '<th>Series</th><th style="text-align:right">Latest</th>',
            '<th style="text-align:right">Chg</th><th style="text-align:right">Chg%</th>',
            '<th>As Of</th></tr></thead><tbody>']

    for cat, cat_rows in by_cat.items():
        html.append(f'<tr><td colspan="5" style="padding:0.5rem 0.6rem 0.2rem;'
                    f'font-size:0.65rem;font-weight:700;letter-spacing:0.07em;'
                    f'text-transform:uppercase;color:#94a3b8;background:#f8fafc">{cat}</td></tr>')
        for r in cat_rows:
            is_sel = r["sid"] == selected_sid
            row_style = "background:#eff6ff;" if is_sel else ""
            up = r["delta"] >= 0
            good = (up and not r["inverse"]) or (not up and r["inverse"])
            cls = "val-pos" if good else "val-neg"
            arrow = "▲" if up else "▼"
            delta_str = f'{arrow} {abs(r["delta"]):.2f}'
            dpct_str  = f'{abs(r["delta_pct"]):.2f}%'
            html.append(
                f'<tr style="{row_style}" onclick="window.location.href=\'?sid={r["sid"]}\'">'
                f'<td>{r["name"]}</td>'
                f'<td style="text-align:right;font-weight:600">{r["fmt"]}</td>'
                f'<td style="text-align:right" class="{cls}">{delta_str}</td>'
                f'<td style="text-align:right" class="{cls}">{dpct_str}</td>'
                f'<td style="color:#94a3b8">{r["date"]}</td></tr>'
            )
    html.append('</tbody></table>')
    return "".join(html)

# ── Overview tab ───────────────────────────────────────────────────────────────
def overview_tab(df):
    rows = build_scoreboard(df)
    all_sids = [r["sid"] for r in rows]

    col_board, col_chart = st.columns([1, 1.6], gap="large")

    with col_board:
        st.markdown('<div class="section-header">All Series</div>', unsafe_allow_html=True)
        selected = st.selectbox("Select series", all_sids,
                                format_func=lambda s: SERIES_LABELS.get(s, s),
                                label_visibility="collapsed", key="overview_select")
        st.markdown(render_scoreboard(rows, selected), unsafe_allow_html=True)

    with col_chart:
        sdf = get_sdf(df, selected)
        latest = sdf.iloc[-1]
        prior  = sdf.iloc[-2] if len(sdf) > 1 else latest
        delta  = latest["value"] - prior["value"]
        good   = (delta >= 0 and selected not in INVERSE) or (delta < 0 and selected in INVERSE)

        st.markdown(f'<div class="section-header">{SERIES_LABELS.get(selected, selected)}</div>',
                    unsafe_allow_html=True)

        m1, m2, m3 = st.columns(3)
        m1.markdown(f"""<div class="metric-card">
            <div class="metric-label">Latest</div>
            <div class="metric-value">{fmt_value(selected, latest["value"])}</div>
            <div class="metric-date">{latest["date"].strftime("%b %d, %Y")}</div>
        </div>""", unsafe_allow_html=True)
        delta_cls = "metric-delta-pos" if good else "metric-delta-neg"
        arrow = "▲" if delta >= 0 else "▼"
        m2.markdown(f"""<div class="metric-card">
            <div class="metric-label">Change</div>
            <div class="metric-value" style="font-size:1.2rem">
              <span class="{delta_cls}">{arrow} {fmt_value(selected, abs(delta))}</span>
            </div>
            <div class="metric-date">vs prior period</div>
        </div>""", unsafe_allow_html=True)
        m3.markdown(f"""<div class="metric-card">
            <div class="metric-label">Series</div>
            <div class="metric-value" style="font-size:1rem;color:#64748b">{selected}</div>
            <div class="metric-date">{len(sdf):,} observations</div>
        </div>""", unsafe_allow_html=True)

        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            years_back = st.select_slider("Range", [1, 2, 3, 5, 10, 20, "All"],
                                          value=5, key="ov_range")
        with c2:
            show_yoy = st.toggle("YoY %", value=False, key="ov_yoy")

        fig = build_chart(df, selected, years_back, show_yoy)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

# ── Overlay tab ────────────────────────────────────────────────────────────────
def overlay_tab(df):
    all_sids = [s for cat in CATEGORIES.values() for s in cat]
    st.markdown('<div class="section-header">Compare Two Series</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        s1 = st.selectbox("Series 1", all_sids, format_func=lambda s: SERIES_LABELS.get(s,s),
                          index=1, key="ov_s1")
    with col2:
        s2 = st.selectbox("Series 2", all_sids, format_func=lambda s: SERIES_LABELS.get(s,s),
                          index=6, key="ov_s2")
    with col3:
        yb = st.selectbox("Range", [1, 3, 5, 10, 20, "All"], index=2, key="ov_yr")

    sdf1 = get_sdf(df, s1, yb)
    sdf2 = get_sdf(df, s2, yb)
    recessions = get_recessions(df)

    m1, m2 = st.columns(2)
    for col, sdf, sid in [(m1, sdf1, s1), (m2, sdf2, s2)]:
        l = sdf.iloc[-1]; p = sdf.iloc[-2] if len(sdf)>1 else l
        d = l["value"] - p["value"]
        good = (d>=0 and sid not in INVERSE) or (d<0 and sid in INVERSE)
        cls = "metric-delta-pos" if good else "metric-delta-neg"
        arr = "▲" if d>=0 else "▼"
        col.markdown(f"""<div class="metric-card">
            <div class="metric-label">{SERIES_LABELS.get(sid,sid)}</div>
            <div class="metric-value">{fmt_value(sid, l["value"])}</div>
            <div class="{cls}">{arr} {fmt_value(sid, abs(d))}</div>
            <div class="metric-date">{l["date"].strftime("%b %d, %Y")}</div>
        </div>""", unsafe_allow_html=True)

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    add_recession_shading(fig, recessions)
    fig.add_trace(go.Scatter(x=sdf1["date"], y=sdf1["value"], mode="lines",
                             line=dict(width=2, color="#2563eb"), name=SERIES_LABELS.get(s1,s1),
                             hovertemplate="%{x|%b %d, %Y}<br>%{y:.2f}<extra></extra>"),
                  secondary_y=False)
    fig.add_trace(go.Scatter(x=sdf2["date"], y=sdf2["value"], mode="lines",
                             line=dict(width=2, color="#dc2626"), name=SERIES_LABELS.get(s2,s2),
                             hovertemplate="%{x|%b %d, %Y}<br>%{y:.2f}<extra></extra>"),
                  secondary_y=True)
    fig.update_yaxes(title_text=SERIES_LABELS.get(s1,s1), title_font=dict(color="#2563eb",size=10),
                     tickfont=dict(color="#2563eb",size=10), gridcolor="#f1f5f9", secondary_y=False)
    fig.update_yaxes(title_text=SERIES_LABELS.get(s2,s2), title_font=dict(color="#dc2626",size=10),
                     tickfont=dict(color="#dc2626",size=10), showgrid=False, secondary_y=True)
    fig.update_layout(height=400, margin=dict(l=10,r=10,t=10,b=10),
                      plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
                      xaxis=dict(showgrid=False, tickfont=dict(size=10,color="#64748b"),
                                 showline=True, linecolor="#e2e8f0"),
                      legend=dict(orientation="h", y=1.08, x=0, font=dict(size=11)),
                      hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

# ── News tab ───────────────────────────────────────────────────────────────────
def news_tab():
    st.markdown('<div class="section-header">Economic Calendar & Headlines</div>', unsafe_allow_html=True)
    if st.button("🔄 Refresh", key="news_refresh"):
        st.cache_data.clear(); st.rerun()

    with st.spinner("Loading..."):
        data = load_news()

    col_cal, col_news = st.columns([1, 1.2], gap="large")

    with col_cal:
        st.markdown('<div class="section-header">Upcoming Releases — 14 days</div>', unsafe_allow_html=True)
        from datetime import date as dt
        today_str = dt.today().isoformat()
        by_date = {}
        for item in data.get("calendar", []):
            by_date.setdefault(item["date"], []).append(item)
        for rdate, items in sorted(by_date.items()):
            tier1 = [i["release_name"] for i in items if i.get("tier1")]
            others = [i["release_name"] for i in items if not i.get("tier1")]
            label = "**Today**" if rdate == today_str else rdate
            badge = " 🔴" if tier1 else ""
            with st.expander(f"{label} — {len(items)} releases{badge}", expanded=(rdate==today_str)):
                for n in tier1:   st.markdown(f"🔴 **{n}**")
                for n in others:  st.markdown(f"· {n}")

    with col_news:
        st.markdown('<div class="section-header">Federal Reserve</div>', unsafe_allow_html=True)
        for item in data.get("fed", [])[:8]:
            t, l = item.get("title",""), item.get("link","")
            if t: st.markdown(f"· [{t}]({l})" if l else f"· {t}")
        st.markdown('<div class="section-header" style="margin-top:1rem">BEA Releases</div>', unsafe_allow_html=True)
        for item in data.get("bea", [])[:8]:
            t, l = item.get("title",""), item.get("link","")
            if t: st.markdown(f"· [{t}]({l})" if l else f"· {t}")

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    if not DATA_PATH.exists():
        with st.spinner("Pulling data from FRED — first load takes ~30s..."):
            fred_pull.main()
        st.cache_data.clear()

    with st.sidebar:
        st.markdown("### Macro Dashboard")
        if st.button("🔄 Refresh FRED Data"):
            with st.spinner("Pulling..."):
                fred_pull.main()
            st.cache_data.clear()
            st.rerun()

    df = load_data()
    last = df["date"].max().date()

    st.markdown(
        f'<h1>Macro Dashboard '
        f'<span style="font-size:0.75rem;font-weight:400;color:#94a3b8;margin-left:0.5rem">'
        f'Data through {last} · FRED</span></h1>',
        unsafe_allow_html=True
    )

    tab1, tab2, tab3 = st.tabs(["OVERVIEW", "OVERLAY", "NEWS & CALENDAR"])
    with tab1: overview_tab(df)
    with tab2: overlay_tab(df)
    with tab3: news_tab()

if __name__ == "__main__":
    main()

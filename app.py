"""
Macro Dashboard — Dark theme, Bloomberg-style, with macro analysis.
Tabs: Overview (analysis + scoreboard + chart) | Overlay | News & Calendar
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
from datetime import date as dt
import fred_pull
import news_feed

st.set_page_config(page_title="Macro Dashboard", layout="wide", initial_sidebar_state="collapsed")

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  html, body, [class*="css"] { font-family: 'Inter','Helvetica Neue',Arial,sans-serif; }
  .block-container { padding-top:1rem; padding-bottom:1rem; max-width:1400px; }
  #MainMenu, footer, header { visibility:hidden; }

  h1 { font-size:1.3rem !important; font-weight:700 !important;
       letter-spacing:-0.02em; color:#e6edf3; margin-bottom:0 !important; }

  /* Tabs */
  .stTabs [data-baseweb="tab-list"] { gap:0; border-bottom:1px solid #30363d; }
  .stTabs [data-baseweb="tab"] {
    font-size:0.72rem; font-weight:700; letter-spacing:0.06em; text-transform:uppercase;
    padding:0.5rem 1.2rem; color:#7d8590;
    border-bottom:2px solid transparent; margin-bottom:-1px;
  }
  .stTabs [aria-selected="true"] { color:#58a6ff !important; border-bottom-color:#58a6ff !important; }

  /* Metric cards */
  .mc { background:#161b22; border:1px solid #30363d; border-radius:6px;
        padding:0.7rem 1rem; margin-bottom:0.5rem; }
  .mc-label { font-size:0.65rem; font-weight:700; letter-spacing:0.06em;
              text-transform:uppercase; color:#7d8590; margin-bottom:0.15rem; }
  .mc-value { font-size:1.45rem; font-weight:700; color:#e6edf3; line-height:1.1; }
  .mc-date  { font-size:0.65rem; color:#484f58; margin-top:0.1rem; }
  .dpos { font-size:0.75rem; font-weight:600; color:#3fb950; }
  .dneg { font-size:0.75rem; font-weight:600; color:#f85149; }

  /* Scoreboard */
  .stbl { width:100%; border-collapse:collapse; font-size:0.8rem; }
  .stbl th { text-align:left; font-size:0.62rem; font-weight:700; letter-spacing:0.07em;
             text-transform:uppercase; color:#7d8590; padding:0.35rem 0.5rem;
             border-bottom:1px solid #30363d; background:#0d1117; }
  .stbl td { padding:0.32rem 0.5rem; border-bottom:1px solid #1c2128; color:#e6edf3; }
  .stbl tr:hover td { background:#1c2128; cursor:pointer; }
  .stbl .cat-row td { font-size:0.62rem; font-weight:700; letter-spacing:0.07em;
                      text-transform:uppercase; color:#484f58;
                      background:#0d1117; padding:0.4rem 0.5rem 0.15rem; }
  .vpos { color:#3fb950; font-weight:600; }
  .vneg { color:#f85149; font-weight:600; }
  .vnu  { color:#7d8590; }

  /* Analysis panel */
  .ap { background:#161b22; border:1px solid #30363d; border-radius:8px;
        padding:1rem 1.2rem; margin-bottom:1rem; }
  .ap-title { font-size:0.65rem; font-weight:700; letter-spacing:0.07em;
              text-transform:uppercase; color:#7d8590; margin-bottom:0.6rem; }
  .regime-badge { display:inline-block; font-size:0.8rem; font-weight:700;
                  padding:0.25rem 0.8rem; border-radius:4px; margin-bottom:0.8rem; }
  .regime-green { background:#0d2818; color:#3fb950; border:1px solid #238636; }
  .regime-yellow { background:#2a1f00; color:#d29922; border:1px solid #9e6a03; }
  .regime-red { background:#2d1117; color:#f85149; border:1px solid #da3633; }

  .sig-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:0.5rem; margin-top:0.5rem; }
  .sig-item { background:#0d1117; border:1px solid #30363d; border-radius:4px; padding:0.4rem 0.6rem; }
  .sig-label { font-size:0.6rem; font-weight:700; letter-spacing:0.05em;
               text-transform:uppercase; color:#484f58; }
  .sig-val-green { font-size:0.8rem; font-weight:600; color:#3fb950; }
  .sig-val-yellow { font-size:0.8rem; font-weight:600; color:#d29922; }
  .sig-val-red   { font-size:0.8rem; font-weight:600; color:#f85149; }

  .sec-hdr { font-size:0.62rem; font-weight:700; letter-spacing:0.08em;
             text-transform:uppercase; color:#484f58;
             border-bottom:1px solid #21262d; padding-bottom:0.3rem; margin:0.8rem 0 0.4rem; }
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
CATEGORIES = {
    "Rates":     ["DGS2","DGS10","DGS30","T10Y2Y","T10Y3M","FEDFUNDS"],
    "Inflation": ["CPIAUCSL","CPILFESL","PCEPI","PCEPILFE","T10YIE"],
    "Labor":     ["UNRATE","PAYEMS","ICSA"],
    "Growth":    ["GDP","GDPC1","INDPRO","RSAFS"],
    "Consumer":  ["UMCSENT","HOUST","MORTGAGE30US"],
    "Risk":      ["VIXCLS","DCOILWTICO","DTWEXBGS","BAMLH0A0HYM2","BAMLC0A0CM"],
}
SERIES_LABELS = {
    "DGS2":"2Y Treasury","DGS10":"10Y Treasury","DGS30":"30Y Treasury",
    "T10Y2Y":"10Y-2Y Spread","T10Y3M":"10Y-3M Spread","FEDFUNDS":"Fed Funds",
    "CPIAUCSL":"CPI","CPILFESL":"Core CPI","PCEPI":"PCE","PCEPILFE":"Core PCE",
    "T10YIE":"10Y Breakeven","UNRATE":"Unemployment","PAYEMS":"Nonfarm Payrolls",
    "ICSA":"Jobless Claims","GDP":"Nominal GDP","GDPC1":"Real GDP",
    "INDPRO":"Indust. Production","RSAFS":"Retail Sales","UMCSENT":"Consumer Sentiment",
    "HOUST":"Housing Starts","MORTGAGE30US":"30Y Mortgage","VIXCLS":"VIX",
    "DCOILWTICO":"WTI Crude","DTWEXBGS":"Dollar Index",
    "BAMLH0A0HYM2":"HY Spread","BAMLC0A0CM":"IG Spread",
}
INVERSE = {"UNRATE","ICSA","VIXCLS","BAMLH0A0HYM2","BAMLC0A0CM","CPIAUCSL","CPILFESL","PCEPI","PCEPILFE"}

CHART_COLORS = ["#58a6ff","#f85149","#3fb950","#d29922","#bc8cff","#39d353"]

def fmt_value(sid, val):
    pct = {"DGS2","DGS10","DGS30","T10Y2Y","T10Y3M","FEDFUNDS","UNRATE","T10YIE","MORTGAGE30US","BAMLH0A0HYM2","BAMLC0A0CM"}
    if sid in pct:             return f"{val:.2f}%"
    if sid == "PAYEMS":        return f"{val/1000:.1f}M"
    if sid == "ICSA":          return f"{val:,.0f}"
    if sid in {"GDP","GDPC1"}: return f"${val/1000:.1f}T"
    if sid == "RSAFS":         return f"${val/1000:.0f}B"
    if sid == "HOUST":         return f"{val:,.0f}K"
    if sid == "DCOILWTICO":    return f"${val:.2f}"
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
    rec = df[df["series_id"]=="USREC"].sort_values("date").copy()
    if rec.empty: return []
    rec["start"] = (rec["value"]==1) & (rec["value"].shift(1)!=1)
    rec["end"]   = (rec["value"]==1) & (rec["value"].shift(-1)!=1)
    return list(zip(rec[rec["start"]]["date"].tolist(), rec[rec["end"]]["date"].tolist()))

def add_recession_shading(fig, recessions):
    for s, e in recessions:
        fig.add_vrect(x0=s, x1=e, fillcolor="#7d8590", opacity=0.1, layer="below", line_width=0)

# ── Macro Analysis ─────────────────────────────────────────────────────────────
def compute_macro_snapshot(df):
    def latest_val(sid):
        sdf = df[df["series_id"]==sid].sort_values("date")
        return (sdf.iloc[-1]["value"] if not sdf.empty else None)

    def yoy_pct(sid, periods=12):
        sdf = df[df["series_id"]==sid].sort_values("date")
        if len(sdf) < periods+2: return None
        v_now, v_then = sdf.iloc[-1]["value"], sdf.iloc[-1-periods]["value"]
        return (v_now/v_then - 1)*100 if v_then != 0 else None

    signals = {}

    # Yield curve
    s102 = latest_val("T10Y2Y")
    if s102 is not None:
        if s102 < -0.25:   signals["Yield Curve"]  = (f"{s102:+.2f}% Inverted",  "red")
        elif s102 < 0.5:   signals["Yield Curve"]  = (f"{s102:+.2f}% Flat",      "yellow")
        else:              signals["Yield Curve"]  = (f"{s102:+.2f}% Normal",    "green")

    # CPI YoY
    cpi_yoy = yoy_pct("CPIAUCSL", 12)
    if cpi_yoy is not None:
        if cpi_yoy > 4:    signals["CPI YoY"]      = (f"{cpi_yoy:.1f}% Elevated", "red")
        elif cpi_yoy > 2.5:signals["CPI YoY"]      = (f"{cpi_yoy:.1f}% Above 2%", "yellow")
        else:              signals["CPI YoY"]      = (f"{cpi_yoy:.1f}% ~Target",  "green")

    # Core PCE YoY
    pce_yoy = yoy_pct("PCEPILFE", 12)
    if pce_yoy is not None:
        if pce_yoy > 3:    signals["Core PCE YoY"] = (f"{pce_yoy:.1f}% High",     "red")
        elif pce_yoy > 2.5:signals["Core PCE YoY"] = (f"{pce_yoy:.1f}% Above 2%", "yellow")
        else:              signals["Core PCE YoY"] = (f"{pce_yoy:.1f}% ~Target",  "green")

    # Unemployment
    unemp = latest_val("UNRATE")
    if unemp is not None:
        if unemp < 4.5:    signals["Unemployment"] = (f"{unemp:.1f}% Tight",     "green")
        elif unemp < 5.5:  signals["Unemployment"] = (f"{unemp:.1f}% Moderate",  "yellow")
        else:              signals["Unemployment"] = (f"{unemp:.1f}% Loose",     "red")

    # Real Fed Funds (Fed Funds minus CPI YoY)
    ff = latest_val("FEDFUNDS")
    if ff is not None and cpi_yoy is not None:
        real_ff = ff - cpi_yoy
        if real_ff > 1.5:  signals["Real Fed Funds"]= (f"{real_ff:+.1f}% Restrictive","red")
        elif real_ff > 0:  signals["Real Fed Funds"]= (f"{real_ff:+.1f}% Mildly Tight","yellow")
        else:              signals["Real Fed Funds"]= (f"{real_ff:+.1f}% Accommodative","green")

    # VIX
    vix = latest_val("VIXCLS")
    if vix is not None:
        if vix < 15:       signals["VIX"]          = (f"{vix:.1f} Complacent",   "yellow")
        elif vix < 20:     signals["VIX"]          = (f"{vix:.1f} Low",          "green")
        elif vix < 30:     signals["VIX"]          = (f"{vix:.1f} Elevated",     "yellow")
        else:              signals["VIX"]          = (f"{vix:.1f} Fear",         "red")

    # HY spreads
    hy = latest_val("BAMLH0A0HYM2")
    if hy is not None:
        if hy < 3.5:       signals["HY Spreads"]   = (f"{hy:.2f}% Tight",       "green")
        elif hy < 5.5:     signals["HY Spreads"]   = (f"{hy:.2f}% Normal",      "yellow")
        else:              signals["HY Spreads"]   = (f"{hy:.2f}% Wide",        "red")

    # Determine regime
    counts = {"red":0,"yellow":0,"green":0}
    for _,(_, c) in signals.items(): counts[c] += 1

    if counts["red"] >= 4:
        regime = ("⚠ Recession Risk / Stagflation", "red")
    elif counts["red"] >= 2 and counts["green"] <= 2:
        regime = ("Late Cycle / Slowing", "yellow")
    elif counts["green"] >= 5:
        regime = ("Expansion / Risk-On", "green")
    elif counts["green"] >= 3 and counts["red"] <= 1:
        regime = ("Moderate Growth / Goldilocks", "green")
    else:
        regime = ("Mixed / Transition", "yellow")

    return signals, regime, {"cpi_yoy": cpi_yoy, "pce_yoy": pce_yoy, "ff": ff,
                              "unemp": unemp, "vix": vix, "hy": hy, "s102": s102}

def render_analysis(df):
    signals, regime, vals = compute_macro_snapshot(df)
    regime_label, regime_color = regime
    regime_cls = f"regime-{regime_color}"

    sig_items = ""
    for label, (val_str, color) in signals.items():
        sig_items += f"""<div class="sig-item">
            <div class="sig-label">{label}</div>
            <div class="sig-val-{color}">{val_str}</div>
        </div>"""

    # Narrative bullets
    bullets = []
    if vals.get("s102") is not None:
        if vals["s102"] < 0:
            bullets.append(f"Yield curve inverted ({vals['s102']:+.2f}%) — historically a leading recession indicator.")
        else:
            bullets.append(f"Yield curve positive at {vals['s102']:+.2f}% — no inversion signal currently.")
    if vals.get("cpi_yoy") is not None and vals.get("ff") is not None:
        real = vals["ff"] - vals["cpi_yoy"]
        if real > 0:
            bullets.append(f"Real Fed Funds rate is positive ({real:+.1f}%) — policy is restrictive, acting as a drag on growth.")
        else:
            bullets.append(f"Real Fed Funds rate is negative ({real:+.1f}%) — policy remains accommodative despite headline rate.")
    if vals.get("vix") is not None and vals.get("hy") is not None:
        if vals["vix"] < 20 and vals["hy"] < 4:
            bullets.append(f"Risk sentiment benign — VIX at {vals['vix']:.1f} and HY spreads tight at {vals['hy']:.2f}%.")
        elif vals["vix"] > 25 or vals["hy"] > 6:
            bullets.append(f"Risk-off conditions — VIX elevated at {vals['vix']:.1f} and/or HY spreads wide at {vals['hy']:.2f}%.")
    if vals.get("unemp") is not None and vals.get("cpi_yoy") is not None:
        if vals["unemp"] < 4.5 and vals["cpi_yoy"] > 3:
            bullets.append(f"Stagflationary mix: unemployment low ({vals['unemp']:.1f}%) while inflation runs above target ({vals['cpi_yoy']:.1f}% YoY).")

    bullets_html = "".join(f"<div style='font-size:0.8rem;color:#8b949e;margin-bottom:0.3rem'>· {b}</div>" for b in bullets)

    st.markdown(f"""<div class="ap">
        <div class="ap-title">Macro Snapshot</div>
        <div class="regime-badge {regime_cls}">{regime_label}</div>
        <div class="sig-grid">{sig_items}</div>
        <div style="margin-top:0.8rem">{bullets_html}</div>
    </div>""", unsafe_allow_html=True)

# ── Chart ──────────────────────────────────────────────────────────────────────
def build_chart(df, sid, years_back=5, show_yoy=False):
    sdf = get_sdf(df, sid, years_back)
    recessions = get_recessions(df)
    if show_yoy and len(sdf) > 14:
        sdf = sdf.copy()
        freq_days = sdf["date"].diff().median().days
        periods = 12 if freq_days < 20 else (4 if freq_days < 100 else 1)
        sdf["plot_val"] = sdf["value"].pct_change(periods=periods)*100
        sdf = sdf.dropna(subset=["plot_val"])
        y_col, y_label = "plot_val", f"{SERIES_LABELS.get(sid,sid)} YoY %"
    else:
        y_col, y_label = "value", SERIES_LABELS.get(sid, sid)

    fig = go.Figure()
    add_recession_shading(fig, recessions)
    fig.add_trace(go.Scatter(
        x=sdf["date"], y=sdf[y_col], mode="lines",
        line=dict(width=1.8, color="#58a6ff"), name=y_label,
        hovertemplate="%{x|%b %d, %Y}  %{y:.2f}<extra></extra>",
    ))
    if show_yoy:
        fig.add_hline(y=0, line=dict(color="#484f58", width=1, dash="dot"))
    fig.update_layout(
        height=320, margin=dict(l=8,r=8,t=8,b=8),
        plot_bgcolor="#0d1117", paper_bgcolor="#0d1117",
        xaxis=dict(showgrid=False, zeroline=False, tickfont=dict(size=9,color="#484f58"),
                   showline=True, linecolor="#21262d", tickcolor="#21262d"),
        yaxis=dict(gridcolor="#161b22", zeroline=False, tickfont=dict(size=9,color="#484f58"),
                   title=dict(text=y_label,font=dict(size=9,color="#484f58")), showline=False),
        showlegend=False, hovermode="x unified",
        hoverlabel=dict(bgcolor="#161b22", bordercolor="#30363d", font=dict(color="#e6edf3",size=11)),
    )
    return fig

# ── Scoreboard ─────────────────────────────────────────────────────────────────
def build_scoreboard_html(df, selected_sid):
    html = ['<table class="stbl"><thead><tr>',
            '<th>Series</th><th style="text-align:right">Latest</th>',
            '<th style="text-align:right">Chg</th><th style="text-align:right">Chg%</th>',
            '<th>As Of</th></tr></thead><tbody>']
    for cat, sids in CATEGORIES.items():
        html.append(f'<tr class="cat-row"><td colspan="5">{cat}</td></tr>')
        for sid in sids:
            sdf = df[df["series_id"]==sid].sort_values("date")
            if sdf.empty: continue
            l = sdf.iloc[-1]; p = sdf.iloc[-2] if len(sdf)>1 else l
            d = l["value"] - p["value"]
            dpct = (d/p["value"]*100) if p["value"]!=0 else 0
            up = d >= 0
            good = (up and sid not in INVERSE) or (not up and sid in INVERSE)
            cls = "vpos" if good else "vneg"
            arr = "▲" if up else "▼"
            sel_style = "background:#1c2128;" if sid==selected_sid else ""
            html.append(
                f'<tr style="{sel_style}">'
                f'<td>{SERIES_LABELS.get(sid,sid)}</td>'
                f'<td style="text-align:right;font-weight:600">{fmt_value(sid,l["value"])}</td>'
                f'<td style="text-align:right" class="{cls}">{arr} {abs(d):.2f}</td>'
                f'<td style="text-align:right" class="{cls}">{abs(dpct):.2f}%</td>'
                f'<td style="color:#484f58">{l["date"].strftime("%b %d")}</td></tr>'
            )
    html.append('</tbody></table>')
    return "".join(html)

# ── Overview tab ───────────────────────────────────────────────────────────────
def overview_tab(df):
    render_analysis(df)

    all_sids = [s for sids in CATEGORIES.values() for s in sids]
    col_board, col_chart = st.columns([1, 1.6], gap="large")

    with col_board:
        st.markdown('<div class="sec-hdr">All Series</div>', unsafe_allow_html=True)
        selected = st.selectbox("Select", all_sids,
                                format_func=lambda s: SERIES_LABELS.get(s,s),
                                label_visibility="collapsed", key="ov_sel")
        st.markdown(build_scoreboard_html(df, selected), unsafe_allow_html=True)

    with col_chart:
        sdf = get_sdf(df, selected)
        l = sdf.iloc[-1]; p = sdf.iloc[-2] if len(sdf)>1 else l
        d = l["value"] - p["value"]
        good = (d>=0 and selected not in INVERSE) or (d<0 and selected in INVERSE)
        st.markdown(f'<div class="sec-hdr">{SERIES_LABELS.get(selected,selected)}</div>', unsafe_allow_html=True)
        m1, m2, m3 = st.columns(3)
        m1.markdown(f'<div class="mc"><div class="mc-label">Latest</div>'
                    f'<div class="mc-value">{fmt_value(selected,l["value"])}</div>'
                    f'<div class="mc-date">{l["date"].strftime("%b %d, %Y")}</div></div>', unsafe_allow_html=True)
        dcls = "dpos" if good else "dneg"
        arr = "▲" if d>=0 else "▼"
        m2.markdown(f'<div class="mc"><div class="mc-label">Change</div>'
                    f'<div class="mc-value" style="font-size:1.1rem"><span class="{dcls}">'
                    f'{arr} {fmt_value(selected,abs(d))}</span></div>'
                    f'<div class="mc-date">vs prior period</div></div>', unsafe_allow_html=True)
        m3.markdown(f'<div class="mc"><div class="mc-label">Series ID</div>'
                    f'<div class="mc-value" style="font-size:0.95rem;color:#7d8590">{selected}</div>'
                    f'<div class="mc-date">{len(sdf):,} observations</div></div>', unsafe_allow_html=True)

        rc1, rc2 = st.columns([2,1])
        with rc1: yb = st.select_slider("Range", [1,2,3,5,10,20,"All"], value=5, key="ov_range")
        with rc2: show_yoy = st.toggle("YoY %", value=False, key="ov_yoy")
        st.plotly_chart(build_chart(df, selected, yb, show_yoy),
                        use_container_width=True, config={"displayModeBar":False})

# ── Overlay tab ────────────────────────────────────────────────────────────────
def overlay_tab(df):
    all_sids = [s for sids in CATEGORIES.values() for s in sids]
    st.markdown('<div class="sec-hdr">Compare Two Series</div>', unsafe_allow_html=True)
    c1,c2,c3 = st.columns([2,2,1])
    with c1: s1 = st.selectbox("Series 1", all_sids, format_func=lambda s:SERIES_LABELS.get(s,s), index=1, key="ov_s1")
    with c2: s2 = st.selectbox("Series 2", all_sids, format_func=lambda s:SERIES_LABELS.get(s,s), index=6, key="ov_s2")
    with c3: yb = st.selectbox("Range", [1,3,5,10,20,"All"], index=2, key="ov_yr")

    sdf1 = get_sdf(df,s1,yb); sdf2 = get_sdf(df,s2,yb)
    recessions = get_recessions(df)

    m1, m2 = st.columns(2)
    for col, sdf, sid in [(m1,sdf1,s1),(m2,sdf2,s2)]:
        l=sdf.iloc[-1]; p=sdf.iloc[-2] if len(sdf)>1 else l; d=l["value"]-p["value"]
        good=(d>=0 and sid not in INVERSE) or (d<0 and sid in INVERSE)
        cls="dpos" if good else "dneg"; arr="▲" if d>=0 else "▼"
        col.markdown(f'<div class="mc"><div class="mc-label">{SERIES_LABELS.get(sid,sid)}</div>'
                     f'<div class="mc-value">{fmt_value(sid,l["value"])}</div>'
                     f'<div class="{cls}">{arr} {fmt_value(sid,abs(d))}</div>'
                     f'<div class="mc-date">{l["date"].strftime("%b %d, %Y")}</div></div>', unsafe_allow_html=True)

    fig = make_subplots(specs=[[{"secondary_y":True}]])
    add_recession_shading(fig, recessions)
    fig.add_trace(go.Scatter(x=sdf1["date"],y=sdf1["value"],mode="lines",
                             line=dict(width=1.8,color="#58a6ff"),name=SERIES_LABELS.get(s1,s1),
                             hovertemplate="%{x|%b %d}  %{y:.2f}<extra></extra>"), secondary_y=False)
    fig.add_trace(go.Scatter(x=sdf2["date"],y=sdf2["value"],mode="lines",
                             line=dict(width=1.8,color="#f85149"),name=SERIES_LABELS.get(s2,s2),
                             hovertemplate="%{x|%b %d}  %{y:.2f}<extra></extra>"), secondary_y=True)
    fig.update_yaxes(title_text=SERIES_LABELS.get(s1,s1), title_font=dict(color="#58a6ff",size=9),
                     tickfont=dict(color="#58a6ff",size=9), gridcolor="#161b22", secondary_y=False)
    fig.update_yaxes(title_text=SERIES_LABELS.get(s2,s2), title_font=dict(color="#f85149",size=9),
                     tickfont=dict(color="#f85149",size=9), showgrid=False, secondary_y=True)
    fig.update_layout(height=400, margin=dict(l=8,r=8,t=8,b=8),
                      plot_bgcolor="#0d1117", paper_bgcolor="#0d1117",
                      xaxis=dict(showgrid=False,tickfont=dict(size=9,color="#484f58"),
                                 showline=True,linecolor="#21262d"),
                      legend=dict(orientation="h",y=1.06,x=0,font=dict(size=11,color="#8b949e"),
                                  bgcolor="rgba(0,0,0,0)"),
                      hovermode="x unified",
                      hoverlabel=dict(bgcolor="#161b22",bordercolor="#30363d",font=dict(color="#e6edf3",size=11)))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})

# ── News tab ───────────────────────────────────────────────────────────────────
def news_tab():
    st.markdown('<div class="sec-hdr">Economic Calendar & Headlines</div>', unsafe_allow_html=True)
    if st.button("🔄 Refresh news"):
        st.cache_data.clear(); st.rerun()
    with st.spinner("Loading..."):
        data = load_news()

    col_cal, col_news = st.columns([1,1.2], gap="large")
    with col_cal:
        st.markdown('<div class="sec-hdr">Upcoming Releases — 14 days</div>', unsafe_allow_html=True)
        today_str = dt.today().isoformat()
        by_date = {}
        for item in data.get("calendar", []):
            by_date.setdefault(item["date"],[]).append(item)
        for rdate, items in sorted(by_date.items()):
            tier1 = [i["release_name"] for i in items if i.get("tier1")]
            others= [i["release_name"] for i in items if not i.get("tier1")]
            label = "**Today**" if rdate==today_str else rdate
            with st.expander(f"{label} — {len(items)} releases{'  🔴' if tier1 else ''}", expanded=(rdate==today_str)):
                for n in tier1:  st.markdown(f"🔴 **{n}**")
                for n in others: st.markdown(f"· {n}")

    with col_news:
        st.markdown('<div class="sec-hdr">Federal Reserve</div>', unsafe_allow_html=True)
        for item in data.get("fed",[])[:8]:
            t,l = item.get("title",""), item.get("link","")
            if t: st.markdown(f"· [{t}]({l})" if l else f"· {t}")
        st.markdown('<div class="sec-hdr" style="margin-top:1rem">BEA Releases</div>', unsafe_allow_html=True)
        for item in data.get("bea",[])[:8]:
            t,l = item.get("title",""), item.get("link","")
            if t: st.markdown(f"· [{t}]({l})" if l else f"· {t}")

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    if not DATA_PATH.exists():
        with st.spinner("Pulling data from FRED — first load ~30s..."):
            fred_pull.main()
        st.cache_data.clear()

    df = load_data()
    last = df["date"].max().date()
    st.markdown(
        f'<h1>Macro Dashboard <span style="font-size:0.72rem;font-weight:400;color:#484f58;'
        f'margin-left:0.5rem">Data through {last} · FRED</span></h1>',
        unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["OVERVIEW","OVERLAY","NEWS & CALENDAR"])
    with tab1: overview_tab(df)
    with tab2: overlay_tab(df)
    with tab3: news_tab()

if __name__ == "__main__":
    main()

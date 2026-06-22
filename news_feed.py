"""
news_feed.py — Economic calendar and news headlines.

Sources:
  1. FRED releases/dates API  — upcoming data releases (next 14 days)
  2. Federal Reserve RSS       — Fed press releases
  3. BEA RSS                   — BEA economic data releases
"""

import os
import time
import requests
import feedparser
from datetime import date, timedelta
from pathlib import Path


def get_api_key():
    key = os.environ.get("FRED_API_KEY")
    if not key:
        try:
            import streamlit as st
            key = st.secrets.get("FRED_API_KEY")
        except Exception:
            pass
    return key


# High-priority release names to highlight in the calendar
TIER1_RELEASES = {
    "Employment Situation",
    "Consumer Price Index",
    "Producer Price Index",
    "Gross Domestic Product",
    "Personal Income and Outlays",
    "Retail Sales",
    "Industrial Production and Capacity Utilization",
    "Housing Starts",
    "FOMC Press Release",
    "Consumer Sentiment",
    "Unemployment Insurance Weekly Claims Report",
    "U.S. International Trade in Goods and Services",
}


def fetch_calendar(days_ahead: int = 14) -> list[dict]:
    """Fetch upcoming FRED data release dates."""
    api_key = get_api_key()
    if not api_key:
        return []
    today = date.today()
    end = today + timedelta(days=days_ahead)
    try:
        resp = requests.get(
            "https://api.stlouisfed.org/fred/releases/dates",
            params={
                "api_key": api_key,
                "file_type": "json",
                "realtime_start": today.isoformat(),
                "realtime_end": end.isoformat(),
                "include_release_dates_with_no_data": "false",
                "limit": 200,
            },
            timeout=15,
        )
        resp.raise_for_status()
        items = resp.json().get("release_dates", [])
        for item in items:
            item["tier1"] = item.get("release_name", "") in TIER1_RELEASES
        return sorted(items, key=lambda x: x["date"])
    except Exception:
        return []


def fetch_rss(url: str, max_items: int = 10) -> list[dict]:
    """Fetch and parse an RSS feed, return list of {title, link, published}."""
    try:
        feed = feedparser.parse(url)
        results = []
        for entry in feed.entries[:max_items]:
            results.append({
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "published": entry.get("published", ""),
                "summary": entry.get("summary", "")[:200] if entry.get("summary") else "",
            })
        return results
    except Exception:
        return []


def fetch_all_news() -> dict:
    """Fetch all news sources. Returns dict with 'calendar', 'fed', 'bea'."""
    return {
        "calendar": fetch_calendar(days_ahead=14),
        "fed":      fetch_rss("https://www.federalreserve.gov/feeds/press_all.xml"),
        "bea":      fetch_rss("https://apps.bea.gov/rss/rss.xml"),
    }

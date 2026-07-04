"""Market-wide data via Financial Modeling Prep (FMP).

Docs: https://site.financialmodelingprep.com/developer/docs

Uses the /stable/ API — FMP retired the old /api/v3/ paths for non-legacy
accounts (cutoff Aug 31, 2025).
"""
from datetime import date, timedelta

import requests

from src import config

BASE_URL = "https://financialmodelingprep.com/stable"

# Movers below these thresholds are micro-cap noise or data errors, not
# tradeable signal.
MIN_PRICE = 1.0
MAX_ABS_CHANGE_PCT = 300.0
MIN_MARKET_CAP = 250_000_000

MACRO_SYMBOLS = {
    "^GSPC": "S&P 500",
    "^DJI": "Dow Jones Industrial Average",
    "^IXIC": "Nasdaq Composite",
    "^RUT": "Russell 2000",
    "^VIX": "CBOE Volatility Index",
    "^TNX": "10-Year Treasury Yield",
}


def _get(path: str, **params) -> list:
    params["apikey"] = config.require(config.FMP_API_KEY, "FMP_API_KEY")
    resp = requests.get(f"{BASE_URL}/{path}", params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict) and "Error Message" in data:
        raise RuntimeError(f"FMP error on {path}: {data['Error Message']}")
    return data


def _get_soft(path: str, **params) -> list:
    """Like _get but returns [] instead of raising — for endpoints/symbols
    that may be premium-gated or intermittently unavailable."""
    try:
        return _get(path, **params)
    except (requests.RequestException, RuntimeError, ValueError):
        return []


def get_quote(symbol: str) -> dict:
    data = _get_soft("quote", symbol=symbol)
    return data[0] if data else {}


def get_profile(symbol: str) -> dict:
    data = _get_soft("profile", symbol=symbol)
    return data[0] if data else {}


def _filter_movers(rows: list[dict], enrich_limit: int = 12) -> list[dict]:
    """Drops data errors and untradeable micro-caps.

    First pass: cheap heuristics (price floor, change-% sanity cap, rights/
    warrants/units by name). Second pass: fetch profiles for the survivors
    and require a real market cap.
    """
    cheap = []
    for r in rows:
        price = r.get("price") or 0
        change = abs(r.get("changesPercentage") or 0)
        name = (r.get("name") or "").lower()
        if price < MIN_PRICE or change > MAX_ABS_CHANGE_PCT:
            continue
        if any(w in name for w in ("warrant", " right", " rights", " unit")):
            continue
        cheap.append(r)

    kept = []
    for r in cheap[:enrich_limit]:
        profile = get_profile(r.get("symbol", ""))
        mcap = profile.get("marketCap")
        is_fund = profile.get("isEtf") or profile.get("isFund")
        if is_fund or (mcap and mcap >= MIN_MARKET_CAP):
            r = dict(r)
            r["marketCap"] = mcap
            r["sector"] = profile.get("sector")
            kept.append(r)
    return kept


def get_gainers(limit: int = 25) -> list[dict]:
    return _filter_movers(_get("biggest-gainers")[:limit])


def get_losers(limit: int = 25) -> list[dict]:
    return _filter_movers(_get("biggest-losers")[:limit])


def get_most_active(limit: int = 25) -> list[dict]:
    return _filter_movers(_get("most-actives")[:limit])


def get_sector_performance(max_days_back: int = 5) -> list[dict]:
    """Sector performance needs an explicit date and is empty on non-trading
    days (weekends/holidays), so walk backward to the last trading day."""
    for days_back in range(max_days_back):
        day = (date.today() - timedelta(days=days_back)).isoformat()
        data = _get_soft("sector-performance-snapshot", date=day)
        if data:
            return data
    return []


def get_macro_snapshot() -> list[dict]:
    """Hard index/vol/yield levels so the model never has to guess the tape."""
    rows = []
    for symbol, label in MACRO_SYMBOLS.items():
        q = get_quote(symbol)
        if q:
            rows.append(
                {
                    "symbol": symbol,
                    "name": label,
                    "price": q.get("price"),
                    "changePercentage": q.get("changePercentage"),
                    "yearHigh": q.get("yearHigh"),
                    "yearLow": q.get("yearLow"),
                }
            )
    return rows


def get_earnings_calendar(days_ahead: int = 7, min_revenue: float = 1e9) -> list[dict]:
    """Upcoming earnings for real companies (revenue >= min_revenue) so the
    analysis can cite concrete, dated catalysts."""
    start = date.today().isoformat()
    end = (date.today() + timedelta(days=days_ahead)).isoformat()
    rows = _get_soft("earnings-calendar", **{"from": start, "to": end})
    major = [
        {
            "symbol": r.get("symbol"),
            "date": r.get("date"),
            "epsEstimated": r.get("epsEstimated"),
            "revenueEstimated": r.get("revenueEstimated"),
        }
        for r in rows
        if (r.get("revenueEstimated") or 0) >= min_revenue
    ]
    major.sort(key=lambda r: (r["date"], -(r["revenueEstimated"] or 0)))
    return major[:40]


def get_market_snapshot() -> dict:
    """One-shot pull of the day's market picture."""
    return {
        "macro": get_macro_snapshot(),
        "gainers": get_gainers(),
        "losers": get_losers(),
        "most_active": get_most_active(),
        "sector_performance": get_sector_performance(),
        "earnings_calendar": get_earnings_calendar(),
    }

"""Exports each run's full output as structured data for the local dashboard.

Reads profile/portfolio.md (YAML frontmatter) for actual holdings, values
them with live FMP quotes, maintains a net-worth history, and writes
dashboard/data.js — a single self-contained payload the static dashboard
page loads with no server needed.
"""
import json
from datetime import datetime
from pathlib import Path

import yaml

from src import config
from src.fetchers.market_data import get_quote

DASHBOARD_DIR = config.ROOT_DIR / "dashboard"
DATA_JS_PATH = DASHBOARD_DIR / "data.js"
PORTFOLIO_PATH = config.ROOT_DIR / "profile" / "portfolio.md"
HISTORY_PATH = config.REPORTS_DIR / "networth_history.json"

BUCKET_LABELS = {
    "core_high_conviction": "Core / High Conviction",
    "growth_momentum": "Growth & Momentum",
    "defensive_income": "Defensive & Income",
    "speculative": "Speculative",
    "diversified_etf": "Diversified / ETF",
}


def _load_portfolio_frontmatter() -> dict:
    if not PORTFOLIO_PATH.exists():
        return {}
    text = PORTFOLIO_PATH.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    end = text.find("---", 3)
    if end == -1:
        return {}
    try:
        return yaml.safe_load(text[3:end]) or {}
    except yaml.YAMLError:
        return {}


def _compute_portfolio_state() -> dict:
    pf = _load_portfolio_frontmatter()
    accounts = pf.get("accounts") or []
    holdings_raw = pf.get("holdings") or []
    other_assets = pf.get("other_assets") or []

    holdings = []
    holdings_value = 0.0
    bucket_values: dict[str, float] = {}
    for h in holdings_raw:
        ticker = (h.get("ticker") or "").upper()
        shares = float(h.get("shares") or 0)
        cost = h.get("cost_basis_per_share")
        price = get_quote(ticker).get("price") if ticker else None
        value = round(shares * price, 2) if price else None
        gain_pct = None
        if price and cost:
            gain_pct = round((price - float(cost)) / float(cost) * 100, 2)
        if value:
            holdings_value += value
            bucket = h.get("bucket") or "unbucketed"
            bucket_values[bucket] = bucket_values.get(bucket, 0.0) + value
        holdings.append(
            {
                "ticker": ticker,
                "shares": shares,
                "cost_basis_per_share": cost,
                "account": h.get("account"),
                "bucket": h.get("bucket"),
                "price_now": price,
                "value_now": value,
                "gain_pct": gain_pct,
            }
        )

    cash_total = sum(float(a.get("cash") or 0) for a in accounts)
    other_total = sum(float(a.get("estimated_value") or 0) for a in other_assets)
    net_worth = round(cash_total + holdings_value + other_total, 2)

    allocation = [
        {"label": BUCKET_LABELS.get(bucket, bucket), "value": round(value, 2)}
        for bucket, value in sorted(bucket_values.items(), key=lambda kv: -kv[1])
    ]
    if cash_total:
        allocation.append({"label": "Cash", "value": round(cash_total, 2)})
    if other_total:
        allocation.append({"label": "Other Assets", "value": round(other_total, 2)})

    return {
        "net_worth": net_worth,
        "cash_total": round(cash_total, 2),
        "holdings_value": round(holdings_value, 2),
        "accounts": accounts,
        "holdings": holdings,
        "other_assets": other_assets,
        "allocation": allocation,
        "profile_last_updated": str(pf.get("last_updated", "")),
    }


def _update_history(net_worth: float, run_date: str) -> list[dict]:
    history = []
    if HISTORY_PATH.exists():
        try:
            history = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            history = []
    history = [h for h in history if h.get("date") != run_date]
    history.append({"date": run_date, "net_worth": net_worth})
    history.sort(key=lambda h: h["date"])
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(history, indent=2), encoding="utf-8")
    return history


def _condense_articles(articles: list[dict], limit: int = 20) -> list[dict]:
    out = []
    for a in articles[:limit]:
        out.append(
            {
                "title": a.get("title"),
                "source": (a.get("source") or {}).get("name"),
                "description": a.get("description"),
                "url": a.get("url"),
                "publishedAt": a.get("publishedAt"),
            }
        )
    return out


def refresh_prices_only() -> dict:
    """Re-prices current holdings and patches just the portfolio section of
    data.js, without touching news/suggested/overall or calling any LLM.
    Used by the dashboard's manual "Refresh" button. Returns the fresh
    portfolio dict (with history) for the caller to send back to the browser.
    """
    from datetime import date

    portfolio = _compute_portfolio_state()
    history = _update_history(portfolio["net_worth"], date.today().isoformat())
    portfolio = {**portfolio, "history": history}

    if DATA_JS_PATH.exists():
        text = DATA_JS_PATH.read_text(encoding="utf-8")
        prefix = "window.DASHBOARD_DATA = "
        if text.startswith(prefix):
            try:
                data = json.loads(text[len(prefix):].rstrip().rstrip(";"))
                data["portfolio"] = portfolio
                DATA_JS_PATH.write_text(
                    prefix + json.dumps(data, indent=2, default=str) + ";\n",
                    encoding="utf-8",
                )
            except json.JSONDecodeError:
                pass  # leave data.js untouched if it's ever malformed

    return portfolio


def update_dashboard(
    market_snapshot: dict,
    news_bundle: dict,
    narrative: str,
    picks: list[dict],
    fundamentals: list[dict],
    scorecard: list[dict],
    run_date: str,
) -> Path:
    portfolio = _compute_portfolio_state()
    history = _update_history(portfolio["net_worth"], run_date)

    data = {
        "run_date": run_date,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "portfolio": {**portfolio, "history": history},
        "news": {
            "top_headlines": _condense_articles(news_bundle.get("top_headlines", [])),
            "market_news": _condense_articles(news_bundle.get("market_news", [])),
            "sector_news": _condense_articles(news_bundle.get("sector_news", [])),
        },
        "suggested": {
            "picks": picks,
            "fundamentals": {f.get("symbol"): f for f in fundamentals if f.get("symbol")},
            "scorecard": scorecard,
        },
        "overall": {
            "macro": market_snapshot.get("macro", []),
            "gainers": market_snapshot.get("gainers", []),
            "losers": market_snapshot.get("losers", []),
            "most_active": market_snapshot.get("most_active", []),
            "sector_performance": market_snapshot.get("sector_performance", []),
            "earnings_calendar": market_snapshot.get("earnings_calendar", []),
        },
        "report_markdown": narrative,
    }

    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
    DATA_JS_PATH.write_text(
        "window.DASHBOARD_DATA = " + json.dumps(data, indent=2, default=str) + ";\n",
        encoding="utf-8",
    )
    return DATA_JS_PATH

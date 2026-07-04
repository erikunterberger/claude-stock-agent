"""Picks ledger: records every recommendation and scores it over time.

Stored at reports/picks_ledger.json as a flat list of pick records:
    {date, ticker, category, horizon, thesis, price_at_pick}
"""
import json

from src import config
from src.fetchers.market_data import get_quote

LEDGER_PATH = config.REPORTS_DIR / "picks_ledger.json"

MAX_SCORECARD_TICKERS = 20


def load_ledger() -> list[dict]:
    if not LEDGER_PATH.exists():
        return []
    try:
        return json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def record_picks(picks: list[dict], run_date: str) -> None:
    """Appends today's picks (with entry price) to the ledger. A ticker
    already recorded on a previous day is not re-recorded — the original
    entry price stays the benchmark."""
    ledger = load_ledger()
    existing = {p["ticker"] for p in ledger}
    for pick in picks:
        ticker = (pick.get("ticker") or "").strip().upper()
        if not ticker or ticker in existing:
            continue
        quote = get_quote(ticker)
        ledger.append(
            {
                "date": run_date,
                "ticker": ticker,
                "category": pick.get("category"),
                "horizon": pick.get("horizon"),
                "thesis": pick.get("thesis"),
                "price_at_pick": quote.get("price"),
            }
        )
        existing.add(ticker)
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    LEDGER_PATH.write_text(json.dumps(ledger, indent=2), encoding="utf-8")


def get_scorecard(run_date: str) -> list[dict]:
    """Current performance of past picks (excluding ones made today),
    most recent first, capped to bound API usage."""
    ledger = [p for p in load_ledger() if p.get("date") != run_date]
    ledger.sort(key=lambda p: p.get("date", ""), reverse=True)

    rows = []
    for pick in ledger[:MAX_SCORECARD_TICKERS]:
        entry = pick.get("price_at_pick")
        current = get_quote(pick["ticker"]).get("price")
        change_pct = None
        if entry and current:
            change_pct = round((current - entry) / entry * 100, 2)
        rows.append(
            {
                "ticker": pick["ticker"],
                "picked_on": pick.get("date"),
                "category": pick.get("category"),
                "horizon": pick.get("horizon"),
                "thesis": pick.get("thesis"),
                "price_at_pick": entry,
                "price_now": current,
                "change_pct_since_pick": change_pct,
            }
        )
    return rows

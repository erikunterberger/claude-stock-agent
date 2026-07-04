"""Per-ticker fundamentals from FMP for the second-pass analysis.

Keeps only decision-relevant fields so the model payload stays small.
"""
from src.fetchers.market_data import _get_soft


def get_fundamentals(symbol: str) -> dict:
    profile_rows = _get_soft("profile", symbol=symbol)
    ratios_rows = _get_soft("ratios-ttm", symbol=symbol)
    target_rows = _get_soft("price-target-consensus", symbol=symbol)

    profile = profile_rows[0] if profile_rows else {}
    ratios = ratios_rows[0] if ratios_rows else {}
    target = target_rows[0] if target_rows else {}

    out = {
        "symbol": symbol,
        "price": profile.get("price"),
        "marketCap": profile.get("marketCap"),
        "beta": profile.get("beta"),
        "sector": profile.get("sector"),
        "industry": profile.get("industry"),
        "lastDividend": profile.get("lastDividend"),
        "range52w": profile.get("range"),
        "isEtf": profile.get("isEtf"),
        "peTTM": ratios.get("priceToEarningsRatioTTM"),
        "priceToSalesTTM": ratios.get("priceToSalesRatioTTM"),
        "grossMarginTTM": ratios.get("grossProfitMarginTTM"),
        "operatingMarginTTM": ratios.get("operatingProfitMarginTTM"),
        "netMarginTTM": ratios.get("netProfitMarginTTM"),
        "debtToEquityTTM": ratios.get("debtToEquityRatioTTM"),
        "dividendYieldTTM": ratios.get("dividendYieldTTM"),
        "analystTargetConsensus": target.get("targetConsensus"),
        "analystTargetHigh": target.get("targetHigh"),
        "analystTargetLow": target.get("targetLow"),
    }
    # Drop empty fields to keep the payload tight.
    return {k: v for k, v in out.items() if v not in (None, "", 0) or k == "symbol"}


def get_fundamentals_bulk(symbols: list[str], limit: int = 15) -> list[dict]:
    seen = set()
    out = []
    for s in symbols:
        s = (s or "").strip().upper()
        if not s or s in seen or s.startswith("^"):
            continue
        seen.add(s)
        out.append(get_fundamentals(s))
        if len(out) >= limit:
            break
    return out

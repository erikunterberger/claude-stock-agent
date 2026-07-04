"""Daily financial/market news via NewsAPI.

Docs: https://newsapi.org/docs
"""
import requests

from src import config

BASE_URL = "https://newsapi.org/v2"

DEFAULT_QUERY = (
    '(stock market OR "federal reserve" OR earnings OR inflation OR '
    "S&P 500 OR Nasdaq OR interest rates)"
)

# A second, broader query so the report isn't limited to whatever the top
# headlines happen to cover — pulls in sector-specific stories the model can
# use to widen the ticker watchlist beyond today's narrow movers list.
SECTOR_QUERY = (
    "(technology stocks OR semiconductor OR artificial intelligence OR "
    "biotech OR pharmaceutical OR energy sector OR renewable energy OR "
    "banking sector OR financial services OR cryptocurrency OR "
    "consumer staples OR industrials)"
)


def get_top_business_headlines(country: str = "us", page_size: int = 30) -> list[dict]:
    resp = requests.get(
        f"{BASE_URL}/top-headlines",
        params={
            "category": "business",
            "country": country,
            "pageSize": page_size,
            "apiKey": config.require(config.NEWSAPI_KEY, "NEWSAPI_KEY"),
        },
        timeout=20,
    )
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("status") != "ok":
        raise RuntimeError(f"NewsAPI error: {payload}")
    return payload.get("articles", [])


def search_market_news(query: str = DEFAULT_QUERY, page_size: int = 40) -> list[dict]:
    resp = requests.get(
        f"{BASE_URL}/everything",
        params={
            "q": query,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": page_size,
            "apiKey": config.require(config.NEWSAPI_KEY, "NEWSAPI_KEY"),
        },
        timeout=20,
    )
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("status") != "ok":
        raise RuntimeError(f"NewsAPI error: {payload}")
    return payload.get("articles", [])


def get_daily_news_bundle() -> dict:
    return {
        "top_headlines": get_top_business_headlines(),
        "market_news": search_market_news(),
        "sector_news": search_market_news(query=SECTOR_QUERY),
    }

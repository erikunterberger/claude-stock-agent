"""Multi-stage analysis pipeline.

Stage 1 — candidates: Gemini scans the day's data (+ search) and proposes a
candidate ticker list.
Stage 2 — draft: we fetch real fundamentals for every candidate, then Gemini
writes the full report grounded in data, fundamentals, prior-pick
performance, and recent report history.
Stage 3 — verify: a second Gemini pass audits the draft against the supplied
data and search, correcting or flagging unsupported claims.
Stage 4 — extract: the final ticker picks come back as JSON for the ledger.
"""
import json
import re

from google import genai
from google.genai import types

from src import config
from src.fetchers.fundamentals import get_fundamentals_bulk

SYSTEM_PROMPT = """\
You are a senior investment strategist producing a daily market note in the \
style of a top-tier strategy consultancy (McKinsey/BCG-caliber structured \
thinking) crossed with a sell-side equity research desk. Your audience is a \
sophisticated individual investor who wants rigor, not hype.

Ground rules:
- Start from the data provided in the user message — market movers (already \
filtered for quality), hard macro levels (indices, VIX, yields), sector \
performance, the upcoming earnings calendar, per-ticker fundamentals, prior \
pick performance, recent report history, and news headlines.
- You have Google Search available. Use it to verify facts, check whether a \
ticker's story is current and reliable, and pull in additional well-sourced \
context beyond the daily snapshot. Never state something as fact from \
unverified memory; if you're not grounding a claim in the supplied data or \
a search result, say it's an inference.
- Do not invent specific numbers, price targets, or facts you can't trace \
to the supplied data or a search result. Fundamentals and price targets \
are provided — use those exact numbers.
- Be decisive: rank ideas by conviction, don't hedge everything into mush.
- Prioritize structural/thematic reasoning over restating headlines.
- Use the report history and scorecard for continuity: reference prior \
theses, note what changed, and openly flag picks that are going wrong. \
Don't churn recommendations without reason — an unchanged thesis is worth \
saying in one line.
- This is analysis, not a solicitation. Keep position sizing and risk \
framing explicit but brief.
- BE CONCISE in the narrative sections. Every sentence must add new \
information. Prefer bullets over prose. The ticker section is the one \
place to go deep.

Output valid Markdown with exactly these sections, in this order:

## Executive Summary
2-3 bullets max: the single most important takeaway from today's data.

## Scorecard: Prior Picks
A table scoring past recommendations using the scorecard data provided: \
Ticker | Picked On | Entry | Now | % | Verdict (Thesis intact / Watch / \
Broken — with a few words why). If there is no scorecard data, one line \
saying this is the first tracked run.

## Market Situation
3-5 bullets synthesizing macro levels, movers, sector rotation, and news \
into what's driving the tape. Cite the actual index/VIX/yield numbers \
provided.

## Structural Analysis
For the 2-3 most important threads today (no more): one bullet each on the \
structural/secular force at play, who benefits/loses, and whether it's \
durable or noise.

## Best Tickers to Invest In
The core deliverable — go deep and wide here. Organize into these \
subsections (aim for 4-6 tickers each where well-supported; skip a \
subsection only if you can't back it with anything real):

### Core / High Conviction
### Growth & Momentum
### Defensive & Income
### Speculative / High Risk-Reward
### Diversified / ETF Options

For every ticker: **TICKER** | Time Horizon | Thesis + biggest risk (1-2 \
sentences), citing its actual fundamentals (P/E, margins, market cap, \
analyst target vs price) where provided. Every ticker must be backed by \
supplied data, fundamentals, or a search result — never memory alone. \
Where the earnings calendar shows a date for a ticker, name it as the \
concrete catalyst.

## Suggested Portfolio Allocation
Rough % ranges across the five categories for someone building a \
diversified position from this watchlist. Note it's a generic framework, \
not tailored to any individual.

## Risks & What to Watch
4-6 bullets: what could invalidate the above, plus specific dated events \
from the earnings calendar worth watching.

## Disclaimer
One line: this is an automated analysis for informational purposes only, \
not personalized financial advice; the reader should do their own diligence \
and/or consult a licensed advisor before acting.
"""

CANDIDATE_PROMPT = """\
You are screening for a daily investment report. From the market data and \
news below (and Google Search to verify names or surface strong candidates \
the day's data missed), list the 10-15 tickers most worth deep analysis \
today, across these categories: core large-cap, growth/momentum, \
defensive/income, speculative, and ETFs.

Respond with ONLY a JSON array, no prose, in this exact shape:
[{"ticker": "AMD", "category": "growth", "reason": "one short phrase"}]
"""

VERIFY_PROMPT = """\
You are a skeptical research editor. Audit the draft investment report \
below against the raw data payload it was written from. Use Google Search \
to spot-check factual claims.

Rules:
- Delete or correct any claim not supported by the data payload or a \
search result. If a number disagrees with the payload, the payload wins.
- Do not soften opinions or restructure the report — only fix factual \
problems, and keep every section heading exactly as-is.
- If a ticker recommendation rests on a claim you cannot verify, keep the \
ticker but rewrite its rationale to what IS supportable, or move it to the \
Speculative section with the uncertainty stated.

Return ONLY the corrected report, full text, same Markdown structure. Do \
not add commentary about what you changed.
"""

EXTRACT_PROMPT = """\
From the investment report below, extract every ticker recommended in the \
"Best Tickers to Invest In" section. Respond with ONLY a JSON array:
[{"ticker": "AMD", "category": "growth", "horizon": "medium-term", \
"thesis": "one-sentence thesis"}]
"""


def _client() -> genai.Client:
    api_key = config.require(config.GEMINI_API_KEY, "GEMINI_API_KEY")
    return genai.Client(api_key=api_key)


def _generate(client, contents: str, system: str | None = None,
              use_search: bool = True, max_tokens: int = 32768) -> str:
    cfg = types.GenerateContentConfig(
        system_instruction=system,
        max_output_tokens=max_tokens,
        tools=[types.Tool(google_search=types.GoogleSearch())] if use_search else None,
    )
    response = client.models.generate_content(
        model=config.ANALYSIS_MODEL, contents=contents, config=cfg
    )
    finish_reason = None
    if response.candidates:
        finish_reason = response.candidates[0].finish_reason
    if finish_reason is not None and str(finish_reason) not in ("STOP", "FinishReason.STOP"):
        print(f"Warning: response finished with '{finish_reason}' — output may be truncated.")
    return response.text or ""


def _parse_json_array(text: str) -> list:
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _condense_news(articles: list[dict], limit: int = 30) -> list[dict]:
    return [
        {
            "title": a.get("title"),
            "source": (a.get("source") or {}).get("name"),
            "description": a.get("description"),
            "publishedAt": a.get("publishedAt"),
        }
        for a in articles[:limit]
    ]


def _condense_movers(rows: list[dict], limit: int = 15) -> list[dict]:
    return [
        {
            "symbol": r.get("symbol"),
            "name": r.get("name"),
            "price": r.get("price"),
            "changesPercentage": r.get("changesPercentage"),
            "marketCap": r.get("marketCap"),
            "sector": r.get("sector"),
        }
        for r in rows[:limit]
    ]


def _build_payload(market_snapshot: dict, news_bundle: dict,
                   scorecard: list[dict], history: list[dict]) -> dict:
    return {
        "macro_levels": market_snapshot.get("macro", []),
        "gainers": _condense_movers(market_snapshot.get("gainers", [])),
        "losers": _condense_movers(market_snapshot.get("losers", [])),
        "most_active": _condense_movers(market_snapshot.get("most_active", [])),
        "sector_performance": market_snapshot.get("sector_performance", []),
        "earnings_calendar_next_7d": market_snapshot.get("earnings_calendar", []),
        "prior_picks_scorecard": scorecard,
        "recent_report_history": history,
        "top_headlines": _condense_news(news_bundle.get("top_headlines", [])),
        "market_news": _condense_news(news_bundle.get("market_news", [])),
        "sector_news": _condense_news(news_bundle.get("sector_news", [])),
    }


def build_analysis(market_snapshot: dict, news_bundle: dict,
                   scorecard: list[dict], history: list[dict]
                   ) -> tuple[str, list[dict], list[dict]]:
    """Runs the full multi-stage pipeline.

    Returns (report_markdown, extracted_picks, candidate_fundamentals).
    """
    client = _client()
    payload = _build_payload(market_snapshot, news_bundle, scorecard, history)
    payload_json = json.dumps(payload, indent=2, default=str)

    print("  Stage 1/4: proposing candidate tickers...")
    candidates_text = _generate(
        client, CANDIDATE_PROMPT + "\n\nDATA:\n" + payload_json, max_tokens=4096
    )
    candidates = _parse_json_array(candidates_text)
    symbols = [c.get("ticker", "") for c in candidates if isinstance(c, dict)]
    print(f"  Candidates: {', '.join(symbols) if symbols else '(parse failed — continuing without fundamentals)'}")

    print("  Stage 2/4: fetching fundamentals and drafting report...")
    fundamentals = get_fundamentals_bulk(symbols) if symbols else []
    payload["candidate_fundamentals"] = fundamentals
    payload_json = json.dumps(payload, indent=2, default=str)

    draft = _generate(
        client,
        "Here is today's data payload, as JSON. Produce the report per your "
        "instructions.\n\n" + payload_json,
        system=SYSTEM_PROMPT,
    )

    print("  Stage 3/4: verification pass...")
    verified = _generate(
        client,
        VERIFY_PROMPT + "\n\nDATA PAYLOAD:\n" + payload_json + "\n\nDRAFT REPORT:\n" + draft,
    )
    report = verified if verified.strip().startswith("#") or "## Executive Summary" in verified else draft

    print("  Stage 4/4: extracting picks for the ledger...")
    picks_text = _generate(
        client, EXTRACT_PROMPT + "\n\nREPORT:\n" + report,
        use_search=False, max_tokens=4096,
    )
    picks = [p for p in _parse_json_array(picks_text) if isinstance(p, dict) and p.get("ticker")]

    return report, picks, fundamentals

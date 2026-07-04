# Stock Agent

A daily agent that pulls market movers + financial news, runs a structured
(McKinsey-style) analysis via Google Gemini (free tier), and produces a
Markdown + PDF report — optionally emailed to you. Run manually whenever you
want a report; nothing is scheduled automatically.

All three data/analysis providers below have genuine free tiers (no credit
card needed to get started). NewsAPI's free tier is officially scoped to
development/testing, not ongoing production use — see the note below.

**Not financial advice.** This is an automated research aid. Do your own
diligence before acting on anything it produces.

## 1. Install

```
cd stock-agent
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

## 2. Get API keys

Copy `.env.example` to `.env` and fill in:

| Key | What it's for | Get it here |
|---|---|---|
| `FMP_API_KEY` | Market movers, sector performance | https://site.financialmodelingprep.com/developer/docs — free tier: 250 requests/day, no card required, no expiration |
| `NEWSAPI_KEY` | Daily business/market headlines | https://newsapi.org/register — free "Developer" tier: 100 req/day, 24h-delayed articles. **Note:** NewsAPI's ToS scope this tier to development/testing only, not ongoing personal/production use — using it for a recurring personal script is a gray area they don't officially sanction. If that matters to you, swap in a provider whose free tier explicitly allows production use (e.g. GNews, Marketaux). |
| `GEMINI_API_KEY` | Powers the analysis narrative | https://aistudio.google.com/apikey — genuinely free, no card required: 1,500 requests/day, 1M tokens/minute on `gemini-2.5-flash`. Note: free-tier inputs/outputs may be used by Google to improve their models. |

Email (only needed if you use `--email`):

| Key | What it's for |
|---|---|
| `SMTP_HOST` / `SMTP_PORT` | Your mail provider's SMTP server (e.g. `smtp.gmail.com`, port 587) |
| `SMTP_USER` / `SMTP_PASS` | Login for that SMTP account (for Gmail, use an [App Password](https://myaccount.google.com/apppasswords), not your real password) |
| `EMAIL_FROM` / `EMAIL_TO` | Sender and recipient addresses |

## 3. Run

```
python -m src.main            # saves reports/<date>-report.md and .pdf
python -m src.main --email    # also emails the PDF
```

Reports land in `reports/`.

## How it works

1. `src/fetchers/market_data.py` — pulls movers (filtered for data errors and
   micro-cap junk via market-cap check), hard macro levels (S&P/Dow/Nasdaq/
   Russell/VIX/10Y), sector performance, and the next 7 days of major
   earnings from Financial Modeling Prep.
2. `src/fetchers/news_fetcher.py` — pulls business headlines + market +
   sector news from NewsAPI.
3. `src/analysis/analyzer.py` — four-stage Gemini pipeline (with Google
   Search grounding): propose candidate tickers → fetch real fundamentals
   (P/E, margins, market cap, analyst targets via
   `src/fetchers/fundamentals.py`) and draft the full report → verification
   pass that audits every claim against the data → extract final picks as
   JSON.
4. `src/analysis/ledger.py` — records every pick with its entry price in
   `reports/picks_ledger.json`; each subsequent run scores past picks and
   the report opens with a performance scorecard.
5. `src/report/obsidian.py` — saves each report to the Obsidian vault
   (`Financial Analysis/` folder) and feeds the most recent reports back
   into the next run for continuity.
6. `src/report/report_builder.py` — assembles narrative + raw-data appendix
   into Markdown, renders PDF.
7. `src/report/emailer.py` — optionally emails the PDF via SMTP.

## Extending

- **Automate it**: once you're happy with report quality, wire
  `python -m src.main --email` into Windows Task Scheduler to run every
  morning before market open.
- **Swap data providers**: the fetchers are isolated modules — swap in
  Finnhub, Polygon.io, Alpha Vantage, etc. without touching the analyzer or
  report builder.
- **Add a watchlist**: currently scans the open market (gainers/losers/most
  active). To track specific tickers instead/also, add a
  `get_quote(symbol)` loop in `market_data.py` and feed those into the
  analyzer payload.

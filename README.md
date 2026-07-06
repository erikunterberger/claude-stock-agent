# Stock Agent

A daily agent that pulls market movers + financial news, runs a structured
(McKinsey-style) analysis via Google Gemini (free tier), and produces a
Markdown + PDF report plus a local dashboard — optionally emailed to you.
Runs automatically every weekday morning via Windows Task Scheduler
(`run_daily.bat`), or manually anytime with `python -m src.main`.

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

Reports land in `reports/`. The dashboard's data (`dashboard/data.js`) is
regenerated on every run too — see below for how to view it.

## Dashboard

Open it two ways:

- **Just viewing**: double-click `dashboard/index.html` — works offline,
  shows whatever the last run generated.
- **Viewing + the Refresh Prices button**: run `start_dashboard.bat`
  (or `venv\Scripts\python.exe dashboard_server.py`) and open
  `http://localhost:8765`. The Refresh button re-prices your current
  holdings only (no LLM calls, ~1 API call per position) without waiting
  for the next full daily run. It only works through this server — a plain
  `file://` page has no server to call, so the button will show an error.

Your actual holdings live in `profile/portfolio.md` (gitignored, local
only) — the dashboard's portfolio page, allocation pie chart, and net
worth history are all computed from that file plus live quotes.

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
7. `src/report/dashboard.py` — prices your actual holdings (from
   `profile/portfolio.md`), updates net-worth history, and writes
   `dashboard/data.js` for the local site.
8. `src/report/emailer.py` — optionally emails the PDF via SMTP.
9. `dashboard_server.py` — optional local server (static files +
   `/api/refresh-prices`) for the dashboard's manual refresh button.

## Automation

`run_daily.bat` runs the full pipeline; a Windows Task Scheduler job
("Stock Agent Daily") fires it every weekday at 7:00 AM with
`StartWhenAvailable` and `WakeToRun` enabled, so it catches up if your PC
was asleep at trigger time (it can't wake from a full shutdown, only sleep).
Logs land in `reports/run_log.txt`.

## Extending

- **Swap data providers**: the fetchers are isolated modules — swap in
  Finnhub, Polygon.io, Alpha Vantage, etc. without touching the analyzer or
  report builder.
- **Add a watchlist**: currently scans the open market (gainers/losers/most
  active). To track specific tickers instead/also, add a
  `get_quote(symbol)` loop in `market_data.py` and feed those into the
  analyzer payload.

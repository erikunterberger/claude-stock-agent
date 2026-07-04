"""Entry point: fetch -> analyze (multi-stage) -> report -> save everywhere.

Usage:
    python -m src.main            # save report as .md + .pdf + Obsidian note
    python -m src.main --email    # also email the PDF
"""
import argparse
import sys
from datetime import date

from src import config
from src.analysis import analyzer, ledger
from src.fetchers import market_data, news_fetcher
from src.report import emailer, obsidian, report_builder


def run(send_email: bool) -> None:
    run_date = date.today().isoformat()

    print("Fetching market data (movers, macro, earnings calendar)...")
    market_snapshot = market_data.get_market_snapshot()

    print("Fetching news...")
    news_bundle = news_fetcher.get_daily_news_bundle()

    print("Scoring prior picks...")
    scorecard = ledger.get_scorecard(run_date)

    print("Loading recent report history from Obsidian...")
    history = obsidian.load_recent_reports(exclude_date=run_date)

    print("Running multi-stage analysis (4 Gemini calls, may take a few minutes)...")
    narrative, picks = analyzer.build_analysis(
        market_snapshot, news_bundle, scorecard, history
    )

    print("Building report...")
    markdown_text = report_builder.build_markdown(market_snapshot, news_bundle, narrative)
    md_path, pdf_path = report_builder.save_report(markdown_text)
    print(f"Saved: {md_path}")
    print(f"Saved: {pdf_path}")

    if picks:
        ledger.record_picks(picks, run_date)
        print(f"Ledger: recorded {len(picks)} picks -> {ledger.LEDGER_PATH}")
    else:
        print("Ledger: no picks extracted this run.")

    vault_path = obsidian.save_to_vault(markdown_text, run_date)
    if vault_path:
        print(f"Obsidian: saved to {vault_path}")
    else:
        print("Obsidian: vault not reachable, skipped (report still saved locally).")

    if send_email:
        print(f"Emailing report to {config.EMAIL_TO}...")
        emailer.send_report_email(
            subject=f"Daily Market Report — {run_date}",
            body_text="Attached: today's automated market and investment report.",
            pdf_path=pdf_path,
        )
        print("Email sent.")

    print("\n--- Executive Summary Preview ---\n")
    print(narrative[:1500])


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily stock news + investment report agent")
    parser.add_argument("--email", action="store_true", help="Email the report after building it")
    args = parser.parse_args()

    try:
        run(send_email=args.email)
    except RuntimeError as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

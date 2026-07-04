"""Assembles the final Markdown report and renders it to PDF."""
from datetime import date
from pathlib import Path

import markdown2
from xhtml2pdf import pisa

from src import config


def _movers_table(rows: list[dict], title: str) -> str:
    if not rows:
        return f"### {title}\n\n_No data available._\n"
    lines = [f"### {title}", "", "| Symbol | Name | Price | Change % |", "|---|---|---|---|"]
    for r in rows:
        lines.append(
            f"| {r.get('symbol', '')} | {r.get('name', '')} | "
            f"{r.get('price', '')} | {r.get('changesPercentage', '')} |"
        )
    return "\n".join(lines) + "\n"


def _sector_table(rows: list[dict], title: str = "Sector Performance") -> str:
    if not rows:
        return f"### {title}\n\n_No data available._\n"
    lines = [f"### {title}", "", "| Sector | Exchange | Avg Change % |", "|---|---|---|"]
    for r in sorted(rows, key=lambda r: r.get("averageChange", 0), reverse=True):
        lines.append(
            f"| {r.get('sector', '')} | {r.get('exchange', '')} | "
            f"{r.get('averageChange', 0.0):.2f} |"
        )
    return "\n".join(lines) + "\n"


def _headlines_list(articles: list[dict], title: str) -> str:
    if not articles:
        return f"### {title}\n\n_No data available._\n"
    lines = [f"### {title}", ""]
    for a in articles[:10]:
        src = (a.get("source") or {}).get("name", "")
        lines.append(f"- **{a.get('title', '')}** ({src})")
    return "\n".join(lines) + "\n"


def _macro_table(rows: list[dict]) -> str:
    if not rows:
        return "### Macro Levels\n\n_No data available._\n"
    lines = ["### Macro Levels", "", "| Index | Level | Change % |", "|---|---|---|"]
    for r in rows:
        lines.append(
            f"| {r.get('name', '')} | {r.get('price', '')} | "
            f"{r.get('changePercentage', '')} |"
        )
    return "\n".join(lines) + "\n"


def _earnings_table(rows: list[dict]) -> str:
    if not rows:
        return "### Upcoming Earnings (next 7 days)\n\n_No data available._\n"
    lines = [
        "### Upcoming Earnings (next 7 days)", "",
        "| Symbol | Date | Est. EPS | Est. Revenue |", "|---|---|---|---|",
    ]
    for r in rows[:20]:
        rev = r.get("revenueEstimated")
        rev_str = f"{rev / 1e9:.1f}B" if rev else ""
        lines.append(
            f"| {r.get('symbol', '')} | {r.get('date', '')} | "
            f"{r.get('epsEstimated', '')} | {rev_str} |"
        )
    return "\n".join(lines) + "\n"


def build_markdown(market_snapshot: dict, news_bundle: dict, analysis_narrative: str) -> str:
    today = date.today().isoformat()
    parts = [
        f"# Daily Market & Investment Report — {today}",
        "",
        analysis_narrative,
        "",
        "---",
        "",
        "## Appendix: Raw Data",
        "",
        _macro_table(market_snapshot.get("macro", [])),
        _earnings_table(market_snapshot.get("earnings_calendar", [])),
        _movers_table(market_snapshot.get("gainers", []), "Top Gainers"),
        _movers_table(market_snapshot.get("losers", []), "Top Losers"),
        _movers_table(market_snapshot.get("most_active", []), "Most Active"),
        _sector_table(market_snapshot.get("sector_performance", [])),
        _headlines_list(news_bundle.get("top_headlines", []), "Top Business Headlines"),
        _headlines_list(news_bundle.get("market_news", []), "Market News"),
        _headlines_list(news_bundle.get("sector_news", []), "Sector-Specific News"),
    ]
    return "\n".join(parts)


def save_report(markdown_text: str) -> tuple[Path, Path]:
    """Saves the report as both .md and .pdf. Returns (md_path, pdf_path)."""
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    md_path = config.REPORTS_DIR / f"{today}-report.md"
    pdf_path = config.REPORTS_DIR / f"{today}-report.pdf"

    md_path.write_text(markdown_text, encoding="utf-8")

    html_body = markdown2.markdown(markdown_text, extras=["tables", "fenced-code-blocks"])
    html_doc = f"""<html><head><meta charset="utf-8"><style>
    body {{ font-family: Helvetica, Arial, sans-serif; font-size: 11pt; }}
    h1 {{ font-size: 18pt; }}
    h2 {{ font-size: 14pt; margin-top: 18px; }}
    h3 {{ font-size: 12pt; margin-top: 12px; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 10px; }}
    th, td {{ border: 1px solid #999; padding: 4px 6px; font-size: 9pt; }}
    </style></head><body>{html_body}</body></html>"""

    with open(pdf_path, "wb") as f:
        result = pisa.CreatePDF(html_doc, dest=f)
    if result.err:
        raise RuntimeError("Failed to render PDF from report HTML.")

    return md_path, pdf_path

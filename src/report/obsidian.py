"""Saves reports into the Obsidian vault and feeds prior reports back in.

Each run writes the full report to `<vault>/Financial Analysis/` with
frontmatter, and the next run loads recent reports from there as context —
giving the agent continuity across days.
"""
from datetime import datetime
from pathlib import Path

from src import config

ANALYSIS_DIR = Path(config.OBSIDIAN_VAULT_DIR) / "Financial Analysis"

# How much of each prior report to feed back in (frontmatter stripped).
HISTORY_FILES = 5
HISTORY_CHARS_PER_FILE = 3500


def save_to_vault(markdown_text: str, run_date: str) -> Path | None:
    """Writes the report as a vault note. Returns the path, or None if the
    vault directory isn't reachable (report still exists in reports/)."""
    try:
        ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
        note_path = ANALYSIS_DIR / f"{run_date} Market Report.md"
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        frontmatter = (
            "---\n"
            "type: financial-analysis\n"
            "tags: [finance, daily-report, stock-agent]\n"
            f"created: {now}\n"
            f"updated: {now}\n"
            "---\n\n"
        )
        note_path.write_text(frontmatter + markdown_text, encoding="utf-8")
        return note_path
    except OSError:
        return None


def load_recent_reports(exclude_date: str) -> list[dict]:
    """Returns snippets of the most recent prior reports for continuity.
    Excludes today's own note so a re-run doesn't feed itself."""
    if not ANALYSIS_DIR.exists():
        return []
    notes = sorted(ANALYSIS_DIR.glob("*Market Report.md"), reverse=True)
    history = []
    for note in notes:
        if exclude_date in note.name:
            continue
        try:
            text = note.read_text(encoding="utf-8")
        except OSError:
            continue
        if text.startswith("---"):
            end = text.find("---", 3)
            if end != -1:
                text = text[end + 3:]
        history.append({"note": note.stem, "content": text.strip()[:HISTORY_CHARS_PER_FILE]})
        if len(history) >= HISTORY_FILES:
            break
    return history

"""Central config loaded from environment / .env."""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

FMP_API_KEY = os.getenv("FMP_API_KEY", "")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
ANALYSIS_MODEL = os.getenv("ANALYSIS_MODEL", "gemini-2.5-flash")

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "")
EMAIL_TO = os.getenv("EMAIL_TO", "")

REPORTS_DIR = ROOT_DIR / "reports"

OBSIDIAN_VAULT_DIR = os.getenv(
    "OBSIDIAN_VAULT_DIR", r"C:\Users\eriku\Vaults\Obsidian\Erik"
)


def require(value: str, name: str) -> str:
    if not value:
        raise RuntimeError(
            f"Missing required config '{name}'. Set it in {ROOT_DIR / '.env'} "
            f"(see .env.example)."
        )
    return value

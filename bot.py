import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from pprint import pprint

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

BROWSERS = {"chromium", "firefox", "webkit"}
DEFAULT_BROWSER = "firefox"
NO_CITAS_TEXT = "En este momento no hay citas disponibles"

@dataclass
class Config:
    base_url: str
    motive: str
    office: str
    doc_type: str
    doc_number: str
    full_name: str
    birth_year: int
    country: str
    min_wait: int
    max_wait: int
    telegram_bot_token: str
    telegram_chat_id: str
    browser: str

REQUIRED = [
    "BASE_URL", "MOTIVE", "OFFICE", "DOC_TYPE", "DOC_NUMBER",
    "FULL_NAME", "BIRTH_YEAR", "COUNTRY", "MIN_WAIT", "MAX_WAIT",
]

# Function to load the configuration file and parse input values
def load_config(path: str = "config.toml") -> Config:
    raw = tomllib.loads(Path(path).read_text(encoding="utf-8"))

    # Check for missing values
    missing = [k for k in REQUIRED if k not in raw or raw[k] in ("", None)]
    if missing:
        raise ValueError(f"Missing required config values: {', '.join(missing)}")

    cfg = Config(
        base_url = raw["BASE_URL"],
        motive = str(raw["MOTIVE"]),
        office = str(raw["OFFICE"]),
        doc_type = str(raw["DOC_TYPE"]).lower(),
        doc_number = raw["DOC_NUMBER"].upper(),
        full_name = raw["FULL_NAME"].upper(),
        birth_year = int(raw["BIRTH_YEAR"]),
        country = raw["COUNTRY"],
        min_wait = int(raw["MIN_WAIT"]),
        max_wait = int(raw["MAX_WAIT"]),
        telegram_bot_token = raw.get("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id = str(raw.get("TELEGRAM_CHAT_ID", "")),
        browser = str(raw.get("BROWSER", DEFAULT_BROWSER)).lower(),
    )

    # Sanitize input values
    if cfg.browser not in BROWSERS:
        raise ValueError(f"BROWSER must be one of {sorted(BROWSERS)}, got {cfg.browser!r}")
    if cfg.doc_type not in {"nie", "passport"}:
        raise ValueError(f"DOC_TYPE must be 'nie' or 'passport', got {cfg.doc_type!r}")
    if cfg.min_wait >= cfg.max_wait:
        raise ValueError("MIN_WAIT must be lower than MAX_WAIT")
    if "p=" not in cfg.base_url:
        raise ValueError("BASE_URL must contain a province code (p=...)")

    return cfg

# Install the browser engine if it is not already installed
def install_browser(browser: str) -> None:
    # Try to run the browser to see if the engine is present
    try:
        with sync_playwright() as pw:
            b = getattr(pw, browser).launch(headless=True)
            b.close()
        return
    except Exception:
        pass

    print(f"Browser '{browser}' not installed, downloading...")
    subprocess.run([sys.executable, "-m", "playwright", "install", browser], check=True)
    print(f"Browser '{browser}' installed")

def main() -> None:
    cfg = load_config()
    pprint(f"{cfg}")

    install_browser(cfg.browser)

if __name__ == "__main__":
    main()
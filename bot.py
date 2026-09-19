import subprocess
import random
import sys
import tomllib
import time
import urllib.parse
import urllib.request
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from playwright.sync_api import sync_playwright

BROWSER_ENGINES = {"chromium", "firefox", "webkit"}
DEFAULT_BROWSER = "chromium"
LOCAL_BROWSERS = {"chrome", "msedge"}
ALL_BROWSERS = BROWSER_ENGINES | LOCAL_BROWSERS

NO_CITAS_TEXT = "En este momento no hay citas disponibles"
WAF_BLOCK_TEXT = "The requested URL was rejected"
TELEGRAM_MESSAGE = "There is an available appointment, complete the reservation manually"
TELEGRAM_WAF_BLOCK_MESSAGE = "Bot blocked by the WAF, backing off"

# HTML elements
MOTIVE_SELECTION = "select[id^='tramiteGrupo']"
ACCEPT_BUTTON = "#btnAceptar"
CONTINUE_BUTTON = "#btnEntrar"
SEND_BUTTON = "#btnEnviar"
RADIAL_NIE = "#rdbTipoDocNie"
RADIAL_PASSPORT = "#rdbTipoDocPas"
DOC_NUMBER_TEXT = "#txtIdCitado"
FULL_NAME_TEXT = "#txtDesCitado"
BIRTHYEAR_TEXT = "#txtAnnoCitado"
NATIONALITY_SELECT = "#txtPaisNac"
INFO_MSG_NO_APPOINTMENTS = ".mf-msg__info"
RESULT_OFFICES  = "select[id^='idSede']"

# Wait times
MIN_HUMAN_SLEEP = 3
MAX_HUMAN_SLEEP = 5
FAST_MIN_HUMAN_SLEEP = 1
FAST_MAX_HUMAN_SLEEP = 2

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
    waf_backoff: int
    telegram_bot_token: str
    telegram_chat_ids: list[str]
    browser: str

REQUIRED = [
    "BASE_URL", "MOTIVE", "OFFICE", "DOC_TYPE", "DOC_NUMBER",
    "FULL_NAME", "BIRTH_YEAR", "COUNTRY", "MIN_WAIT", "MAX_WAIT", "WAF_BACKOFF"
]

# Human-like wait to avoid bot detection
def human_sleep(min_s, max_s) -> None:
    time.sleep(random.uniform(min_s, max_s))

# Human-like fill for text fields to avoid bot detection
def human_fill(page, selector: str, text: str) -> None:
    human_sleep(FAST_MIN_HUMAN_SLEEP, FAST_MAX_HUMAN_SLEEP)
    page.click(selector)
    # 70 and 160 stand for the millisecond wait per key
    page.type(selector, text, delay=random.uniform(70, 160))

# Human-like button click to avoid bot detection
def human_click(page, selector: str) -> None:
    page.hover(selector)
    human_sleep(FAST_MIN_HUMAN_SLEEP, FAST_MAX_HUMAN_SLEEP)
    # 60 and 140 stand for the delay between down-up
    page.click(selector, delay=random.uniform(60, 140))

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
        min_wait = int(raw["MIN_WAIT"]) * 60, # Convert to seconds
        max_wait = int(raw["MAX_WAIT"]) * 60, # Convert to seconds
        waf_backoff = int(raw["WAF_BACKOFF"]) * 60, # Convert to seconds
        telegram_bot_token = raw.get("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_ids = [str(x) for x in raw.get("TELEGRAM_CHAT_IDS", [])],
        browser = str(raw.get("BROWSER", DEFAULT_BROWSER)).lower(),
    )

    # Sanitize input values
    if cfg.browser not in ALL_BROWSERS:
        raise ValueError(f"BROWSER must be one of {sorted(ALL_BROWSERS)}, got {cfg.browser!r}")
    if cfg.doc_type not in {"nie", "passport"}:
        raise ValueError(f"DOC_TYPE must be 'nie' or 'passport', got {cfg.doc_type!r}")
    if cfg.min_wait >= cfg.max_wait:
        raise ValueError("MIN_WAIT must be lower than MAX_WAIT")
    if "p=" not in cfg.base_url:
        raise ValueError("BASE_URL must contain a province code (p=...)")

    return cfg

# Install the browser engine if it is not already installed
def install_browser(browser: str) -> None:
    if browser in LOCAL_BROWSERS:
        return  # system-installed, nothing to download

    # Try to run the browser to see if the engine is present
    try:
        with sync_playwright() as pw:
            b = getattr(pw, browser).launch(headless=True)
            b.close()
        return
    except Exception:
        pass

    logging.info(f"Browser '{browser}' not installed, downloading...")
    subprocess.run([sys.executable, "-m", "playwright", "install", browser], check=True)
    logging.info(f"Browser '{browser}' installed")


# Launch the configured browser
def launch_browser(pw, name: str):
    if name in LOCAL_BROWSERS:
        return pw.chromium.launch(channel=name, headless=False)

    launcher = getattr(pw, name)
    if name == "chromium":
        return launcher.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
    if name == "firefox":
        return launcher.launch(
            headless=False,
            firefox_user_prefs={
                "dom.webdriver.enabled": False,
                "useAutomationExtension": False,
            },
        )
    if name == "webkit": return launcher.launch(headless=False)

# Check if the appointment for the NIE is available
def check_nie_appointment(page, cfg: Config) -> bool | None:
    # Go to starting page
    page.goto(cfg.base_url)

    # WAF rejection page, wait a long backoff and try again
    if WAF_BLOCK_TEXT in page.content():
        retry_at = datetime.now() + timedelta(seconds=cfg.waf_backoff)
        logging.warning(f"WAF blocked this session, backing off until {retry_at.strftime('%H:%M')}")
        notify_telegram(cfg, TELEGRAM_WAF_BLOCK_MESSAGE)
        time.sleep(cfg.waf_backoff)
        return None

    # Page 1: Motive selection
    human_sleep(MIN_HUMAN_SLEEP, MAX_HUMAN_SLEEP) # Simulate reading page
    page.select_option(MOTIVE_SELECTION, value=cfg.motive)
    human_sleep(FAST_MIN_HUMAN_SLEEP, FAST_MAX_HUMAN_SLEEP)
    human_click(page, ACCEPT_BUTTON)

    # Page 2: Info page
    human_sleep(MIN_HUMAN_SLEEP, MAX_HUMAN_SLEEP) # Simulate reading page
    human_click(page, CONTINUE_BUTTON)

    # Page 3: Personal data form
    human_sleep(MIN_HUMAN_SLEEP, MAX_HUMAN_SLEEP) # Simulate reading page
    if cfg.doc_type == "nie":
        human_click(page, RADIAL_NIE)
    else:
        human_click(page, RADIAL_PASSPORT)

    human_fill(page, DOC_NUMBER_TEXT, cfg.doc_number)
    human_fill(page, FULL_NAME_TEXT, cfg.full_name)
    human_fill(page, BIRTHYEAR_TEXT, str(cfg.birth_year))
    human_sleep(MIN_HUMAN_SLEEP, MAX_HUMAN_SLEEP)
    page.select_option(NATIONALITY_SELECT, label=cfg.country)
    human_click(page, SEND_BUTTON)

    # Page 4: Confirm
    human_sleep(MIN_HUMAN_SLEEP, MAX_HUMAN_SLEEP) # Simulate reading page
    human_click(page, SEND_BUTTON)

    # Page 5: Result, info banner means no appointments, office picker means availability
    page.wait_for_selector(
        f"{INFO_MSG_NO_APPOINTMENTS}, {RESULT_OFFICES}",
        state="visible",
        timeout=15000,
    )
    banner = page.query_selector(INFO_MSG_NO_APPOINTMENTS)
    if banner and NO_CITAS_TEXT in banner.inner_text():
        return False
    if page.query_selector(RESULT_OFFICES):
        return True
    raise RuntimeError("unexpected result page — layout changed?")

# Send a message via Telegram to the configured chat
def notify_telegram(cfg: Config, message: str) -> None:
    if not cfg.telegram_bot_token or not cfg.telegram_chat_ids:
        logging.info("Telegram not configured, skipping notification")
        return

    url = f"https://api.telegram.org/bot{cfg.telegram_bot_token}/sendMessage"
    for chat_id in cfg.telegram_chat_ids:
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": message,
        }).encode()
        try:
            urllib.request.urlopen(url, data=data, timeout=15)
        except Exception as e:
            logging.error(f"Telegram failed for chat {chat_id}: {e}")

def main() -> None:
    # Set up logger
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("bot.log"),
        ],
    )

    cfg = load_config()
    logging.info(f"{cfg}")
    config_mtime = Path("config.toml").stat().st_mtime

    install_browser(cfg.browser)

    with sync_playwright() as pw:
        # Set up the browser
        browser = launch_browser(pw, cfg.browser)
        context = browser.new_context(locale="es-ES")
        page = context.new_page()

        try:
            while True:
                # Check if the appointment is available
                try:
                    found = check_nie_appointment(page, cfg)
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    logging.error(f"Flow error: {e}")
                    found = False

                # WAF backoff already slept, start next check right away
                if found is None:
                    continue

                # If there is an appointment print a note and stop
                if found:
                    logging.info("Appointment available, complete the process manually")
                    notify_telegram(cfg, TELEGRAM_MESSAGE)
                    input("Pause, press Enter to restart the loop or Ctrl+C to exit")
                    continue

                # Wait until next request
                wait = random.randint(cfg.min_wait, cfg.max_wait)
                next_check = datetime.now() + timedelta(seconds=wait)
                logging.info(f"No available appointments, next check at {next_check.strftime('%H:%M')}")
                time.sleep(wait)

                # Reload the config only if the file changed on disk
                try:
                    mtime = Path("config.toml").stat().st_mtime
                except FileNotFoundError:
                    logging.warning("config.toml not found, keeping the previous configuration")
                else:
                    if mtime != config_mtime:
                        logging.info("Config file changed, reloading the configuration ...")
                        cfg = load_config()
                        config_mtime = mtime

        except KeyboardInterrupt:
            logging.info("Shutting down gracefully...")
        finally:
            try:
                browser.close()
            except Exception:
                pass

if __name__ == "__main__":
    main()
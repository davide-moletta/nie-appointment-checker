# nie-appointment-checker

A semi-automated checker for appointment (cita previa) availability on the Spanish police booking portal.

The bot drives a real browser through the multi-step booking flow with human-like pacing, reads the result page, and repeats on a randomized schedule. When slots are available it stops, plays no tricks with the final CAPTCHA/SMS steps, and leaves the browser tab open so you complete the booking manually.

## Requirements

Install Python 3.11+ with venv and pip support, and make:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip make
```

Verify:

```bash
python3 --version   # must print 3.11 or newer
```

## Setup

Fill your personal data in the `config.toml` file.

Create `.venv` and install required libraries:

```bash
make install
```

Run the bot:

```bash
make run
```

## Configuration

`config.toml` contains every setting, with all available values documented
directly in the file as comments (province codes, trámite codes, office codes,
nationality values, etc.), read it top to bottom and fill in your data.

The bot validates the config at startup and refuses to run with empty or
inconsistent values. If the portal flow fails partway through a run, it almost
always means one of the values you entered does not match the portal, check
your trámite code matches the province in `BASE_URL`, and that `COUNTRY` is
written exactly as it appears in the nationality dropdown.

### Telegram notification (optional)

If you whish to use Telegram notification follow these steps:

1. Open [@BotFather](https://t.me/BotFather), send `/newbot`, follow the prompts to get a token like `123456:ABC-...`
2. Send any message to your new bot, then ask [@userinfobot](https://t.me/userinfobot) for your chat ID
3. Fill both values in `config.toml` under `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` respectively

## Project structure

```bash
.
├── .gitignore 
├── bot.py
├── config.toml
├── LICENSE
├── Makefile
├── README
└── requirements.txt
```

## TODO

- Timestamp log for every check
- Config hot-reload each loop (tune waits without restarting)
- Optional headless mode for unattended monitoring

VENV := .venv
PYTHON := python3
PIP := $(VENV)/bin/pip
BOT := $(VENV)/bin/python bot.py

$(VENV)/bin/activate: requirements.txt
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	touch $(VENV)/bin/activate

.PHONY: venv install run clean

venv: $(VENV)/bin/activate ## Create virtual environment and install Python deps

install: venv ## Setup the project

run: install ## Run the bot (downloads the configured browser on first run)
	$(BOT)

clean:	## Remove virtual environment
	rm -rf $(VENV)
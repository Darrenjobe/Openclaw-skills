PYTHON   := python3
VENV     := .venv
PIP      := $(VENV)/bin/pip
VENV_PY  := $(VENV)/bin/python

.DEFAULT_GOAL := help

.PHONY: help setup run recent top hashtags test clean

help:
	@echo ""
	@echo "x-research skill — available targets:"
	@echo ""
	@echo "  make setup     Create .venv, install dependencies, copy config template"
	@echo "  make run       Run a research pass (topics from config.yaml)"
	@echo "  make recent    Show most recently stored tweets"
	@echo "  make top       Show top tweets by engagement"
	@echo "  make hashtags  Show trending hashtags"
	@echo "  make test      Run the test suite"
	@echo "  make clean     Remove .venv and generated data"
	@echo ""

# ── Setup ─────────────────────────────────────────────────────────────────────

$(VENV)/bin/activate: requirements.txt
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip --quiet
	$(PIP) install -r requirements.txt --quiet
	@touch $(VENV)/bin/activate

setup: $(VENV)/bin/activate
	@if [ ! -f config.yaml ]; then \
		cp config.example.yaml config.yaml; \
		echo ""; \
		echo "  config.yaml created from template."; \
		echo "  Edit it to add your topics (and optionally an X API Bearer Token)."; \
		echo ""; \
	else \
		echo "  config.yaml already exists — skipping copy."; \
	fi
	@echo "  Setup complete. Run 'make run' to start researching."

# ── Skill commands ─────────────────────────────────────────────────────────────

run: $(VENV)/bin/activate
	$(VENV_PY) src/main.py run

recent: $(VENV)/bin/activate
	$(VENV_PY) src/main.py recent

top: $(VENV)/bin/activate
	$(VENV_PY) src/main.py top

hashtags: $(VENV)/bin/activate
	$(VENV_PY) src/main.py hashtags

# ── Tests ─────────────────────────────────────────────────────────────────────

test: $(VENV)/bin/activate
	$(VENV_PY) -m pytest tests/ -v

# ── Cleanup ───────────────────────────────────────────────────────────────────

clean:
	rm -rf $(VENV) data/
	@echo "Removed .venv and data/."

PYTHON   := python3
VENV     := .venv
PIP      := $(VENV)/bin/pip
VENV_PY  := $(VENV)/bin/python

.DEFAULT_GOAL := help

.PHONY: help setup run ask recent test clean

help:
	@echo ""
	@echo "web-research skill — available targets:"
	@echo ""
	@echo "  make setup          Create .venv, install dependencies, copy config template"
	@echo "  make run            Run research on all queries in config.yaml"
	@echo "  make ask Q='...'    Run a one-off research query"
	@echo "  make recent         Show most recently stored results"
	@echo "  make test           Run the test suite"
	@echo "  make clean          Remove .venv and generated data"
	@echo ""
	@echo "Examples:"
	@echo "  make ask Q='What is happening in Iran?'"
	@echo "  make ask Q='Latest Raspberry Pi news'"
	@echo ""

# ── Setup ──────────────────────────────────────────────────────────────────────

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
		echo "  Edit it to add your queries and set your Anthropic API key."; \
		echo "  Either set claude.api_key in config.yaml or:"; \
		echo "    export ANTHROPIC_API_KEY=your_key"; \
		echo ""; \
	else \
		echo "  config.yaml already exists — skipping copy."; \
	fi
	@echo "  Setup complete."
	@echo "  Run 'make ask Q=\"What is happening in Iran?\"' to get started."

# ── Skill commands ─────────────────────────────────────────────────────────────

run: $(VENV)/bin/activate
	PYTHONPATH=../../ $(VENV_PY) src/main.py run

ask: $(VENV)/bin/activate
	@if [ -z "$(Q)" ]; then \
		echo "Usage: make ask Q=\"your research question\""; \
		exit 1; \
	fi
	PYTHONPATH=../../ $(VENV_PY) src/main.py ask "$(Q)"

recent: $(VENV)/bin/activate
	PYTHONPATH=../../ $(VENV_PY) src/main.py recent

# ── Tests ──────────────────────────────────────────────────────────────────────

test: $(VENV)/bin/activate
	PYTHONPATH=../../ $(VENV_PY) -m pytest tests/ -v

# ── Cleanup ────────────────────────────────────────────────────────────────────

clean:
	rm -rf $(VENV) data/
	@echo "Removed .venv and data/."

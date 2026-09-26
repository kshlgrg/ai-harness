SHELL := /bin/bash
VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: all setup run test clean benchmark help

all: setup test

help:
	@echo "AI Harness Hackathon 2026 - Standardised Makefile"
	@echo "Commands:"
	@echo "  make setup      - Install and configure all required dependencies"
	@echo "  make run        - Initialise and launch the AI Harness"
	@echo "  make test       - Execute internal test and evaluation procedure"
	@echo "  make clean      - Remove generated artefacts, where applicable"
	@echo "  make benchmark  - Run comparative benchmark suite"

setup:
	@echo "==> [make setup] Installing and configuring all required dependencies..."
	@if [ ! -d "$(VENV)" ]; then \
		echo "Creating isolated virtual environment in $(VENV)..."; \
		python3 -m venv $(VENV); \
	fi
	@echo "Installing package dependencies into $(VENV)..."
	@$(PIP) install --quiet --upgrade pip
	@$(PIP) install --quiet -r requirements.txt
	@$(PIP) install --quiet -e .
	@mkdir -p .agent/runs .agent/cache
	@echo "==> [make setup] Setup completed successfully."

run:
	@if [ ! -f "$(PYTHON)" ]; then \
		echo "[NOTICE] Virtual environment not found. Initialising setup..."; \
		$(MAKE) setup; \
	fi
	@mkdir -p .agent/runs
	@echo "==> [make run] Initialising and launching AI Harness..."
	@$(PYTHON) -m forge.cli run $(if $(ISSUE),--issue "$(ISSUE)",)

test:
	@if [ ! -f "$(PYTHON)" ]; then \
		echo "[NOTICE] Virtual environment not found. Initialising setup..."; \
		$(MAKE) setup; \
	fi
	@echo "==> [make test] Executing test and evaluation procedure..."
	@$(PYTHON) -m pytest -v tests/

clean:
	@echo "==> [make clean] Removing generated artefacts..."
	@rm -rf .pytest_cache __pycache__ */__pycache__ */*/__pycache__
	@rm -rf build dist *.egg-info
	@rm -rf .agent/runs/* .agent/cache/*
	@echo "==> [make clean] Clean completed."

benchmark:
	@if [ ! -f "$(PYTHON)" ]; then \
		$(MAKE) setup; \
	fi
	@$(PYTHON) -m forge.cli benchmark

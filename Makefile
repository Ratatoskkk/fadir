# fadir — multi-currency portfolio PnL tracker (SPEC §1).
#
# Bound to loopback only. No cloud, no auth, no external hosting.

SHELL := /bin/bash

VENV    := .venv
ifeq ($(OS),Windows_NT)
  PY    := $(VENV)/Scripts/python.exe
  PIP   := $(VENV)/Scripts/pip.exe
else
  PY    := $(VENV)/bin/python
  PIP   := $(VENV)/bin/pip
endif

HOST := 127.0.0.1
PORT := 8000

.DEFAULT_GOAL := help
.PHONY: help venv install verify bootstrap demo build run dev api web test test-live golden clean reset

help:  ## show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

venv:  ## create the virtualenv
	python -m venv $(VENV)

install: venv  ## install python + node dependencies
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r requirements-dev.txt
	cd frontend && npm install

verify:  ## SPEC §2 - verify every yfinance symbol resolves. Run this first.
	$(PY) scripts/verify_symbols.py

bootstrap:  ## create the DB, import data/seed_transactions.csv if present, fetch prices
	$(PY) scripts/bootstrap.py

demo:  ## fill the DB with the worked example instead of your own data
	$(PY) scripts/bootstrap.py --seed examples/seed_transactions.example.csv

reset:  ## wipe the DB and re-bootstrap from scratch
	$(PY) scripts/bootstrap.py --reset

build:  ## bundle the frontend into frontend/dist
	cd frontend && npm run build

run: build  ## serve the dashboard on 127.0.0.1:8000 (production mode)
	$(PY) -m uvicorn app.main:app --host $(HOST) --port $(PORT)

api:  ## run the API alone, with autoreload (no frontend build)
	$(PY) -m uvicorn app.main:app --host $(HOST) --port $(PORT) --reload

web:  ## run the Vite dev server (proxies /api to $(HOST):$(PORT))
	cd frontend && npm run dev

dev:  ## development: API with autoreload + Vite dev server together
	@echo "API  -> http://$(HOST):$(PORT)"
	@echo "App  -> http://localhost:5173"
	@$(MAKE) -j2 api web

test:  ## run the test suite (live tests excluded)
	$(PY) -m pytest

test-live:  ## run only the live network test
	$(PY) -m pytest -m live

golden:  ## regenerate the reconciliation golden file
	$(PY) scripts/make_golden.py

clean:  ## remove build artefacts and caches
	rm -rf frontend/dist frontend/node_modules/.vite
	find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache

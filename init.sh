#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  python -m venv .venv
fi

if [ -f ".venv/Scripts/activate" ]; then
  source .venv/Scripts/activate
elif [ -f ".venv/bin/activate" ]; then
  source .venv/bin/activate
fi

python -m pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium
pytest -m "not live"

#!/usr/bin/env bash
set -euo pipefail

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp -n .env.example .env || true

mkdir -p data/raw data/processed data/chroma

echo "Bootstrap complete. Activate with: source .venv/bin/activate"

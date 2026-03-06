#!/usr/bin/env bash
set -euo pipefail

if [[ ! -d .venv ]]; then
  ./scripts/bootstrap.sh
fi

source .venv/bin/activate
export ANONYMIZED_TELEMETRY=False
pip install -e ".[dev]" -q

mkdir -p data/raw
cat > data/raw/sample.txt <<'TXT'
ChromaDB stores embeddings and metadata for local retrieval.
TXT

python -m alcove.ingest.pipeline
python -m alcove.index.pipeline
python -m alcove.query.cli "What does ChromaDB store?" --k 1

make seed-demo

test -f data/raw/seed/alice.txt
test -f data/raw/seed/frankenstein.txt
test -f data/processed/chunks.jsonl
test -f data/processed/seed_index.json

pytest -q

echo "smoke ok"

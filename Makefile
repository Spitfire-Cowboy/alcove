SHELL := /bin/bash

setup:
	./scripts/bootstrap.sh
	pip install -e ".[dev]"

serve:
	source .venv/bin/activate && alcove serve

ingest:
	source .venv/bin/activate && python -m alcove.ingest.pipeline

index:
	source .venv/bin/activate && python -m alcove.index.pipeline

query:
	source .venv/bin/activate && python -m alcove.query.cli "$(Q)"

seed-fetch:
	python3 scripts/fetch_seed_corpus.py

seed-ingest:
	python3 scripts/ingest_seed_demo.py

seed-index:
	python3 scripts/build_seed_index.py

seed-demo: seed-fetch seed-ingest seed-index

smoke:
	./scripts/smoke.sh

test:
	python3 -m pytest -q

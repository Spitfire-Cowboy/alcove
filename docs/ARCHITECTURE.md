# ARCHITECTURE

## Pipeline (local-only default)

1) `alcove/ingest` discovers `data/raw/**` and extracts `.txt/.pdf/.epub` into chunked JSONL.

2) `alcove/index` reads chunks and writes embeddings + metadata to local Chroma persistence.

3) `alcove/query` retrieves from local Chroma by CLI or tiny FastAPI service.

## Data flow

`data/raw/*` → `data/processed/chunks.jsonl` → `data/chroma/*` → query responses

## Boundary

- Operator owns host + storage.
- No default outbound integrations.
- Telemetry set off by default.

## Tradeoffs

- Deterministic hash embedder for reproducibility over quality.
- Thin implementation for speed-to-demo.

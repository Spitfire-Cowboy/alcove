# OPERATIONS

## First run

```bash
cp .env.example .env
make setup
```

Add files to `data/raw/`, then:

```bash
make ingest
make index
make query Q="what is in this corpus?"
```

## Smoke

```bash
make smoke
```

## Web UI + API

```bash
alcove serve
# or: make serve
```

- `GET /` — web UI (search + file upload)
- `POST /query` with `{ "query": "...", "k": 3 }`
- `POST /ingest` — file upload (multipart)
- `GET /health` — readiness check

## Docker (optional)

```bash
docker compose up -d --build
```

## Backup

Backup `data/raw`, `data/processed`, and `data/chroma`.

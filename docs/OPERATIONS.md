# Operations

This guide covers the shipped local runtime: install, ingest, index, search, serve, back up, and test. It does not cover planned MCP, registry, or hosted-index workflows.

## First run

```bash
pip install alcove-search[semantic]
alcove seed-demo
alcove serve
```

Open `http://localhost:8000`.

`seed-demo` fetches the public sample corpus, ingests it, and builds a local index. See [Seed Corpus](SEED_CORPUS.md) for what it includes.

For the zero-download base install:

```bash
pip install alcove-search
alcove seed-demo
alcove serve
```

The base install uses the hash embedder. It is deterministic and offline, but it is not a semantic model.

## Dependency verification

For low-trust or release-verification environments, keep installs aligned with the public base-runtime constraints:

```bash
pip install -c constraints/base-runtime.txt .
python3 scripts/check_dependency_integrity.py
```

The verifier reports three things:
- whether `constraints/base-runtime.txt` still matches `[project.dependencies]` in `pyproject.toml`
- whether installed package versions satisfy the public base-runtime constraints
- which installed packages include native extensions, which are the highest-trust dependency artifacts to review first

For development, install the extras you need on top of the same base constraints. The public repo does not ship a full hash-pinned lockfile; the maintained contract today is the checked-in constraints file plus the drift report.

## Local Ollama embeddings

If you already run Ollama locally, Alcove can use an embedding model served from that local process:

```bash
ollama pull nomic-embed-text
EMBEDDER=ollama OLLAMA_MODEL=nomic-embed-text alcove seed-demo
EMBEDDER=ollama OLLAMA_MODEL=nomic-embed-text alcove serve
```

By default Alcove connects to `http://127.0.0.1:11434`. Set `OLLAMA_BASE_URL` to use another operator-managed local endpoint. When using the zvec backend with a non-default embedding model, set `OLLAMA_DIM` to that model's vector dimension before creating the index.

## Custom documents

```bash
alcove ingest /path/to/your/files
alcove search "phrase to find" --mode hybrid --k 5
alcove serve
```

Files can also be uploaded through the local web UI.

## Search modes

```bash
alcove search "local search" --mode semantic
alcove search "exact phrase" --mode keyword
alcove search "mix both" --mode hybrid
```

| Mode | Use when |
|------|----------|
| `semantic` | You installed `[semantic]` and want meaning-based retrieval. |
| `keyword` | Exact terms, names, identifiers, or hash-only installs matter more. |
| `hybrid` | You want semantic retrieval with keyword backup. |

## Enabling semantic search

```bash
pip install alcove-search[semantic]
EMBEDDER=sentence-transformers alcove ingest /path/to/files
EMBEDDER=sentence-transformers alcove serve
```

The first run downloads `all-MiniLM-L6-v2`. The model is cached locally; later runs do not require network access.

## Web UI and API

```bash
alcove serve --host 127.0.0.1 --port 8000
```

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web UI: search and file upload |
| `/query` | POST | Search JSON: `{ "query": "...", "k": 3, "mode": "hybrid" }` |
| `/ingest` | POST | File upload (multipart) |
| `/collections` | GET | Collection names and document counts |
| `/health` | GET | Readiness check |

Bind to a non-localhost address only after reviewing [Security: Operator Responsibilities](SECURITY.md#operator-responsibilities). Alcove has no built-in authentication.

## Collections

Collections are metadata labels used for filtering. Uploaded files and index runs default to `default` unless a caller supplies a collection.

```bash
alcove collections
```

For ChromaDB, `CHROMA_COLLECTION=*` or `ALCOVE_MULTI_COLLECTION=1` enables fan-out across named ChromaDB collections in the same local store. Demo multi-root mode is controlled by `ALCOVE_DEMO_ROOT` and is read-only.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBEDDER` | `hash` | Embedder to use (`hash`, `sentence-transformers`, or `ollama`) |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Local Ollama base URL when `EMBEDDER=ollama` |
| `OLLAMA_MODEL` | `nomic-embed-text` | Ollama embedding model when `EMBEDDER=ollama` |
| `OLLAMA_TIMEOUT` | `60` | Ollama request timeout in seconds |
| `OLLAMA_DIM` | `768` | Ollama embedding dimension for backends that need it at initialization |
| `VECTOR_BACKEND` | `chromadb` | Vector store (`chromadb` or `zvec`) |
| `CHROMA_PATH` | `./data/chroma` | ChromaDB persistence directory |
| `CHROMA_COLLECTION` | `alcove_docs` | ChromaDB collection name; `*` enables multi-collection fan-out |
| `ZVEC_PATH` | `./data/zvec` | zvec persistence directory |
| `CHUNK_SIZE` | `1000` | Characters per chunk |
| `CHUNK_OVERLAP` | `150` | Overlap between chunks |
| `RAW_DIR` | `data/raw` | Default input directory for ingestion |
| `ALCOVE_MULTI_COLLECTION` | unset | Set to `1`, `true`, or `yes` to query all ChromaDB collections |
| `ALCOVE_ROOT_PATH` | unset | URL prefix when served behind a reverse proxy |
| `ALCOVE_DEMO_READONLY` | unset | Disable web upload ingest in demo/read-only mode |

## Docker

```bash
docker compose up -d --build
```

Port 8000 is exposed. Use `/health` for readiness checks.

## Backup and rebuild

Back up:

- `data/raw`
- `data/processed`
- `data/chroma` for ChromaDB
- `data/zvec` for zvec

The raw files and processed chunks are enough to rebuild the vector store. Keeping the vector store avoids re-embedding.

## Running tests

```bash
pip install -e ".[dev]"
pytest
```

Docs hygiene checks live in `tests/test_public_docs_hygiene.py`:

```bash
pytest tests/test_public_docs_hygiene.py
```

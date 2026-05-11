# Operations

## First run

```bash
pip install alcove-search
alcove seed-demo          # download sample corpus + build index
alcove serve              # open http://localhost:8000
```

For how the pipeline works, see [Architecture](ARCHITECTURE.md).

## Enabling semantic search

By default, Alcove uses a deterministic hash embedder (offline, no external models). For semantic search:

```bash
pip install alcove-search[semantic]
EMBEDDER=sentence-transformers alcove seed-demo
EMBEDDER=sentence-transformers alcove serve
```

This downloads `all-MiniLM-L6-v2` (~80 MB) on first use. See [Seed Corpus](SEED_CORPUS.md) for what `seed-demo` includes. The model is cached locally; subsequent runs are offline.

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
alcove serve
```

Files can also be uploaded via the web UI at `http://localhost:8000`.

## Web UI and API

```bash
alcove serve
```

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web UI: search and file upload |
| `/query` | POST | `{ "query": "...", "k": 3 }` |
| `/ingest` | POST | File upload (multipart) |
| `/health` | GET | Readiness check |

Bind to a non-localhost address only after reviewing [Security: Operator Responsibilities](SECURITY.md#operator-responsibilities).

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBEDDER` | `hash` | Embedder to use (`hash`, `sentence-transformers`, or `ollama`) |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Local Ollama base URL when `EMBEDDER=ollama` |
| `OLLAMA_MODEL` | `nomic-embed-text` | Ollama embedding model when `EMBEDDER=ollama` |
| `OLLAMA_TIMEOUT` | `60` | Ollama request timeout in seconds |
| `OLLAMA_DIM` | `768` | Ollama embedding dimension for backends that need it at initialization |
| `ALCOVE_LANGUAGE_PROVIDER` | `heuristic` | Language metadata detector (`none`, `heuristic`, `langdetect`, `transformers`, `huggingface`, `ollama`, or plugin name) |
| `ALCOVE_LANGUAGE_MODEL` | provider-specific | Hugging Face or Ollama model for language detection |
| `ALCOVE_LANGUAGE_CONFIDENCE_THRESHOLD` | `0.0` | Minimum detector confidence before writing a language code |
| `ALCOVE_LANGUAGE_OLLAMA_BASE_URL` | `OLLAMA_BASE_URL` or `http://127.0.0.1:11434` | Local Ollama base URL for `ALCOVE_LANGUAGE_PROVIDER=ollama` |
| `ALCOVE_LANGUAGE_TIMEOUT` | `30` | Ollama language detection timeout in seconds |
| `ALCOVE_LANGUAGE_MAX_CHARS` | `4000` | Maximum characters sampled per chunk for language detection |
| `VECTOR_BACKEND` | `chromadb` | Vector store (`chromadb` or `zvec`) |
| `CHROMA_PATH` | `./data/chroma` | ChromaDB persistence directory |
| `CHROMA_COLLECTION` | `alcove_docs` | Collection name |
| `CHUNK_SIZE` | `1000` | Characters per chunk |
| `CHUNK_OVERLAP` | `150` | Overlap between chunks |
| `RAW_DIR` | `data/raw` | Input directory for ingestion |

`ALCOVE_LANGUAGE_OLLAMA_BASE_URL` deliberately falls back to `OLLAMA_BASE_URL`
so embedding and language detection can share one local Ollama host. Set
`ALCOVE_LANGUAGE_OLLAMA_BASE_URL` explicitly when the language detector should
use a different Ollama instance than `EMBEDDER=ollama`.

## Docker

```bash
docker compose up -d --build
```

Port 8000 is exposed; the `/health` endpoint signals readiness.

## Backup

Back up `data/raw`, `data/processed`, and `data/chroma` (or `data/zvec` if using the zvec backend). These directories contain everything Alcove needs to reconstruct the index.

## Running tests

```bash
pip install alcove-search[dev]
pytest
```

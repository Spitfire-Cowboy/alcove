# Architecture

The README describes three stages: ingest, index, query. They are independent modules that operate over local files only. Each can be swapped out entirely via the plugin system without touching the others.

## Pipeline

Ingest discovers files in `data/raw/**`, extracts text using format-specific extractors, and chunks the result into `data/processed/chunks.jsonl`. Index reads those chunks, computes embeddings, and writes embeddings plus metadata to a local vector store. Query retrieves results via CLI or a built-in FastAPI web service. Data flows left to right with no backpressure; each stage is silent on disk until the next stage reads it.

```
data/raw/*  →  data/processed/chunks.jsonl  →  vector store  →  query responses
```

## Supported formats

| Format | Extension | Dependency |
|--------|-----------|------------|
| Plain text | `.txt` | — |
| PDF | `.pdf` | pypdf |
| EPUB | `.epub` | ebooklib (optional) |
| HTML | `.html`, `.htm` | beautifulsoup4 |
| Markdown | `.md` | — |
| reStructuredText | `.rst` | — |
| CSV | `.csv` | — |
| TSV | `.tsv` | — |
| JSON | `.json` | — |
| JSONL | `.jsonl` | — |
| DOCX | `.docx` | python-docx (optional) |

## Embedders

| Name | Env value | Description |
|------|-----------|-------------|
| Hash (default) | `EMBEDDER=hash` | Deterministic SHA-256 hash; offline, zero download, good for smoke tests |
| Sentence Transformers | `EMBEDDER=sentence-transformers` | Real semantic search via `all-MiniLM-L6-v2` (~80 MB model downloaded on first use) |

Set the embedder with the `EMBEDDER` environment variable. Custom embedders can be installed as plugins.

## Vector backends

| Name | Env value | Dependency |
|------|-----------|------------|
| ChromaDB (default) | `VECTOR_BACKEND=chromadb` | chromadb (included) |
| zvec | `VECTOR_BACKEND=zvec` | zvec (optional) |

Set the backend with the `VECTOR_BACKEND` environment variable.

## Plugin system

Custom extractors, embedders, and vector backends plug in via Python entry points. Alcove discovers plugins at startup and merges them with builtins; plugins take precedence in name collisions.

| Group | Purpose | Example entry point |
|-------|---------|---------------------|
| `alcove.extractors` | Add file format support | `rtf = my_plugin:extract_rtf` |
| `alcove.backends` | Add vector store backends | `pinecone = my_plugin:PineconeBackend` |
| `alcove.embedders` | Add embedding models | `openai = my_plugin:OpenAIEmbedder` |

To create a plugin, add an `[project.entry-points]` section in your package's `pyproject.toml`:

```toml
[project.entry-points."alcove.extractors"]
rtf = "my_plugin:extract_rtf"
```

## Boundary

Operator owns host and storage. The system makes no outbound network calls by default; sentence-transformers downloads its model once on first use only. Telemetry is disabled by default. This boundary keeps the system local-first and under operator control.

## Tradeoffs

Hash embedder is the default because it requires zero downloads and runs offline; swap to sentence-transformers if semantic quality matters more than speed-to-demo. ChromaDB is chosen for broad compatibility; zvec for lighter footprint. The implementation prioritizes simplicity over optimization, trading some throughput for faster iteration and easier debugging.

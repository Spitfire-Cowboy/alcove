# Architecture

Alcove is a local-first retrieval pipeline. It has three independent stages: ingest, index, and query. Each stage reads from local disk, writes to local disk, and can be run again without changing the others.

```text
data/raw/* -> data/processed/chunks.jsonl -> vector store -> query responses
```

Alcove does not generate text. It returns chunks that already exist in the indexed corpus.

## Shipped pipeline

| Stage | Module | Input | Output |
|-------|--------|-------|--------|
| Ingest | `alcove/ingest` | Files under a local directory | `data/processed/chunks.jsonl` |
| Index | `alcove/index` | Chunk JSONL | Local vector store |
| Query | `alcove/query` | Query text and optional filters | Matching chunks plus metadata |

The CLI in `alcove/cli.py` wires these modules into commands such as `alcove ingest`, `alcove search`, `alcove collections`, `alcove status`, and `alcove serve`.

## Ingest

Ingest discovers files recursively and extracts plain text using extension-specific extractors. The output is newline-delimited JSON, so the indexer can be rerun without re-reading the source files.

Supported formats:

| Format | Extension | Dependency |
|--------|-----------|------------|
| Plain text | `.txt` | none |
| PDF | `.pdf` | pypdf |
| EPUB | `.epub` | ebooklib (optional extra) |
| HTML | `.html`, `.htm` | beautifulsoup4 |
| Markdown | `.md` | none |
| reStructuredText | `.rst` | none |
| CSV | `.csv` | none |
| TSV | `.tsv` | none |
| JSON | `.json` | none |
| JSONL | `.jsonl` | none |
| DOCX | `.docx` | python-docx (optional extra) |
| PPTX | `.pptx` | python-pptx (optional extra) |

## Index

Index reads chunks, embeds their text, and writes vectors plus metadata to a local backend. Metadata includes source and collection fields used by result rendering and collection filtering.

### Embedders

| Name | Env value | Description |
|------|-----------|-------------|
| Hash (default) | `EMBEDDER=hash` | Deterministic SHA-256 vectors. Offline, zero download, useful for smoke tests and non-ML operation. |
| Sentence Transformers | `EMBEDDER=sentence-transformers` | Semantic embeddings via `all-MiniLM-L6-v2`; downloads the model on first use, then runs locally. |
| Ollama | `EMBEDDER=ollama` | Semantic embeddings via an operator-managed Ollama server; defaults to local loopback. |

### Vector backends

| Name | Env value | Dependency |
|------|-----------|------------|
| ChromaDB (default) | `VECTOR_BACKEND=chromadb` | chromadb |
| zvec | `VECTOR_BACKEND=zvec` | zvec optional extra |

ChromaDB telemetry is disabled. The storage paths and collection naming rules are documented in [Operations](OPERATIONS.md#environment-variables).

## Query

Query is available through the CLI and through the FastAPI app started by `alcove serve`.

Search modes:

| Mode | Behavior |
|------|----------|
| `semantic` | Embed the query and run vector similarity against the local backend. |
| `keyword` | Run BM25 over `data/processed/chunks.jsonl`. |
| `hybrid` | Merge semantic and keyword results. |

The API accepts collection filters. The web UI displays collection chips when more than one collection exists.

## Browse mode

Browse mode is a core, read-only view over indexed metadata. It does not inspect
raw corpus files directly and does not mutate the index. Backends expose stored
metadata through `iter_metadata_records()`, and `alcove/query/browse.py`
aggregates that metadata into source-document facets such as collection, file
type, author, year, and recent documents. Backends may also include stored chunk
text in internal `__document` fields and chunk IDs in `__chunk_id` fields so the
web UI can show document drill-down previews without reading raw files.

Backend plugins should implement `iter_metadata_records()` when they want the
core web UI's `/browse` page to show corpus facets. If a backend cannot enumerate
metadata records, browse mode falls back to an empty state while search remains
available.

## Plugin system

Plugins use Python entry points. Three extension groups are shipped:

| Group | Purpose | Example entry point |
|-------|---------|---------------------|
| `alcove.extractors` | Add file format support | `rtf = my_plugin:extract_rtf` |
| `alcove.backends` | Add vector store backends | `sqlite_vec = my_plugin:SQLiteVecBackend` |
| `alcove.embedders` | Add embedding models | `local_model = my_plugin:LocalEmbedder` |

To create a plugin, add an entry-point section to your package:

```toml
[project.entry-points."alcove.extractors"]
rtf = "my_plugin:extract_rtf"
```

Plugins are discovered at startup and merged with built-ins. If a plugin and a built-in use the same name, the plugin wins.

Plugins can change the trust boundary. A cloud embedder or hosted backend can send data off-machine if an operator installs and selects it. That is outside the default Alcove boundary and must be documented by the plugin.

## Boundary

The operator owns the host and the storage. Normal ingest, index, query, and serve operations use local disk. Explicit network use is limited to commands or options the operator selects, such as fetching the public seed corpus, downloading the optional sentence-transformers model on first use, or pointing `EMBEDDER=ollama` at an operator-managed Ollama endpoint. Ollama defaults to the local loopback interface. Telemetry is disabled, including ChromaDB's upstream telemetry.

Alcove does not include authentication or authorization. Keep the server bound to localhost unless a reverse proxy, network policy, or OS-level access control protects it.

See [Security](SECURITY.md) for the full security model.

## Release boundary

The published 0.4.0 package includes the STDIO MCP server, browse mode, Ollama embeddings, PPTX extraction, local signing helpers, runtime deployment controls, and desktop packaging preparation.

Manifest-based registry discovery, richer provenance workflows, streaming ingest, multilingual model-selection UX, and cross-modal indexing remain design or roadmap work unless a shipped CLI command, API endpoint, or module implements them. The status map lives in [Roadmap](ROADMAP.md#pending-feature-map).

## Tradeoffs

The hash embedder ships as the default because it requires zero downloads and works offline. The cost is that it produces deterministic but non-semantic vectors; use `sentence-transformers` for real semantic search quality.

ChromaDB is the default backend for compatibility and ecosystem support. zvec is available for operators who want a lighter optional backend.

The implementation is deliberately thin. The v0.4.0 goal is a correct local retrieval pipeline with clear extension points, not a managed platform.

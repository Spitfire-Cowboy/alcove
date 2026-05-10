<img src="docs/assets/logo.svg" alt="Alcove" height="56">

<p>
  <a href="https://github.com/Spitfire-Cowboy/alcove/actions/workflows/ci.yml"><img src="https://github.com/Spitfire-Cowboy/alcove/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://codecov.io/gh/Spitfire-Cowboy/alcove"><img src="https://codecov.io/gh/Spitfire-Cowboy/alcove/graph/badge.svg" alt="Coverage"></a>
  <a href="https://pypi.org/project/alcove-search/"><img src="https://img.shields.io/pypi/v/alcove-search.svg" alt="PyPI"></a>
  <a href="https://pypi.org/project/alcove-search/"><img src="https://img.shields.io/pypi/pyversions/alcove-search.svg" alt="Python Versions"></a>
  <a href="https://github.com/Spitfire-Cowboy/alcove/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="License"></a>
</p>

**Local-first document retrieval. Your data never leaves your disk.**

---

Alcove is search infrastructure for documents you keep on your own machine. It ingests a local directory, extracts text, chunks it, writes a local index, and returns matching chunks through a CLI or local web/API server.

It is retrieval, not generation. Alcove does not summarize, answer questions, host models, or invent text. Search results are excerpts from the indexed corpus.

**[See it in 30 seconds](https://spitfire-cowboy.github.io/alcove/demo.html)** · [Why Alcove?](WHY.md)

## What ships today

Alcove v0.4.0 ships a working local pipeline:

- Recursive ingest for PDF, EPUB, HTML, Markdown, CSV, JSON, JSONL, DOCX, PPTX, RST, TSV, and plain text.
- Local indexing with ChromaDB by default, with zvec available as an optional backend.
- A deterministic hash embedder by default, plus opt-in sentence-transformers and Ollama embedders for real semantic similarity.
- CLI search and a FastAPI web service with search, upload, health, collection-list, and browse endpoints.
- Semantic, keyword (BM25), and hybrid search modes.
- Named collection metadata and collection filtering.
- STDIO MCP retrieval tools for local index search and collection listing.
- Local signing helpers and index signing tooling for provenance checks.
- Python entry-point plugins for extractors, embedders, and vector backends.

The roadmap includes richer manifests, provenance workflows, streaming ingest, and more plugin categories. Those are not documented here as shipped behavior; see [Roadmap](docs/ROADMAP.md) for the pending-feature map.

## How it works

Three stages. Each stage reads from local disk and writes to local disk, so it can be re-run independently.

```text
data/raw/* -> data/processed/chunks.jsonl -> vector store -> query responses
```

**Ingest** discovers files recursively and extracts text with format-specific extractors.

**Index** embeds chunks and writes vectors plus metadata to a local vector store.

**Query** retrieves matching chunks through the CLI or local API/web UI.

See [Architecture](docs/ARCHITECTURE.md) for module boundaries and extension points.

## Quick start

```bash
pip install alcove-search[semantic]
alcove seed-demo
alcove serve
```

Open `http://localhost:8000`.

The `[semantic]` extra installs sentence-transformers. The first semantic run downloads `all-MiniLM-L6-v2` once, then runs locally. For zero-download installs:

```bash
pip install alcove-search
```

The base package uses the hash embedder. It is deterministic, offline, and useful for smoke tests or operators who do not want ML in the pipeline. It is not a semantic search model.

<details>
<summary>Install extras</summary>

| Extra | Install command | What it adds |
|-------|----------------|--------------|
| Semantic search | `pip install alcove-search[semantic]` | Real vector similarity via sentence-transformers |
| EPUB support | `pip install alcove-search[epub]` | `.epub` ingestion |
| DOCX support | `pip install alcove-search[docx]` | `.docx` ingestion |
| zvec backend | `pip install alcove-search[zvec]` | Optional zvec vector store |
| PPTX support | `pip install alcove-search[pptx]` | `.pptx` ingestion |
| Everything | `pip install alcove-search[semantic,epub,docx,pptx,zvec]` | All optional runtime features |

</details>

<table><tr>
<td><a href="docs/assets/web-ui-dark.png"><img src="docs/assets/web-ui-dark.png" alt="Alcove UI, dark theme" width="420"></a></td>
<td><a href="docs/assets/web-ui-light.png"><img src="docs/assets/web-ui-light.png" alt="Alcove UI, light theme" width="420"></a></td>
</tr></table>

## Trust model

Local disk only for normal ingest, index, query, and serve operations. No telemetry. No account creation. ChromaDB's upstream telemetry is disabled.

Network use is explicit: `alcove seed-demo` fetches the public sample corpus, and sentence-transformers downloads its model on first use. After that, embedding runs locally.

Alcove does not require authentication. The local API is open to anyone who can reach the port, so keep it bound to `127.0.0.1` unless you put authentication in front of it. See [Operations](docs/OPERATIONS.md) and [Security](docs/SECURITY.md).

## Common commands

```bash
alcove ingest /path/to/files
alcove search "phrase to find" --mode hybrid --k 5
alcove collections
alcove status
alcove serve --host 127.0.0.1 --port 8000
```

## Documentation

[Why Alcove?](WHY.md) · [Architecture](docs/ARCHITECTURE.md) · [Operations](docs/OPERATIONS.md) · [Security](docs/SECURITY.md) · [Desktop Packaging](docs/DESKTOP.md) · [Seed Corpus](docs/SEED_CORPUS.md) · [Roadmap](docs/ROADMAP.md) · [Plugin Ideas](docs/PLUGINS.md) · [Accessibility](ACCESSIBILITY.md)

## License

[Apache 2.0](LICENSE)

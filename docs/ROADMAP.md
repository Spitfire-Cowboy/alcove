# Roadmap

This roadmap separates the published package from planned design work. Public docs should not describe roadmap items as available in a package release until they are tagged and published.

## Current package release (v0.4.0)

The published 0.4.0 package ships a working local retrieval pipeline:

- Ingest, index, and query stages over local disk.
- Twelve document formats: PDF, EPUB, HTML, Markdown, CSV, JSON, JSONL, DOCX, PPTX, RST, TSV, and plain text.
- Hash, sentence-transformers, and Ollama embedders.
- ChromaDB and zvec vector backends.
- CLI search, status, collection listing, plugin listing, and seed-demo commands.
- FastAPI web UI/API with search, upload ingest, health, collection, and browse endpoints.
- Semantic, keyword, and hybrid search modes.
- Named collection metadata and collection filtering.
- STDIO MCP retrieval tools for local search and collection listing.
- Local signing helpers and index signing tooling.
- Runtime deployment controls.
- Release packaging checks.
- Desktop packaging preparation docs and guardrails; no supported desktop bundle ships yet.
- Python entry-point plugins for extractors, embedders, and vector backends.
- Docker runtime, CI, accessibility improvements, and Apache 2.0 licensing.

See [the 0.4.0 release notes](RELEASE_0_4_0_PLAN.md) for scope details and release verification.

## Pending feature map

These buckets track design and future work without tying public docs to private branch names, hostnames, or PR numbers.

| Area | Status | Public wording until shipped |
|------|--------|------------------------------|
| Manifest and registry discovery | Draft design | Entry-point plugins ship today. `alcove.json`, remote registries, and index registry discovery are design notes. |
| Provenance layer | Partial foundation | Source and collection metadata ship today. Rich provenance manifests and compliance workflows are planned. |
| Streaming ingest | Planned | Ingest is batch-oriented today. Watch/re-index loops are roadmap work. |
| Cross-modal indexing | Plugin candidate | Text document extraction ships today. Audio, image, video, OCR, and transcription belong in plugins or future releases. |
| Multilingual model selection | Exploratory | Operators can choose sentence-transformers through `EMBEDDER`. Per-model multilingual CLI flags and automatic prefix handling are not a shipped public contract. |
| Richer plugin lifecycle | Planned | Extractor, embedder, and backend entry points ship today. Lifecycle hooks, query transforms, and custom ranking are roadmap work. |
| Federation | Research | A single local instance ships today. Multi-instance query surfaces without raw-data sharing remain long-term work. |

## Near-term

**Desktop packaging preparation.** Keep Briefcase metadata public and minimal, document that no desktop app bundle ships yet, and add checks that prevent accidental private paths, hostnames, or release claims from entering packaging files. The first milestone is packaging readiness, not an app-shaped wrapper around an unfinished experience.

**More file formats.** RTF, ODT, and XLSX are good extractor-plugin candidates. PPTX support ships in 0.4.0. The current plugin API already supports third-party extractors.

**Browse mode.** Browse mode ships in 0.4.0. Next steps are deeper directory-aware browsing while keeping the surface retrieval-only.

**Local model hooks.** Ollama embedding support ships in 0.4.0. Near-term work is documentation polish and model-specific guidance, not hosted inference or generated answers.

**MCP endpoint.** The STDIO MCP retrieval server ships in 0.4.0. Exposing any endpoint changes the security surface; authentication remains the operator's responsibility.

**Release packaging hygiene.** Public releases now include checks for package metadata, release automation, and Homebrew formula safety. PyPI remains the supported public install channel; Homebrew packaging stays deferred until the formula can be generated with public URLs, Apache-2.0 metadata, real release hashes, and vendored Python resources.

**Streaming ingest.** The shipped pipeline is batch-oriented: run ingest, then index. A watcher can keep the index current without manual reruns.

**Provenance improvements.** Source and collection metadata and local signing helpers ship in 0.4.0; richer provenance manifests and compliance workflows remain planned work.

**Runtime deployment controls.** Feature flags and deployment metadata ship in 0.4.0. They should stay explicit, testable, and file-backed so public builds, local installs, and future demos do not drift through ad hoc environment tweaks.

## Mid-term

**Cross-modal indexing.** Audio transcription, image OCR, and video keyframe extraction fit the same architecture: extractors produce text chunks, embedders index those chunks, and query returns matching source excerpts.

**Relevance as memory, not just distance.** Vector similarity is a starting point. Future ranking can consider recency, frequency of access, and corpus familiarity while preserving the retrieval-only boundary.

**Richer plugin API.** Lifecycle hooks, query-time transformations, custom ranking, and plugin metadata can extend the current entry-point surface.

## Long-term

**Federation.** Multiple Alcove instances could share a query surface without sharing raw data. Each node would still own its corpus and decide what to expose.

**Desktop application.** A native app for people who should not need a terminal to search their own files. This is packaging and distribution work, not architecture work; the core stays the same. Current status is documented in [Desktop Packaging](DESKTOP.md): Alcove has preparation docs and checks, but no supported desktop bundle yet.

## Plugin candidates

The shipped plugin API exposes three extension points: extractors (`alcove.extractors`), embedders (`alcove.embedders`), and vector backends (`alcove.backends`). Candidate plugins should document whether they preserve Alcove's local-first boundary.

### Extractor candidates

| Candidate | Library | Notes |
|-----------|---------|-------|
| RTF | `striprtf` | Legacy text documents. |
| ODT / ODP / ODS | `odfpy` | OpenDocument text, slides, and sheets. |
| XLSX | `openpyxl` | Spreadsheet text and tabular metadata. |
| Audio transcription | `faster-whisper` | Local transcription when models are installed locally. |
| Image OCR | `pytesseract` or local vision models | Extract searchable text from images. |

### Embedder candidates

| Candidate | Boundary |
|-----------|----------|
| Local sentence-transformers variants | Local after first model download. |
| Ollama or other local model servers | Local if the model server is local. |
| MLX on Apple Silicon | Local hardware acceleration. |
| Cloud embedding APIs | Break the default local-only boundary; must be opt-in and documented by the plugin. |

### Backend candidates

| Candidate | Boundary |
|-----------|----------|
| SQLite-vec | Local single-file index. |
| Qdrant local mode | Local if configured for local storage. |
| Remote vector databases | Break the default local-only boundary; must be opt-in and documented by the plugin. |

## Out of scope

Alcove will not become a hosted service. There is no plan for mandatory cloud storage, account creation, telemetry, or a managed SaaS offering. If an operator chooses cloud plugins or exposes a local API, that is a deployment decision outside the default Alcove runtime.

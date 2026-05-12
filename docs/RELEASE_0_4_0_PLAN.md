# Alcove 0.4.0 Release Notes

Status: release-prep complete. This document records the public 0.4.0 package scope; tagging and publishing still happen after the release PR is merged.

Target tag: `v0.4.0`.

Current package version: 0.4.0.

## Release Scope

0.4.0 is a feature-batch release made from reviewed and merged public work on `main`.

Included behavior:

- Browse mode and read-only document drill-down previews.
- STDIO MCP retrieval tools for local search and collection listing.
- Ollama embeddings through `EMBEDDER=ollama`.
- PPTX text extraction.
- Local Ed25519 signing helpers and index signing tooling.
- Runtime deployment controls.
- Release packaging checks for public metadata, release workflows, and Homebrew formula safety.
- Desktop packaging preparation docs and guardrails; no desktop app bundle ships yet.
- Public documentation cleanup that separates released behavior from draft designs.

Deferred or still exploratory:

- Manifest and registry discovery.
- Rich provenance manifests and compliance workflows.
- Streaming ingest.
- Cross-modal indexing.
- Multilingual model-selection CLI flags and automatic multilingual-E5 prefix handling.
- Federation.

## Release Checklist

Before tagging:

- [ ] Confirm `main` passes CI for supported Python versions.
- [ ] Run focused local tests for changed surfaces.
- [ ] Confirm package metadata points to the public project URLs.
- [ ] Confirm no release docs include private hostnames, private repository references, personal filesystem paths, or PII.
- [ ] Confirm `pyproject.toml`, `alcove/__init__.py`, `CHANGELOG.md`, and `docs/ROADMAP.md` all agree on 0.4.0.

At release time:

- [ ] Merge the release PR.
- [ ] Tag `v0.4.0` only after tests and release notes are final.
- [ ] Push the tag to trigger GitHub Release and PyPI publish workflows.
- [ ] Verify the published artifact and public release notes.

After release:

- [ ] Sanity-check install from PyPI.
- [ ] Open follow-up issues for deferred roadmap items.

## Public-Safety Notes

The release decision should be reproducible from public project state. Do not include private branch names, private repository slugs, operator-specific directories, internal deployment hosts, credentials, access tokens, customer names, or incident details in release notes.

If a private operational detail is needed to complete a release, keep it outside checked-in public documentation and translate the public-facing release note into project behavior.

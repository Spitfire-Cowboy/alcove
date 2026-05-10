# Changelog

All notable changes to alcove-search.

## [Unreleased]

## [0.4.0] - 2026-05-12

- Consolidate public README, architecture, operations, and roadmap docs around the published package and current unreleased main-branch scope.
- Add a pending-feature map so draft manifest, provenance, streaming ingest, multilingual, and cross-modal work is not presented as already shipped.
- Clarify install, trust-boundary, API, collection, backup, and docs hygiene guidance.
- Document desktop packaging status and guardrails without claiming a supported app bundle.
- Add focused checks for public-safe Briefcase metadata and local-first desktop packaging docs.
- Add read-only browse document detail pages with stable IDs and chunk previews.
- Add a read-only browse mode for recent indexed documents, collections, file types, authors, and years.
- Add release packaging checks for public metadata, release workflows, and Homebrew formula safety.
- Add public 0.4.0 release notes and bump package metadata to 0.4.0.
- Add `EMBEDDER=ollama` for local Ollama embedding models.
- Add built-in PPTX text extraction and pipeline dispatch.
- Add local Ed25519 signing helpers and a standalone index signing tool for provenance checks.
- Add a STDIO Model Context Protocol server for querying local Alcove indexes.
- Add runtime configuration feature flags for environment and config-file controlled deployments.

## [0.3.0] - 2026-03-07

- Add theme toggle, fix WCAG AA contrast, update accessibility docs
- Use relative paths for README images, move a11y to docs list
- Add WCAG AA accessibility improvements
- Fix README image paths for PyPI rendering
- Add project tagline to README
- Rewrite docs, fix embedder bug, add optional extras to README
- Switch to Apache 2.0, first-run welcome banner, bump to 0.3.0
- Show welcome banner when index is empty

## [0.2.0] - 2026-03-06

- Fix version to 0.2.0, clean up stale references
- Alcove v0.2.0 — local-first document search

# Alcove 0.5.0 Release Notes

Status: release-prep complete. This document records the public 0.5.0 package
scope; tagging and publishing happen only after the release PR is merged.

Target tag: `v0.5.0`.

Current package version: 0.5.0.

## Release Scope

0.5.0 is a feature-batch release made from reviewed and merged public work on
`main` since v0.4.0.

Included behavior:

- RTF, ODT, and XLSX text extraction, bringing the built-in document-format
  count to fifteen.
- Source metadata preservation through JSONL ingest and indexing.
- Machine-readable capability discovery at the documented capability routes.
- Plugin discovery filters, plugin detail surfaces, and metadata enricher entry
  points with explicit local-code trust boundaries.
- Batched ChromaDB upserts for larger indexes.
- Status output that identifies the active index target and network mode.
- Dependency-integrity verification for installed runtime packages.
- Cryptography 50.x compatibility, including the patched line for
  CVE-2026-69247.
- Public sponsorship and documentation-site analytics updates.

Deferred or still exploratory:

- Manifest and remote-registry discovery.
- Rich provenance manifests and compliance workflows.
- Streaming ingest.
- Cross-modal indexing.
- Multilingual model-selection CLI flags and automatic multilingual-E5 prefix
  handling.
- Federation.

## Release Checklist

Before tagging:

- [ ] Confirm `main` passes CI for supported Python versions.
- [ ] Run focused local tests for changed release and packaging surfaces.
- [ ] Confirm package metadata points to the public project URLs.
- [ ] Confirm release docs contain no private hostnames, private repository
  references, personal filesystem paths, credentials, or PII.
- [ ] Confirm `pyproject.toml`, `alcove/__init__.py`, `CHANGELOG.md`, and
  `docs/ROADMAP.md` all agree on 0.5.0.

At release time:

- [ ] Merge the release PR.
- [ ] Tag `v0.5.0` only after tests and release notes are final.
- [ ] Push the tag to trigger GitHub Release and PyPI publish workflows.
- [ ] Verify the published artifact and public release notes.

After release:

- [ ] Sanity-check installation from PyPI.
- [ ] Refresh the `alcove-dux` optional integration lock and verify that its
  cryptography alert closes.
- [ ] Open follow-up issues for deferred roadmap items.

## Public-Safety Notes

The release decision should be reproducible from public project state. Do not
include private branch names, private repository slugs, operator-specific
directories, internal deployment hosts, credentials, access tokens, customer
names, or incident details in release notes.

If a private operational detail is needed to complete a release, keep it
outside checked-in public documentation and translate the public-facing note
into project behavior.

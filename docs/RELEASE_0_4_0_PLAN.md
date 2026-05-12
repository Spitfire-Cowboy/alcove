# Alcove 0.4.0 Release Plan

Status: planning only. This document does not ship features, merge feature PRs, bump package metadata, create a tag, or publish artifacts.

Target: 0.4.0 feature-batch release.

Current package version: 0.3.0 until the release commit.

## Scope Decision

0.4.0 should be decided as a reviewed feature batch, not as a rolling collection of branch state. A feature belongs in 0.4.0 only after its PR has been reviewed, merged, tested on `main`, and documented as shipped behavior.

Candidate areas to evaluate:

- Retrieval surface improvements that preserve Alcove's retrieval-only contract.
- Ingest and extractor improvements that keep data local by default.
- Plugin-system improvements with clear entry-point compatibility notes.
- Web or CLI usability improvements that are covered by focused tests.
- Documentation updates that describe shipped behavior without promising unmerged work.

Explicitly out of scope for this planning branch:

- Version bump to 0.4.0 or 1.0.0.
- Release tag creation.
- Publishing to PyPI or package registries.
- Private deployment notes, internal hostnames, private repository names, or operator-specific paths.

## PR Review Sequence

Use this sequence before cutting the release:

1. Review dependency and maintenance PRs first so feature branches are evaluated against current dependencies.
2. Review data-model, manifest, or plugin contract PRs before UI or documentation PRs that depend on those contracts.
3. Review ingest and indexing changes before query/API changes that expose their output.
4. Review user-facing CLI, API, and web changes after the underlying pipeline behavior is stable.
5. Review documentation and changelog updates last, using only merged and verified behavior.

Each accepted PR should leave behind enough evidence for release notes: tests run, public docs touched, and any compatibility notes. Deferred PRs should be listed as deferred follow-up work, not as 0.4.0 features.

## Release Checklist

Before release scope is approved:

- [ ] Confirm every candidate feature PR is merged or explicitly deferred.
- [ ] Confirm `main` passes CI for supported Python versions.
- [ ] Run focused local tests for changed surfaces.
- [ ] Confirm package metadata still points to the public project URLs.
- [ ] Confirm no release docs include private hostnames, private repository references, personal filesystem paths, or PII.
- [ ] Rewrite this plan's candidate language into final release notes for only merged behavior.

At release time:

- [ ] Bump package metadata from 0.3.0 to 0.4.0 in the release commit.
- [ ] Move the 0.4.0 changelog entry from planned scope to dated shipped scope.
- [ ] Tag `v0.4.0` only after tests and release notes are final.
- [ ] Verify the published artifact and public release notes.

After release:

- [ ] Update `docs/ROADMAP.md` so 0.4.0 is described as current shipped behavior.
- [ ] Open follow-up issues for deferred PRs and incomplete roadmap items.
- [ ] Remove or archive this planning checklist if it no longer reflects the public release state.

## Public-Safety Notes

The release decision should be reproducible from public project state. Do not include private branch names, private repository slugs, operator-specific directories, internal deployment hosts, credentials, access tokens, customer names, or incident details in release notes.

If a private operational detail is needed to complete a release, keep it outside checked-in public documentation and translate the public-facing release note into project behavior.

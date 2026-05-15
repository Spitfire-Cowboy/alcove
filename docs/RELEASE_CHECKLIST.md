# Public Release Checklist

Use this checklist for public Alcove releases.

## Pre-release

1. Confirm open PR queue status and merge/close dependency bumps with rationale.
2. Confirm `main` is green in CI for supported Python versions.
3. Update `CHANGELOG.md` with user-visible changes and scope boundaries.
4. Confirm docs avoid internal-only deployment details and private repo references.
5. Verify package metadata and public links point to `Spitfire-Cowboy/alcove`.
6. Run `python3 scripts/check_release_packaging.py`.

For a feature-batch release such as 0.4.0, start from the public [0.4.0 release notes](RELEASE_0_4_0_PLAN.md). Keep candidate work separate from shipped behavior until the release commit is ready.

## Release

1. Create release commit and tag: `vX.Y.Z`.
2. Push tag to trigger release automation:
   - `.github/workflows/release.yml`
   - `.github/workflows/publish.yml`
3. Verify GitHub Release notes generated successfully.
4. Verify PyPI publish completed successfully.

## Post-release

1. Sanity-check install path from PyPI.
2. Confirm docs site/demo links are still valid.
3. Confirm release notes and roadmap language match shipped behavior.
4. Open follow-up issues for deferred items.

## Packaging notes

- PyPI is the supported public package channel.
- Do not add a Homebrew formula until the formula has public URLs, Apache-2.0 metadata, a real release SHA, and vendored Python resources suitable for offline Homebrew installs.
- If a `Formula/alcove.rb` file is added, `scripts/check_release_packaging.py` must pass before release.

## Public-safety guardrails

- Do not include internal hostnames, private filesystem paths, or customer-specific instructions.
- Keep scope and acceptance criteria explicit in issue/PR tracking.
- Avoid release claims that are not already shipped and verified.

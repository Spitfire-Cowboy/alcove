# Public Release Checklist

Use this checklist for public Alcove releases.

## Pre-release

1. Confirm open PR queue status and merge/close dependency bumps with rationale.
2. Confirm `main` is green in CI for supported Python versions.
3. Update `CHANGELOG.md` with user-visible changes and scope boundaries.
4. Confirm docs avoid internal-only deployment details and private repo references.
5. Verify package metadata and public links point to `Spitfire-Cowboy/alcove`.
6. If preparing Homebrew packaging, generate the formula only after the public release artifact exists and use its real SHA-256.

## Release

1. Create release commit and tag: `vX.Y.Z`.
2. Push tag to trigger release automation:
   - `.github/workflows/release.yml`
   - `.github/workflows/publish.yml`
3. Verify GitHub Release notes generated successfully.
4. Verify PyPI publish completed successfully.
5. If a Homebrew formula is part of this release, run `python3 scripts/generate_homebrew_formula.py --check <formula>` before publishing it.

## Post-release

1. Sanity-check install path from PyPI.
2. Confirm docs site/demo links are still valid.
3. Confirm release notes and roadmap language match shipped behavior.
4. Open follow-up issues for deferred items.
5. Do not add Homebrew install instructions until `brew install` succeeds from the public formula.

## Public-safety guardrails

- Do not include internal hostnames, private filesystem paths, or customer-specific instructions.
- Keep scope and acceptance criteria explicit in issue/PR tracking.
- Avoid release claims that are not already shipped and verified.
- Never publish or document a Homebrew formula with placeholder checksums.

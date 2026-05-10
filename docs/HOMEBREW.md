# Homebrew Packaging

Alcove does not currently ship an installable Homebrew formula.

This repository includes a public-safe formula template and generator so release work can prepare a formula only after a real release artifact exists. Do not publish a generated formula with placeholder checksums, private repository URLs, or local filesystem paths.

## Generate a Formula

1. Publish the Alcove release artifact.
2. Download or inspect the released sdist checksum from the public artifact source.
3. Generate the formula with the real checksum:

```bash
python3 scripts/generate_homebrew_formula.py \
  --version 0.3.0 \
  --sha256 <real-64-character-sdist-sha256> \
  --output Formula/alcove-search.rb
```

4. Validate the generated formula:

```bash
python3 scripts/generate_homebrew_formula.py --check Formula/alcove-search.rb
```

The template lives at `packaging/homebrew/alcove-search.rb.template`. It is intentionally not a live formula because the repository should not claim Homebrew support until the formula is generated from a real public release and tested through Homebrew.

## Safety Rules

- Use only public release artifact URLs.
- Use only the real SHA-256 for that exact artifact.
- Do not commit generated formulas with placeholder values.
- Do not reference private repositories, internal hostnames, local user paths, or deployment details.
- Do not advertise Homebrew installation until `brew install` succeeds from the published formula.

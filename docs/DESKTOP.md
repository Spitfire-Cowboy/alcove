# Desktop Packaging

Alcove does not currently ship a desktop application bundle.

The repository keeps minimal Briefcase metadata in `pyproject.toml` so packaging work has a public project identity and canonical source URL. It deliberately does not define a `tool.briefcase.app.*` target yet. Until a real desktop shell exists, `briefcase build`, `briefcase run`, and platform installer generation are not supported release paths.

## Current Status

- Supported distribution: Python package and source checkout.
- Supported user interfaces: CLI and local FastAPI web UI.
- Desktop app status: packaging preparation only.
- Local-first boundary: unchanged. Ingested documents, processed chunks, embeddings, and vector stores stay on the operator's disk.

## Packaging Principles

Desktop packaging must preserve the existing architecture:

- The app shell may launch or supervise Alcove, but the ingest, index, and query pipeline remains the source of truth.
- The default runtime must not add telemetry, account creation, hosted storage, or background network calls.
- The hash embedder remains available as a zero-download mode. Sentence-transformers remains opt-in and may download its model on first use.
- Platform packaging must not include private hostnames, deployment paths, private repository references, local user paths, signing identities, or personal data.

## Before Adding a Briefcase App Target

A future `tool.briefcase.app.alcove` section should not be added until these pieces exist:

1. A real desktop entry point that starts a useful local experience.
2. Explicit platform notes for macOS, Windows, and Linux.
3. Tests that verify the desktop entry point does not change Alcove's local-first defaults.
4. A release checklist section for app signing, notarization, installer contents, and public artifact naming.
5. Manual verification notes for a clean machine or disposable user account.

Until then, the honest state is preparation, not a half-working app bundle.

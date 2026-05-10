# Mirrulations Public Data Loader

Mirrulations publishes public Regulations.gov data in a shape that is useful for testing Alcove against real regulatory records. Alcove supports local Mirrulations `text-*` directories as a public-data loader.

The loader reads only files already present on local disk. It does not download data, call hosted services, or require credentials.

## Supported Inputs

Point `alcove mirrulations-demo` at a Mirrulations root, agency directory, docket directory, or direct `text-<docket>` directory. It normalizes:

- `docket/*.json` into one retrieval record per docket
- `documents/*.json` plus matching `documents/*_content.htm` into one retrieval record per document
- `comments/*.json` into one retrieval record per public comment
- `documents_extracted_text/*/*.txt` and `comments_extracted_text/*/*.txt` into one retrieval record per extracted attachment text file

Binary attachment files are out of scope for this loader. If you want attachment content indexed, provide extracted `.txt` files in the Mirrulations text tree.

## Usage

Prepare a local text-only Mirrulations subset outside Alcove, then index it:

```bash
alcove mirrulations-demo data/raw/mirrulations --agency EPA --jsonl-out data/processed/mirrulations.jsonl
```

By default, records are tagged with the `mirrulations_docs` collection metadata value:

```bash
alcove search "power plant emissions limits" --mode hybrid
```

Use `--collection` to tag records for a different collection-aware workflow:

```bash
alcove mirrulations-demo data/raw/mirrulations --collection regulatory_test_docs
```

## Notes

- Field coverage varies by docket, so the loader skips records that do not contain searchable text.
- Agency filters are case-insensitive and can be repeated.
- Source metadata points to local file paths and public Regulations.gov URLs derived from docket, document, and comment identifiers.

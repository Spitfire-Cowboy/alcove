# Language & Linguistics Plugins

## Multilingual Search

**Library:** `sentence-transformers` (multilingual-e5 model)

Cross-lingual search works out of the box with multilingual-e5. A query in English can retrieve documents in Spanish, French, German, or any other language the model covers. No per-language configuration required.

Documented community deployments include English, Spanish, Latin, French, German, Samoan, Ojibwe, and Tongan. The model covers 100+ languages to varying degrees of quality.

## Endangered and Minority Languages

Alcove is a reasonable fit for endangered language preservation work. The relevant stack:

- Audio transcription via `faster-whisper` for elder recordings and oral histories
- OCR for scanned curriculum materials and handwritten documents
- Multilingual embeddings for cross-document search where training data exists

The deployment model matters here. An institution running Alcove on its own hardware keeps data inside the community. No recordings, transcripts, or documents go to an external service. This is a meaningful difference from cloud-based alternatives for communities where data sovereignty is a concern.

Grant paths worth knowing: IMLS, Administration for Native Americans (ANA) Language Preservation Program, NEH Digital Humanities.

## Constructed Languages

D'ni, Klingon, Na'vi, Tolkien's languages (Quenya, Sindarin), and similar constructed languages are too sparse for semantic embeddings to be useful. The training data does not exist at the scale these models require.

The practical approach: use metadata-only retrieval. Filter by language tag, canon status (official vs. fan-created), and source. Full-text search over the corpus works for exact or near-exact matches. Skip the vector index for these collections.

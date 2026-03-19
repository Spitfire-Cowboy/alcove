# Plugin Ideas & Domain Recipes

This document catalogs potential Alcove plugins and the domain use cases that motivate them. Each entry is a recipe: a corpus type, the plugin that gets data into the index, and what you can do once it's there.

These are ideas and directions — not all of them are implemented. The plugin system is open; if something here resonates, it can be built as a standalone pip package and registered against the `alcove.extractors`, `alcove.embedders`, or `alcove.backends` entry-point groups. See [ARCHITECTURE.md](ARCHITECTURE.md#plugin-system) for the interface contract.

---

## Audio & Acoustic Data

### Speech transcription
**Plugin type:** extractor
**Library:** `faster-whisper`, `whisper`
**Formats:** `.wav`, `.mp3`, `.m4a`, `.flac`, `.mp4`, `.ogg`

Transcribe spoken audio locally with OpenAI Whisper. The extractor runs inference on-device, emits time-coded text chunks, and indexes them like any other document. Oral histories, interview recordings, lecture audio, field notes dictated into a voice recorder — anything spoken becomes searchable text, with the original file as the provenance source. No audio leaves the machine.

Model size is configurable (`tiny` through `large-v3`); `base` is a reasonable default for most corpora.

### Bioacoustics & wildlife audio
**Plugin type:** extractor
**Libraries:** `birdnetlib` (wraps BirdNET-Analyzer), `opensoundscape`
**Formats:** `.wav`, `.mp3`, `.flac`

BirdNET is a neural network trained on 6,000+ bird species. Pass a field recording through the extractor and get back species detections with timestamps and confidence scores — which become searchable metadata. A corpus of dawn chorus recordings becomes queryable: "all recordings where a Wood Thrush was detected above 0.8 confidence," "sites where the Yellow Rail has been heard in the last five years."

`opensoundscape` generalizes beyond birds: bat echolocation, frog calls, insect stridulation, marine mammals. The same extraction pattern applies — acoustic event → text chunk with species, time, location, confidence.

Motivating use cases: ornithological field surveys, biodiversity monitoring transects, citizen science sound archives (xeno-canto, Macaulay Library), acoustic ecology research.

### Ocean hydrophone & passive acoustic monitoring
**Plugin type:** extractor
**Libraries:** `soundfile`, `scipy`, `opensoundscape`, custom spectral analysis
**Formats:** `.wav`, `.flac`, `.aiff`, hydrophone-specific container formats

Hydrophones dropped in the ocean produce continuous recordings of everything: whale song, shipping traffic, seismic events, military sonar, the ambient hum of the deep. NOAA's PMEL and MBARI maintain large passive acoustic archives. The extractor processes long recordings in windows, runs species classifiers or anomaly detectors, and indexes events as chunks with timestamp, frequency band, and detection type.

Once indexed: "all blue whale calls recorded at Station NRS11 in February," "shipping events within 20km of the monitoring buoy," "unusual low-frequency events coinciding with the earthquake sequence." The corpus stays local; the hydrophone data never has to leave the research institution.

Related: seismoacoustics (infrasound), cryosphere acoustics (glacial calving, ice sheet dynamics).

### Twitch VOD & streaming media transcription
**Plugin type:** extractor
**Libraries:** `yt-dlp`, `faster-whisper`

Download VOD audio, transcribe, chunk by segment. A streamer's full back-catalog becomes a searchable text corpus: "every time I talked about the map design in this game," "all the moments where chat went wild and I explained why." Works for any platform where `yt-dlp` can pull audio.

---

## Visual & Document Intelligence

### Image description via local vision model
**Plugin type:** extractor
**Libraries:** `ollama` + LLaVA/LLaMA-Vision, `Pillow`
**Formats:** `.jpg`, `.png`, `.tiff`, `.webp`

Send an image to a locally-running vision model, get back a text description, index it. A physical archive of photographs becomes semantically searchable without uploading a single pixel to a cloud service. The description becomes the chunk; the original image path is the provenance.

Stronger for documents: receipts, handwritten notes, whiteboards, serial number plates, screenshots with text. Pair with Tesseract for OCR-first fallback on clean printed text.

### Barcode & physical inventory scanning
**Plugin type:** extractor
**Libraries:** `zxing-cpp`, `pyzbar`, `Pillow`; vision model for unlabeled items

Photograph an object, scan its barcode or QR code, look up product data, index the record. Serial numbers, model numbers, purchase dates, storage locations, insurance values. A household or small institution (library, museum, makerspace) builds a searchable physical inventory with no SaaS subscription required.

Use cases: estate management, insurance documentation, equipment room tracking, artifact cataloging.

### Video keyframe extraction
**Plugin type:** extractor
**Libraries:** `opencv-python`, `ffmpeg-python`, vision model for description
**Formats:** `.mp4`, `.mkv`, `.mov`

Sample frames at regular intervals or scene-change boundaries, describe each via vision model, index by timestamp. A documentary rough cut, a lecture recording with slides, a surveillance archive — all become queryable by visual content rather than just filename.

---

## Text Formats & Specialized Documents

### Office formats (PPTX, XLSX, ODT)
**Plugin type:** extractor
**Libraries:** `python-pptx`, `openpyxl`, `odfpy`

Slide decks, spreadsheets, and OpenDocument files contain institutional knowledge that never makes it into searchable systems. One chunk per slide (PPTX), one chunk per sheet with headers + row data as prose (XLSX), heading-chunked text (ODT).

### RTF & legacy word processing
**Plugin type:** extractor
**Library:** `striprtf`

RTF is 40 years old and organizational archives are full of it. Strip the markup, chunk by paragraph.

### HTML & web archives
**Plugin type:** extractor
**Library:** `beautifulsoup4`

Local web archives (WARC files, downloaded site mirrors, browser exports). Strip tags, extract visible text, chunk by block element. Pair with `trafilatura` for article-optimized extraction that discards navigation and boilerplate.

### Markdown & structured text
**Plugin type:** extractor
**Libraries:** `mistletoe`, `markdown`

Parse the AST, chunk by heading level. A Markdown-based knowledge base (Obsidian vault, Logseq graph, wiki export) becomes a retrievable corpus with document structure preserved in metadata.

### Schema.org Recipe
**Plugin type:** extractor
**Libraries:** `extruct`, `recipe-scrapers`

Cookbooks and recipe sites embed structured data (`schema.org/Recipe`) with fields for ingredients, cook time, yield, suitable diet, and cuisine. Extract and index these fields as structured metadata alongside the recipe text. Enables queries like "warming soups under 30 minutes using pantry staples" that keyword search cannot answer. Works on local HTML archives, Gutenberg cookbooks, and USDA recipe databases.

Liturgical calendar integration is a natural extension: index feast-day recipes with the calendar date as metadata, query by upcoming observance.

---

## Language & Linguistics

### Multilingual corpora
**Plugin type:** embedder configuration
**Libraries:** `sentence-transformers` (nomic-embed-text, multilingual-e5), `langdetect`

The default sentence-transformers embedder is multilingual. Cross-lingual search (query in English, retrieve in French) works out of the box with the right model. Per-chunk language detection enables filtered retrieval ("only Spanish sources").

Languages with documented use cases in Alcove deployments: English, Spanish, Latin, French, German, Russian, Mandarin, Arabic, Samoan, Ojibwe, Tongan. Constructed languages (D'ni from the Myst universe, Klingon, Tolkien's Quenya) require metadata-based retrieval; semantic embeddings do not generalize.

### Endangered and indigenous language archives
**Plugin type:** extractor + embedder
**Considerations:** data sovereignty, community consent, access controls

Elder recordings, transcripts, curriculum materials, and oral histories in endangered languages. The extraction path is audio transcription (if recordings exist) or document OCR (if materials are written). The embedding challenge is that most multilingual models have thin coverage of low-resource languages; fine-tuned or community-trained models matter here.

Deployment model: the institution (tribal college, cultural center, university linguistics department) runs Alcove on their own hardware. Data does not leave the community. Access controls at the network level, not the plugin level.

Grant landscape: IMLS (Institute of Museum and Library Services), Administration for Native Americans (ANA Language Preservation), NEH Digital Humanities.

### Constructed language corpora
**Plugin type:** metadata-only indexing

Constructed languages with rich community archives (D'ni, Klingon, Na'vi, Tolkien's languages) are not well-served by semantic embeddings — the training data is too sparse. The pattern that works: index documents as opaque chunks with rich metadata (language, canon status, source, date), retrieve by metadata filter and keyword, skip vector similarity. The Alcove query layer supports metadata-only retrieval today.

---

## Scientific & Research Data

### Scientific paper corpora
**Plugin type:** extractor
**Libraries:** `pypdf`, `pymupdf`, `grobid-client`
**Sources:** arXiv bulk exports, PubMed Open Access, institutional repositories

Academic PDFs with consistent structure (abstract, methods, results, references) benefit from section-aware chunking. GROBID is an open-source tool that parses scientific PDFs into structured XML, enabling chunk-by-section rather than chunk-by-page. A research group indexes their literature corpus locally; queries return the specific methods section or result paragraph rather than a full paper.

### Field survey data & ecological monitoring
**Plugin type:** extractor
**Libraries:** `pandas`, `geopandas`, custom parsers
**Formats:** CSV, GeoJSON, species occurrence TSV (GBIF format)

Biodiversity survey data, species occurrence records, transect counts, phenology observations. Convert tabular records to prose chunks with location, date, species, and observer metadata. Query: "all Great Gray Owl sightings above 2000m elevation in March," "survey sites with declining amphibian counts since 2010."

### Federal regulatory corpora
**Plugin type:** extractor
**Libraries:** `pypdf`, `beautifulsoup4`, `lxml`
**Sources:** GovInfo bulk data (regulations.gov, Federal Register, Congressional bills)

Federal documents — bill summaries, regulatory comments, Federal Register notices — have consistent XML structure (GovInfo BILLSUM, BILLSTATUS formats). The extractor parses agency XML, emits one chunk per document section with Congress, agency, and docket metadata. Enables retrieval across the full regulatory record without a SaaS subscription to LexisNexis or Westlaw.

---

## Domain-Specific Embedder Plugins

### Legal domain embedder
**Plugin type:** embedder
**Library:** `sentence-transformers` with `legal-bert` or `law-ai/legal-led`

General-purpose embedders underperform on legal text because legal language has domain-specific semantics ("consideration," "estoppel," "in rem"). A legal-domain fine-tuned model improves retrieval quality for contract corpora, case law archives, and regulatory documents.

### Scientific/biomedical embedder
**Plugin type:** embedder
**Library:** `sentence-transformers` with `allenai/specter2`, `microsoft/BiomedNLP-BiomedBERT`

Biomedical and scientific text has the same domain-specificity problem. SPECTER2 is trained on scientific paper citations; BiomedBERT on PubMed. Use these instead of general-purpose embedders when the corpus is scientific literature.

### On-device Apple Silicon embedder
**Plugin type:** embedder
**Library:** `mlx-lm`

Run embedding inference on the M-series GPU via MLX. Fastest local option on Apple hardware; no GPU separate from the CPU, so memory bandwidth is the bottleneck rather than PCIe transfer. Suitable for large corpora where embedding throughput matters.

---

## Alternative Vector Backends

### SQLite-vec
**Plugin type:** backend
**Library:** `sqlite-vec`

Embeds vector search in a SQLite file. Zero external process, single-file corpus portability. Copy the `.db` file and the index moves with it. Strong fit for the desktop app goal and for operators who do not want to run ChromaDB as a background service.

### Qdrant
**Plugin type:** backend
**Library:** `qdrant-client`

Supports local embedded mode (file-based, no server) and remote server mode. Lighter memory footprint than ChromaDB at large scale. Built-in sparse vector support (useful for hybrid BM25 + dense retrieval).

### Weaviate
**Plugin type:** backend
**Library:** `weaviate-client`

Native hybrid search (BM25 + vector) with a rich filter API. Useful when the corpus has structured metadata that should participate in ranking, not just filtering.

---

## Notes on Building Plugins

Any of these can be packaged as a standalone pip installable and registered via `pyproject.toml` entry points. No Alcove source modification required:

```toml
[project.entry-points."alcove.extractors"]
wav  = "my_audio_plugin:extract_audio"
mp3  = "my_audio_plugin:extract_audio"
flac = "my_audio_plugin:extract_audio"
```

The plugin is discovered at startup, overrides the builtin for any shared extension names, and is visible in `alcove plugins`. See [ARCHITECTURE.md](ARCHITECTURE.md#plugin-system) for the full interface contract.

Authentication is out of scope for the plugin system. Plugins handle data flow; access control belongs at the deployment boundary.

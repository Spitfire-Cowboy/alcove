# Plugin Ideas & Domain Recipes

This document catalogs potential Alcove plugins and the domain use cases that motivate them. Each entry is a recipe: a corpus type, the plugin that gets data into the index, and what you can do once it's there.

These are ideas and directions — not all of them are implemented. The plugin system is open; if something here resonates, it can be built as a standalone pip package and registered against the `alcove.extractors`, `alcove.embedders`, or `alcove.backends` entry-point groups. See [ARCHITECTURE.md](ARCHITECTURE.md#plugin-system) for the interface contract.

---

## Plugin Philosophy

> **Gate question for every plugin: "Do we need to build this ourselves, or have some nerds already done this work for us?"**

Alcove is domain expert in exactly one thing: its own source code. Everything else is a plugin. This is by design — the birding community has built BirdNET; Cornell has built the eBird API and Macaulay Library; the bioacoustics community has built opensoundscape. The right move is to wrap that expertise as an extractor and let Alcove provide the local-first retrieval layer underneath.

A second principle: **view layer, not copy layer.** When indexing large external datasets, Alcove should store manifests of pointers with provenance metadata, not duplicate the data itself. The index is the access layer; the source stays authoritative.

---

## Domain Verticals

Fifteen verticals have been identified. The gate question separates them into two tiers:

**Deep nerd coverage — plugin and go:** birding, bioacoustics, music production, podcasting, film/post-production, photography, academic research, security/surveillance, streaming/Twitch.

**Partial coverage — some glue needed:** legal/e-discovery, journalism, real estate, insurance/claims, compliance/audit, architecture/construction.

The entries below go deep on several of these. The rest are sketched at the end.

---

## Audio

### Speech transcription
**Plugin type:** extractor
**Library:** `faster-whisper`, `whisper`
**Formats:** `.wav`, `.mp3`, `.m4a`, `.flac`, `.mp4`, `.ogg`

Transcribe spoken audio locally with OpenAI Whisper. The extractor runs inference on-device, emits time-coded text chunks, and indexes them like any other document. Oral histories, interview recordings, lecture audio, field notes dictated into a voice recorder — anything spoken becomes searchable text, with the original file as the provenance source. No audio leaves the machine.

Model size is configurable (`tiny` through `large-v3`); `base` is a reasonable default for most corpora.

### Speaker diarization
**Plugin type:** extractor
**Libraries:** `pyannote.audio`, `speechbrain`

Whisper tells you what was said; diarization tells you who said it. Combine both: every chunk gets a speaker label. A recorded meeting becomes queryable by participant: "what did Sarah say about the timeline?" A multi-interview oral history project gets per-subject retrieval.

### Semantic audio search (CLAP)
**Plugin type:** extractor + embedder
**Library:** `laion-clap`, `msclap`

CLAP (Contrastive Language-Audio Pretraining) embeds audio clips and natural language descriptions in the same space — the same insight as CLIP for images, applied to sound. Query by description: "find the clip where someone laughs," "birdsong from the hike," "rain on a metal roof." Works for any audio corpus where content-based retrieval beats filename-based search.

### Sound event classification
**Plugin type:** extractor
**Libraries:** `tensorflow` + YAMNet, `torch-audiomentations`

YAMNet classifies audio clips into 521 sound event categories (music, speech, animal sounds, environmental, etc.). Each classification becomes a searchable metadata tag. A mixed archive of field recordings, meetings, and media files gets automatically categorized without manual tagging.

### Music identification & fingerprinting
**Plugin type:** extractor
**Libraries:** `pyacoustid`, `chromaprint`

Chromaprint generates an acoustic fingerprint from any audio file; AcoustID matches it against a public database to return title, artist, and MusicBrainz ID. A personal music library becomes semantically indexed. A content creator can scan a project folder for inadvertent use of copyrighted material before publishing.

### Sentiment & prosody analysis
**Plugin type:** extractor
**Libraries:** `transformers` (speech emotion recognition models), `praat-parselmouth`

Not just what was said, but how. Sentiment models classify emotional tone per segment; Praat-parselmouth extracts prosodic features (pitch, speaking rate, intensity). Useful for meeting review, interview analysis, or any corpus where the emotional register of speech carries meaning.

### Bioacoustics & wildlife audio
**Plugin type:** extractor
**Libraries:** `birdnetlib` (wraps BirdNET-Analyzer), `opensoundscape`
**Formats:** `.wav`, `.mp3`, `.flac`

BirdNET is a Cornell-developed neural network trained on 6,000+ bird species. Pass a field recording through the extractor and get back species detections with timestamps and confidence scores — which become searchable metadata. A corpus of dawn chorus recordings becomes queryable: "all recordings where a Wood Thrush was detected above 0.8 confidence," "sites where the Yellow Rail has been heard in the last five years."

`opensoundscape` generalizes beyond birds: bat echolocation, frog calls, insect stridulation, marine mammals. The same extraction pattern applies — acoustic event → text chunk with species, time, location, confidence.

See the **Birding & Ornithology** vertical below for the full Cornell Lab stack.

### Ocean hydrophone & passive acoustic monitoring
**Plugin type:** extractor
**Libraries:** `soundfile`, `scipy`, `opensoundscape`, custom spectral analysis
**Formats:** `.wav`, `.flac`, `.aiff`, hydrophone-specific container formats

Hydrophones dropped in the ocean produce continuous recordings of everything: whale song, shipping traffic, seismic events, military sonar, the ambient hum of the deep. NOAA's PMEL and MBARI maintain large passive acoustic archives. The extractor processes long recordings in windows, runs species classifiers or anomaly detectors, and indexes events as chunks with timestamp, frequency band, and detection type.

Once indexed: "all blue whale calls recorded at Station NRS11 in February," "shipping events within 20km of the monitoring buoy," "unusual low-frequency events coinciding with the earthquake sequence." The corpus stays local; the hydrophone data never has to leave the research institution.

Related: seismoacoustics (infrasound), cryosphere acoustics (glacial calving, ice sheet dynamics). Conservation organizations deploying distributed acoustic sensor networks (rainforest, wetland, reef monitoring) produce the same kind of archive — long-running recordings tied to GPS coordinates that benefit from local retrieval without cloud dependency.

---

## Video

### Scene detection & keyframe extraction
**Plugin type:** extractor
**Libraries:** `scenedetect`, `opencv-python`, `ffmpeg-python`
**Formats:** `.mp4`, `.mkv`, `.mov`

PySceneDetect cuts a video into semantic segments at scene boundaries. Extract one representative frame per scene, describe it via a vision model, and index by timestamp. A documentary rough cut, a lecture with slides, or a surveillance archive becomes queryable by visual content.

### Object detection in video
**Plugin type:** extractor
**Libraries:** `ultralytics` (YOLOv8), `torch`

YOLO runs on Apple Silicon for lightweight use; GPU-accelerated on any CUDA device for throughput. Each detected object becomes a metadata tag on the corresponding video segment. "Find all clips with a dog," "segments where a whiteboard is visible," "scenes with more than four people."

### OCR on video frames
**Plugin type:** extractor
**Libraries:** `tesseract` (pytesseract), `paddleocr`

Text visible in video — signs, slides, whiteboards, on-screen titles, subtitles burned in — can be extracted from keyframes and indexed. A recorded presentation becomes searchable by slide text. A collection of instructional videos becomes retrievable by the formulas or diagrams shown on screen.

### Action recognition
**Plugin type:** extractor
**Libraries:** `transformers` (VideoMAE, TimeSformer), `torch`

What is happening in the video, not just what is visible in a single frame. Action recognition models classify temporal sequences: cooking, exercising, presenting, assembling, playing. Indexes a sports archive by play type, a home workout library by exercise, a manufacturing floor recording by process step.

### Video semantic embeddings
**Plugin type:** embedder
**Libraries:** `transformers` (CLIP, X-CLIP, VideoCLIP)

CLIP embeds individual frames in the same space as text queries. X-CLIP and VideoCLIP extend this to temporal clips. Query: "find segments that look like a campfire," "moments with emotional crowd reactions," "scenes set at night." No description required — the query is the retrieval key.

### Local LLM video understanding
**Plugin type:** extractor
**Libraries:** `ollama` + LLaVA-Video; `transformers` (Video-LLaMA, mPLUG-Owl)

Ask a natural language question about a video and get an answer grounded in specific timestamps. "What was shown on the whiteboard?" "At what point does the speaker change subjects?" "Describe everything that happens in the first two minutes." Heavier models (LLaVA-Video) run well on GPU; lighter variants run on Apple Silicon.

### Twitch VOD & streaming media
**Plugin type:** extractor
**Libraries:** `yt-dlp`, `faster-whisper`

Download VOD audio, transcribe, chunk by segment. A streamer's full back-catalog becomes a searchable text corpus: "every time I explained the decision to change the map design," "all the moments where I talked about ranked anxiety." Works for any platform where `yt-dlp` can pull audio. Combine with scene detection and object recognition for a richer index.

---

## Photos & Personal Media

### CLIP-based semantic photo search
**Plugin type:** extractor + embedder
**Library:** `open-clip-torch`, `Pillow`
**Formats:** `.jpg`, `.png`, `.heic`, `.webp`, `.tiff`

Apple already does semantic photo search ("beach sunset," "dog playing"). CLIP provides the same capability on your own hardware, against your own index, without uploading a pixel. Query: "photos from the cabin trip," "pictures of the kids at the park," "anything that looks like a birthday." The embedding stays local; the index stays local; nothing touches a cloud service.

### Face clustering
**Plugin type:** extractor
**Libraries:** `facenet-pytorch` (MTCNN + InceptionResnet), `scikit-learn`

Group photos by person without uploading to any cloud. MTCNN detects faces; ArcFace or InceptionResnet embeds them; clustering groups them by identity. Once named, person labels become searchable metadata. A family archive gets organized by person. An oral history project clusters interview subjects. No biometric data leaves the machine.

### EXIF & GPS metadata extraction
**Plugin type:** extractor
**Library:** `exifread`, `Pillow`

Every modern photo has embedded metadata: timestamp, GPS coordinates, camera model, focal length, exposure settings. Extract these as structured fields. "Photos taken in Denver," "everything shot with the 50mm before 2019," "the two weeks we were in Costa Rica" — all become valid queries without requiring image understanding.

Combine with semantic embeddings for compound queries: "outdoor photos from the Colorado trip where there's a body of water visible."

### Scene & location classification
**Plugin type:** extractor
**Libraries:** `torch` + Places365 model

Places365 classifies the location depicted in a photo into 365 scene categories: kitchen, forest, beach, gymnasium, art gallery, etc. The classification becomes a metadata tag. A mixed personal archive gets rough location labels without requiring GPS data in every file.

### iCloud Photo Library
**Plugin type:** extractor
**Library:** `osxphotos`, `Pillow`

`osxphotos` reads the local iCloud Photo Library on macOS without exporting — it accesses Apple's SQLite database directly and reads HEIC files from the local cache. Extract Apple's own metadata (albums, keywords, faces, places, favorites) alongside EXIF data, and index alongside CLIP embeddings for local semantic search over your full library.

---

## Domain Vertical: Birding & Ornithology

The birding vertical has the richest existing tooling of any domain. The nerds have already done the work; Alcove provides the local retrieval layer underneath.

**Cornell Lab toolkit:**

- **BirdNET-Analyzer** (`birdnetlib`): Species detection from audio. 6,000+ species. Runs locally. Output: species, timestamp, confidence, geographic filtering.
- **eBird API 2.0**: Real-time and historical sighting data. Recent observations by location, regional species lists, hotspot data. Used with `ebird-api` Python client.
- **ebirdst**: eBird Status & Trends — species abundance rasters, range maps, migration routes. R and Python interfaces.
- **Macaulay Library**: 84M+ media assets (audio, photos, video). Largest wildlife media archive in the world. Cornell-hosted; accessible via API.
- **NABirds dataset**: 48K annotated bird images across 555 North American species. Useful for fine-tuning visual classifiers.

**What you can build:** A local corpus of field recordings, annotated with BirdNET detections, cross-referenced against eBird occurrence data for the same location and date. Queries: "all recordings with species not on my county list," "audio detections that don't match expected seasonal presence according to eBird," "photos of birds I haven't seen in a year."

**Pattern:** Cornell built the domain expertise across 80 years of ornithology. Alcove wraps it as local-first infrastructure — no account required, no data uploaded, no subscription to access your own field recordings.

---

## Text Formats & Documents

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
**Library:** `beautifulsoup4`, `trafilatura`

Local web archives (WARC files, downloaded site mirrors, browser exports). `trafilatura` does article-optimized extraction that discards navigation and boilerplate; `beautifulsoup4` for structured HTML where the full document matters.

### Markdown & structured text
**Plugin type:** extractor
**Libraries:** `mistletoe`, `markdown`

Parse the AST, chunk by heading level. A Markdown-based knowledge base (Obsidian vault, Logseq graph, wiki export) becomes a retrievable corpus with document structure preserved in metadata.

### Schema.org Recipe
**Plugin type:** extractor
**Libraries:** `extruct`, `recipe-scrapers`

Cookbooks and recipe sites embed structured data (`schema.org/Recipe`) with fields for ingredients, cook time, yield, suitable diet, and cuisine. Extract and index these fields as structured metadata alongside the recipe text. Enables queries like "warming soups under 30 minutes using pantry staples" that keyword search cannot answer.

Liturgical calendar integration is a natural extension: index feast-day recipes with the calendar date as metadata, query by upcoming observance.

### Barcode & physical inventory scanning
**Plugin type:** extractor
**Libraries:** `zxing-cpp`, `pyzbar`, `Pillow`; vision model for unlabeled items

Photograph an object, scan its barcode or QR code, look up product data, index the record. Serial numbers, model numbers, purchase dates, storage locations, insurance values. Estate management, insurance documentation, equipment room tracking, artifact cataloging — without a SaaS subscription.

---

## Language & Linguistics

### Multilingual corpora
**Plugin type:** embedder configuration
**Libraries:** `sentence-transformers` (nomic-embed-text, multilingual-e5), `langdetect`

The default embedder is multilingual. Cross-lingual search (query in English, retrieve in French) works out of the box. Per-chunk language detection enables filtered retrieval.

Languages with documented use cases in Alcove deployments: English, Spanish, Latin, French, German, Russian, Mandarin, Arabic, Samoan, Ojibwe, Tongan. Constructed languages (D'ni, Klingon, Tolkien's Quenya) require metadata-based retrieval; semantic embeddings do not generalize.

### Endangered and indigenous language archives
**Plugin type:** extractor + embedder
**Considerations:** data sovereignty, community consent, access controls

Elder recordings, transcripts, curriculum materials, and oral histories in endangered languages. The extraction path is audio transcription (if recordings exist) or document OCR (if materials are written). The embedding challenge is that most multilingual models have thin coverage of low-resource languages; fine-tuned or community-trained models matter here.

Deployment model: the institution (tribal college, cultural center, university linguistics department) runs Alcove on their own hardware. Data does not leave the community.

Grant landscape: IMLS, Administration for Native Americans (ANA Language Preservation), NEH Digital Humanities.

### Constructed language corpora
**Plugin type:** metadata-only indexing

Constructed languages with rich community archives (D'ni, Klingon, Na'vi, Tolkien's languages) are not well-served by semantic embeddings — the training data is too sparse. Index with rich metadata (language, canon status, source, date), retrieve by metadata filter and keyword, skip vector similarity.

---

## Scientific & Research Data

### Scientific paper corpora
**Plugin type:** extractor
**Libraries:** `pypdf`, `pymupdf`, `grobid-client`
**Sources:** arXiv bulk exports, PubMed Open Access, institutional repositories

GROBID parses scientific PDFs into structured XML, enabling chunk-by-section rather than chunk-by-page. A research group indexes their literature corpus locally; queries return the specific methods section or result paragraph rather than a full paper.

### Field survey data & ecological monitoring
**Plugin type:** extractor
**Libraries:** `pandas`, `geopandas`
**Formats:** CSV, GeoJSON, GBIF occurrence TSV

Biodiversity survey data, species occurrence records, transect counts, phenology observations. Convert tabular records to prose chunks with location, date, species, and observer metadata. Query: "survey sites with declining amphibian counts since 2010," "all Great Gray Owl sightings above 2000m in March."

### Federal regulatory corpora
**Plugin type:** extractor
**Libraries:** `pypdf`, `beautifulsoup4`, `lxml`
**Sources:** GovInfo bulk data (regulations.gov, Federal Register, Congressional bills)

Federal documents have consistent XML structure (GovInfo BILLSUM, BILLSTATUS formats). The extractor parses agency XML, emits one chunk per section with Congress, agency, and docket metadata. Retrieval across the full regulatory record without a SaaS subscription to LexisNexis or Westlaw.

---

## Domain-Specific Embedder Plugins

### Legal domain embedder
**Plugin type:** embedder
**Library:** `sentence-transformers` with `legal-bert` or `law-ai/legal-led`

Legal language has domain-specific semantics ("consideration," "estoppel," "in rem") that general-purpose embedders underserve. A legal-domain fine-tuned model improves retrieval quality for contract corpora, case law archives, and regulatory documents.

### Scientific/biomedical embedder
**Plugin type:** embedder
**Library:** `sentence-transformers` with `allenai/specter2`, `microsoft/BiomedNLP-BiomedBERT`

SPECTER2 is trained on scientific paper citations; BiomedBERT on PubMed. Use these instead of general-purpose embedders when the corpus is scientific literature.

### On-device Apple Silicon embedder
**Plugin type:** embedder
**Library:** `mlx-lm`

Embedding inference on the M-series GPU via MLX. No GPU separate from the CPU, so memory bandwidth is the bottleneck rather than PCIe transfer. Suitable for large corpora where embedding throughput matters.

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

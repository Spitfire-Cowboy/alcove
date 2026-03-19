# Audio Plugins

Alcove wraps existing audio analysis libraries. It does not reimplement signal processing. Each plugin registers an extractor for one or more file extensions and returns structured metadata that lands in the index alongside the source file.

## Speech Transcription

**Library:** `faster-whisper`

Transcribes any spoken audio to time-coded text. Use it for oral histories, interviews, lectures, field notes, voice memos. Each chunk carries a start and end timestamp so queries can return a playback position, not just a filename.

Faster-Whisper runs locally. Audio never leaves the machine.

## Speaker Diarization

**Library:** `pyannote.audio`

Segments audio by speaker identity. Each segment gets a label (SPEAKER_00, SPEAKER_01, etc.). Combine with the transcription plugin: every text chunk carries both a timestamp and a speaker tag. Useful for multi-participant interviews, council recordings, panel discussions.

Note: pyannote models require accepting a license on Hugging Face before download.

## Semantic Audio Search

**Library:** `laion-clap`

CLAP (Contrastive Language-Audio Pretraining) embeds audio clips and text queries in a shared vector space. You can query with a text description: "rain on a metal roof," "crowd applause," "someone laughing." No transcription required. Works on any audio, not just speech.

## Sound Classification

**Library:** YAMNet via `tensorflow`

Classifies audio against 521 sound event categories from Google's AudioSet taxonomy. Outputs confidence scores per category. Use it to tag mixed archives automatically, or to filter a large collection down to a specific sound type before deeper analysis.

## Music Fingerprinting

**Libraries:** `pyacoustid`, `chromaprint`

Identifies recordings by acoustic fingerprint against the AcoustID database. Returns MusicBrainz identifiers when a match is found. Useful for personal music libraries, digitized tape collections, or copyright scanning workflows.

## Bioacoustics

**Libraries:** `birdnetlib`, `opensoundscape`

Detects species from field recordings: birds, bats, frogs, marine mammals. Returns species name, timestamp, and confidence score per detection. See the [Birding detail file](birding.md) for how this connects to eBird and other ornithology data sources.

## Ocean Hydrophone Archives

**Libraries:** `soundfile`, `scipy`

Indexes passive acoustic monitoring archives: whale calls, shipping vessel noise, seismic events. Institutions running long-term hydrophone arrays accumulate recordings that are impractical to review manually. This plugin extracts metadata and enables time-range queries over large archives. Data stays at the institution.

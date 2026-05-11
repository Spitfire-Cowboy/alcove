from __future__ import annotations

import json
import sys
import types
import urllib.error

import pytest
from fastapi.testclient import TestClient

from alcove.index.language import (
    LanguageDetection,
    LangdetectLanguageDetector,
    OllamaLanguageDetector,
    TransformersLanguageDetector,
    detect_language,
    get_language_detector,
)
from alcove.query import api
from alcove.query.retriever import query_text


@pytest.fixture(autouse=True)
def clear_language_config(monkeypatch):
    for env_name in (
        "ALCOVE_CONFIG_PATH",
        "ALCOVE_LANGUAGE_PROVIDER",
        "ALCOVE_LANGUAGE_MODEL",
        "ALCOVE_LANGUAGE_CONFIDENCE_THRESHOLD",
        "ALCOVE_LANGUAGE_OLLAMA_BASE_URL",
        "ALCOVE_LANGUAGE_TIMEOUT",
        "ALCOVE_LANGUAGE_MAX_CHARS",
    ):
        monkeypatch.delenv(env_name, raising=False)


class _FakeEmbedder:
    def embed(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]


class _CaptureBackend:
    def __init__(self):
        self.add_calls = []
        self.query_calls = []

    def add(self, ids, embeddings, documents, metadatas):
        self.add_calls.append({
            "ids": ids,
            "embeddings": embeddings,
            "documents": documents,
            "metadatas": metadatas,
        })

    def query(self, embedding, k=3, collections=None, language_filter=None):
        self.query_calls.append({
            "embedding": embedding,
            "k": k,
            "collections": collections,
            "language_filter": language_filter,
        })
        return {"ids": [[]], "documents": [[]], "distances": [[]], "metadatas": [[]]}


class _FakeLanguageDetector:
    provider = "fake"

    def __init__(self):
        self.seen = []

    def detect(self, text):
        self.seen.append(text)
        language = "es" if "La entrevista" in text else "en"
        return LanguageDetection(language, 1.0, self.provider)


def test_detect_language_empty_returns_unknown():
    assert detect_language("") == "unknown"


def test_detect_language_english_returns_en():
    text = "The harbor interviews describe family history, migration, and faith traditions in detail."
    assert detect_language(text) == "en"


def test_detect_language_spanish_returns_es():
    text = "Las entrevistas familiares describen historia, migracion, tradiciones y memoria colectiva."
    assert detect_language(text) == "es"


def test_detect_language_script_shortcuts():
    assert detect_language("История семьи и сообщества") == "ru"
    assert detect_language("家族历史和社区记忆") == "zh"
    assert detect_language("تاريخ العائلة والمجتمع") == "ar"


def test_detect_language_accent_shortcuts():
    assert detect_language("niñez") == "es"
    assert detect_language("garçon") == "fr"


def test_detect_language_unknown_without_tokens():
    assert detect_language("12345 !!!") == "unknown"


def test_detect_language_french_heuristic():
    text = "L'histoire de la famille décrit la mémoire, le travail et la communauté."
    assert detect_language(text) == "fr"


def test_detect_language_unknown_for_unscored_latin_text():
    assert detect_language("qwerty zxcv asdf") == "unknown"


def test_detect_language_handles_invalid_sample_limit(monkeypatch):
    monkeypatch.setenv("ALCOVE_LANGUAGE_MAX_CHARS", "wide")

    assert detect_language("The family history interview") == "en"


def test_get_language_detector_can_disable_detection(monkeypatch):
    monkeypatch.setenv("ALCOVE_LANGUAGE_PROVIDER", "none")

    detector = get_language_detector()

    assert detector.detect("The family history interview").language == "unknown"


def test_detect_language_uses_configured_langdetect_provider(monkeypatch):
    fake_module = types.ModuleType("langdetect")

    class FakeDetectorFactory:
        seed = None

    class FakeLangDetectException(Exception):
        pass

    class FakeLang:
        lang = "pt"
        prob = 0.91

    def detect_portuguese(sample):
        return [FakeLang()]

    fake_module.DetectorFactory = FakeDetectorFactory
    fake_module.LangDetectException = FakeLangDetectException
    fake_module.detect_langs = detect_portuguese
    monkeypatch.setitem(sys.modules, "langdetect", fake_module)
    monkeypatch.setenv("ALCOVE_LANGUAGE_PROVIDER", "langdetect")

    assert detect_language("texto em portugues") == "pt"
    assert FakeDetectorFactory.seed == 0


def test_langdetect_provider_returns_unknown_on_low_confidence(monkeypatch):
    fake_module = types.ModuleType("langdetect")

    class FakeDetectorFactory:
        seed = None

    class FakeLangDetectException(Exception):
        pass

    class FakeLang:
        lang = "es"
        prob = 0.40

    def detect_low_confidence(sample):
        return [FakeLang()]

    fake_module.DetectorFactory = FakeDetectorFactory
    fake_module.LangDetectException = FakeLangDetectException
    fake_module.detect_langs = detect_low_confidence
    monkeypatch.setitem(sys.modules, "langdetect", fake_module)

    detector = LangdetectLanguageDetector(confidence_threshold=0.75)

    assert detector.detect("La familia").language == "unknown"


def test_langdetect_provider_handles_empty_and_no_candidates(monkeypatch):
    fake_module = types.ModuleType("langdetect")

    class FakeDetectorFactory:
        seed = None

    class FakeLangDetectException(Exception):
        pass

    fake_module.DetectorFactory = FakeDetectorFactory
    fake_module.LangDetectException = FakeLangDetectException
    fake_module.detect_langs = lambda sample: []
    monkeypatch.setitem(sys.modules, "langdetect", fake_module)

    detector = LangdetectLanguageDetector()

    assert detector.detect("").language == "unknown"
    assert detector.detect("???").language == "unknown"


def test_langdetect_provider_handles_detection_exception(monkeypatch):
    fake_module = types.ModuleType("langdetect")

    class FakeDetectorFactory:
        seed = None

    class FakeLangDetectException(Exception):
        pass

    def fail_detect(sample):
        raise FakeLangDetectException("not enough text")

    fake_module.DetectorFactory = FakeDetectorFactory
    fake_module.LangDetectException = FakeLangDetectException
    fake_module.detect_langs = fail_detect
    monkeypatch.setitem(sys.modules, "langdetect", fake_module)

    assert LangdetectLanguageDetector().detect("???").language == "unknown"


def test_langdetect_provider_reports_missing_dependency(monkeypatch):
    original_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "langdetect":
            raise ImportError("missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)

    with pytest.raises(RuntimeError, match="langdetect"):
        LangdetectLanguageDetector().detect("The family history interview")


def test_transformers_provider_uses_configured_model(monkeypatch):
    fake_module = types.ModuleType("transformers")
    calls = {}

    def fake_pipeline(task, model):
        calls["task"] = task
        calls["model"] = model

        def classify(sample, truncation=True):
            calls["sample"] = sample
            calls["truncation"] = truncation
            return [{"label": "es", "score": 0.97}]

        return classify

    fake_module.pipeline = fake_pipeline
    monkeypatch.setitem(sys.modules, "transformers", fake_module)

    detector = TransformersLanguageDetector(model_name="local-language-id")

    assert detector.detect("La familia").language == "es"
    assert calls == {
        "task": "text-classification",
        "model": "local-language-id",
        "sample": "La familia",
        "truncation": True,
    }


def test_transformers_provider_handles_empty_and_low_confidence(monkeypatch):
    fake_module = types.ModuleType("transformers")

    def fake_pipeline(task, model):
        return lambda sample, truncation=True: [{"label": "es", "score": 0.2}]

    fake_module.pipeline = fake_pipeline
    monkeypatch.setitem(sys.modules, "transformers", fake_module)

    detector = TransformersLanguageDetector(confidence_threshold=0.8)

    assert detector.detect("").language == "unknown"
    assert detector.detect("La familia").language == "unknown"


def test_transformers_provider_reports_missing_dependency(monkeypatch):
    original_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "transformers":
            raise ImportError("missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)

    with pytest.raises(RuntimeError, match="transformers"):
        TransformersLanguageDetector()


def test_ollama_provider_reads_json_language_response(monkeypatch):
    calls = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({"response": json.dumps({"language": "fr"})}).encode("utf-8")

    def fake_urlopen(request, timeout):
        calls["url"] = request.full_url
        calls["timeout"] = timeout
        calls["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr("alcove.index.language.urllib.request.urlopen", fake_urlopen)

    detector = OllamaLanguageDetector(
        model_name="llama3.2",
        base_url="http://127.0.0.1:11434",
        timeout=5,
    )

    assert detector.detect("Bonjour la famille").language == "fr"
    assert calls["url"] == "http://127.0.0.1:11434/api/generate"
    assert calls["timeout"] == 5
    assert calls["body"]["model"] == "llama3.2"
    assert calls["body"]["format"] == "json"


def test_ollama_provider_handles_empty_text():
    assert OllamaLanguageDetector().detect("").language == "unknown"


def test_ollama_provider_returns_unknown_for_unparseable_response(monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({"response": "not-json"}).encode("utf-8")

    monkeypatch.setattr(
        "alcove.index.language.urllib.request.urlopen",
        lambda request, timeout: FakeResponse(),
    )

    detector = OllamaLanguageDetector()

    assert detector.detect("Bonjour la famille").language == "unknown"


def test_ollama_provider_reports_http_and_url_errors(monkeypatch):
    def raise_http(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url,
            500,
            "server error",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr("alcove.index.language.urllib.request.urlopen", raise_http)
    detector = OllamaLanguageDetector(base_url="http://127.0.0.1:11434")

    with pytest.raises(RuntimeError, match="HTTP 500"):
        detector.detect("Bonjour")

    def raise_url(request, timeout):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr("alcove.index.language.urllib.request.urlopen", raise_url)

    with pytest.raises(RuntimeError, match="Could not reach Ollama"):
        detector.detect("Bonjour")


def test_invalid_confidence_env_falls_back(monkeypatch):
    monkeypatch.setenv("ALCOVE_LANGUAGE_CONFIDENCE_THRESHOLD", "wide")

    detector = LangdetectLanguageDetector()

    assert detector.confidence_threshold == 0.0


def test_get_language_detector_rejects_unknown_provider(monkeypatch):
    monkeypatch.setenv("ALCOVE_LANGUAGE_PROVIDER", "does-not-exist")

    with pytest.raises(ValueError, match="Unknown language detector"):
        get_language_detector()


def test_get_language_detector_configures_transformers_provider(monkeypatch):
    fake_module = types.ModuleType("transformers")
    calls = {}

    def fake_pipeline(task, model):
        calls["task"] = task
        calls["model"] = model
        return lambda sample, truncation=True: [{"label": "en", "score": 1.0}]

    fake_module.pipeline = fake_pipeline
    monkeypatch.setitem(sys.modules, "transformers", fake_module)
    monkeypatch.setenv("ALCOVE_LANGUAGE_PROVIDER", "huggingface")
    monkeypatch.setenv("ALCOVE_LANGUAGE_MODEL", "local-detector")
    monkeypatch.setenv("ALCOVE_LANGUAGE_CONFIDENCE_THRESHOLD", "0.5")

    detector = get_language_detector()

    assert detector.model_name == "local-detector"
    assert detector.confidence_threshold == 0.5
    assert calls == {"task": "text-classification", "model": "local-detector"}


def test_get_language_detector_configures_ollama_provider(monkeypatch):
    monkeypatch.setenv("ALCOVE_LANGUAGE_PROVIDER", "ollama")
    monkeypatch.setenv("ALCOVE_LANGUAGE_MODEL", "llama3.2")
    monkeypatch.setenv("ALCOVE_LANGUAGE_OLLAMA_BASE_URL", "http://localhost:11435")
    monkeypatch.setenv("ALCOVE_LANGUAGE_TIMEOUT", "7")

    detector = get_language_detector()

    assert detector.model_name == "llama3.2"
    assert detector.base_url == "http://localhost:11435"
    assert detector.timeout == 7


def test_plugin_language_detector_can_be_selected(monkeypatch):
    class CustomDetector:
        provider = "custom"

        def detect(self, text):
            return LanguageDetection("tlh", 1.0, self.provider)

    monkeypatch.setenv("ALCOVE_LANGUAGE_PROVIDER", "custom")
    monkeypatch.setattr(
        "alcove.plugins.discover_language_detectors",
        lambda: {"custom": CustomDetector},
    )

    assert detect_language("nuqneH") == "tlh"


def test_index_pipeline_writes_language_metadata(tmp_path, monkeypatch):
    from alcove.index import pipeline

    chunks_file = tmp_path / "chunks.jsonl"
    rows = [
        {
            "id": "a:0",
            "source": "english.txt",
            "chunk": "The interview transcript discusses work, family, and local history in Minnesota.",
        },
        {
            "id": "b:0",
            "source": "spanish.txt",
            "chunk": "La entrevista habla de trabajo, familia y memoria cultural en la comunidad.",
        },
    ]
    chunks_file.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

    backend = _CaptureBackend()
    monkeypatch.setattr(pipeline, "get_embedder", _FakeEmbedder)

    def get_backend(_embedder):
        return backend

    monkeypatch.setattr(pipeline, "get_backend", get_backend)
    detector = _FakeLanguageDetector()
    monkeypatch.setattr(pipeline, "get_language_detector", lambda: detector)

    total = pipeline.run(chunks_file=str(chunks_file))

    assert total == 2
    assert detector.seen == [row["chunk"] for row in rows]
    metadatas = backend.add_calls[0]["metadatas"]
    assert [meta["source"] for meta in metadatas] == ["english.txt", "spanish.txt"]
    assert [meta["language"] for meta in metadatas] == ["en", "es"]


def test_index_pipeline_preserves_existing_language_without_detector(tmp_path, monkeypatch):
    from alcove.index import pipeline

    chunks_file = tmp_path / "chunks.jsonl"
    chunks_file.write_text(
        json.dumps({
            "id": "a:0",
            "source": "tagged.txt",
            "chunk": "Already tagged.",
            "language": "FR",
        }),
        encoding="utf-8",
    )

    backend = _CaptureBackend()
    monkeypatch.setattr(pipeline, "get_embedder", _FakeEmbedder)
    monkeypatch.setattr(pipeline, "get_backend", lambda _embedder: backend)
    monkeypatch.setattr(
        pipeline,
        "get_language_detector",
        lambda: (_ for _ in ()).throw(AssertionError("detector should not load")),
    )

    assert pipeline.run(chunks_file=str(chunks_file)) == 1
    assert backend.add_calls[0]["metadatas"][0]["language"] == "fr"


def test_retriever_passes_language_filter(monkeypatch):
    from alcove.query import retriever

    backend = _CaptureBackend()
    monkeypatch.setattr(retriever, "get_embedder", _FakeEmbedder)

    def get_backend(_embedder):
        return backend

    monkeypatch.setattr(retriever, "get_backend", get_backend)

    result = query_text("hola mundo", n_results=4, language_filter="es")

    assert result["ids"] == [[]]
    assert backend.query_calls[0]["k"] == 4
    assert backend.query_calls[0]["language_filter"] == "es"


def test_api_query_accepts_language_filter(monkeypatch):
    called = {}

    def fake_query_text(query, n_results=3, language_filter=None, **kwargs):
        called["query"] = query
        called["k"] = n_results
        called["language_filter"] = language_filter
        called["collections"] = kwargs.get("collections")
        return {"ids": [[]], "documents": [[]], "distances": [[]], "metadatas": [[]]}

    monkeypatch.setattr(api, "query_text", fake_query_text)

    client = TestClient(api.app)
    response = client.post("/query", json={"query": "hola", "k": 2, "language_filter": "es"})

    assert response.status_code == 200
    assert called == {"query": "hola", "k": 2, "language_filter": "es", "collections": None}


def test_keyword_search_can_filter_by_language(tmp_path):
    from alcove.index.keyword import KeywordIndex

    chunks_file = tmp_path / "chunks.jsonl"
    rows = [
        {
            "id": "en:0",
            "source": "english.txt",
            "chunk": "The family interview covers community history.",
        },
        {
            "id": "es:0",
            "source": "spanish.txt",
            "chunk": "La entrevista familiar cubre historia de la comunidad.",
        },
    ]
    chunks_file.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

    result = KeywordIndex(str(chunks_file)).search("historia comunidad", k=3, language_filter="es")

    assert result["ids"] == [["es:0"]]
    assert result["metadatas"][0][0]["language"] == "es"


def test_keyword_search_can_filter_by_collection_after_scoring(tmp_path):
    from alcove.index.keyword import KeywordIndex

    chunks_file = tmp_path / "chunks.jsonl"
    rows = [
        {
            "id": "letters:0",
            "source": "letters.txt",
            "collection": "letters",
            "chunk": "The family interview covers community history.",
        },
        {
            "id": "minutes:0",
            "source": "minutes.txt",
            "collection": "minutes",
            "chunk": "The family interview covers community history.",
        },
    ]
    chunks_file.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

    result = KeywordIndex(str(chunks_file)).search(
        "family community",
        k=1,
        collections=["minutes"],
    )

    assert result["ids"] == [["minutes:0"]]
    assert result["metadatas"][0][0]["collection"] == "minutes"


def test_keyword_search_uses_existing_language_without_detector(tmp_path, monkeypatch):
    from alcove.index import keyword

    chunks_file = tmp_path / "chunks.jsonl"
    chunks_file.write_text(
        json.dumps({
            "id": "fr:0",
            "source": "french.txt",
            "language": "FR",
            "chunk": "famille histoire communaute",
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        keyword,
        "get_language_detector",
        lambda: (_ for _ in ()).throw(AssertionError("detector should not load")),
    )

    result = keyword.KeywordIndex(str(chunks_file)).search(
        "famille histoire",
        k=1,
        language_filter="fr",
    )

    assert result["ids"] == [["fr:0"]]
    assert result["metadatas"][0][0]["language"] == "fr"


def test_api_dispatch_keyword_passes_collection_and_language(monkeypatch):
    called = {}

    def fake_query_keyword(query, **kwargs):
        called["query"] = query
        called.update(kwargs)
        return {"ids": [[]], "documents": [[]], "distances": [[]], "metadatas": [[]]}

    monkeypatch.setattr(api, "query_keyword", fake_query_keyword)

    result = api._dispatch_query(
        "familia",
        4,
        mode="keyword",
        collections=["letters"],
        language_filter="es",
    )

    assert result["ids"] == [[]]
    assert called == {
        "query": "familia",
        "n_results": 4,
        "collections": ["letters"],
        "language_filter": "es",
    }


def test_api_dispatch_hybrid_passes_language(monkeypatch):
    called = {}

    def fake_query_hybrid(query, **kwargs):
        called["query"] = query
        called.update(kwargs)
        return {"ids": [[]], "documents": [[]], "distances": [[]], "metadatas": [[]]}

    monkeypatch.setattr(api, "query_hybrid", fake_query_hybrid)

    result = api._dispatch_query("familia", 2, mode="hybrid", language_filter="es")

    assert result["ids"] == [[]]
    assert called == {
        "query": "familia",
        "n_results": 2,
        "collections": None,
        "language_filter": "es",
    }


def test_hybrid_query_passes_collection_and_language(monkeypatch):
    from alcove.query import retriever

    calls = []

    def fake_query_text(query, **kwargs):
        calls.append(("semantic", query, kwargs))
        return {
            "ids": [["doc-1"]],
            "documents": [["semantic"]],
            "distances": [[0.2]],
            "metadatas": [[{"source": "a.txt"}]],
        }

    def fake_query_keyword(query, **kwargs):
        calls.append(("keyword", query, kwargs))
        return {
            "ids": [["doc-1"]],
            "documents": [["keyword"]],
            "distances": [[0.4]],
            "metadatas": [[{"source": "a.txt"}]],
        }

    monkeypatch.setattr(retriever, "query_text", fake_query_text)
    monkeypatch.setattr(retriever, "query_keyword", fake_query_keyword)

    result = retriever.query_hybrid(
        "familia",
        n_results=3,
        collections=["letters"],
        language_filter="es",
    )

    assert result["ids"] == [["doc-1"]]
    assert calls == [
        (
            "semantic",
            "familia",
            {
                "n_results": 3,
                "collections": ["letters"],
                "language_filter": "es",
            },
        ),
        (
            "keyword",
            "familia",
            {
                "n_results": 3,
                "collections": ["letters"],
                "language_filter": "es",
            },
        ),
    ]


def test_chroma_query_where_combines_collection_and_language():
    from alcove.index.backend import _query_where

    assert _query_where() is None
    assert _query_where(language_filter="ES") == {"language": "es"}
    assert _query_where(collections=["docs"], language_filter="es") == {
        "$and": [{"collection": {"$in": ["docs"]}}, {"language": "es"}]
    }


class _FakeChromaCollection:
    name = "docs"

    def __init__(self):
        self.query_kwargs = None

    def count(self):
        return 1

    def query(self, **kwargs):
        self.query_kwargs = kwargs
        return {
            "ids": [["doc-1"]],
            "documents": [["hola"]],
            "distances": [[0.1]],
            "metadatas": [[{"source": "a.txt", "language": "es"}]],
        }


def test_multi_chroma_query_passes_language_filter():
    from alcove.index.backend import MultiChromaBackend

    collection = _FakeChromaCollection()
    backend = MultiChromaBackend.__new__(MultiChromaBackend)

    def get_filtered_collections(collections=None):
        return [collection]

    backend._get_filtered_collections = get_filtered_collections

    result = backend.query([0.1], k=1, language_filter="ES")

    assert result["ids"] == [["doc-1"]]
    assert collection.query_kwargs["where"] == {"language": "es"}


def test_multi_root_query_passes_language_filter():
    from alcove.index.backend import MultiRootBackend

    collection = _FakeChromaCollection()
    backend = MultiRootBackend.__new__(MultiRootBackend)
    backend._cols = [("docs", None, collection)]

    result = backend.query([0.1], k=1, language_filter="es")

    assert result["ids"] == [["doc-1"]]
    assert collection.query_kwargs["where"] == {"language": "es"}


class _FakeZvecDoc:
    def __init__(self, doc_id="doc-1", score=-0.2, **fields):
        self.id = doc_id
        self.score = score
        self._fields = fields

    def field(self, name):
        return self._fields.get(name)


class _FakeZvec:
    class DataType:
        STRING = "string"
        VECTOR_FP32 = "vector"

    class CollectionOption:
        pass

    class FieldSchema:
        def __init__(self, name, data_type):
            self.name = name
            self.data_type = data_type

    class VectorSchema:
        def __init__(self, name, data_type, dimension):
            self.name = name
            self.data_type = data_type
            self.dimension = dimension

    class CollectionSchema:
        def __init__(self, name, fields, vectors):
            self.name = name
            self.fields = fields
            self.vectors = vectors

    class VectorQuery:
        def __init__(self, name, vector):
            self.name = name
            self.vector = vector

    class Doc:
        def __init__(self, doc_id=None, vectors=None, fields=None, **kwargs):
            if doc_id is None:
                doc_id = kwargs["id"]
            self.id = doc_id
            self.vectors = vectors
            self.fields = fields


class _FakeZvecCollection:
    def __init__(self, docs=None, raise_on_language=False):
        self.docs = docs or []
        self.raise_on_language = raise_on_language
        self.upserted = None
        self.flushed = False

    def upsert(self, docs):
        self.upserted = docs

    def flush(self):
        self.flushed = True

    def query(self, vectors, topk, output_fields):
        if self.raise_on_language and "language" in output_fields:
            raise RuntimeError("old schema")
        return self.docs[:topk]


def test_zvec_add_writes_language_metadata():
    from alcove.index.backend import ZvecBackend

    backend = ZvecBackend.__new__(ZvecBackend)
    backend._zvec = _FakeZvec
    backend._collection = _FakeZvecCollection()

    backend.add(
        ids=["doc-1"],
        embeddings=[[0.1]],
        documents=["hola"],
        metadatas=[{"source": "a.txt", "collection": "docs", "language": "ES"}],
    )

    doc = backend._collection.upserted[0]
    assert doc.fields["language"] == "es"
    assert backend._collection.flushed is True


def test_zvec_query_filters_by_language_and_returns_metadata():
    from alcove.index.backend import ZvecBackend

    backend = ZvecBackend.__new__(ZvecBackend)
    backend._zvec = _FakeZvec
    backend._collection = _FakeZvecCollection([
        _FakeZvecDoc(document="hello", source="a.txt", collection="docs", language="en"),
        _FakeZvecDoc(doc_id="doc-2", document="hola", source="b.txt", collection="docs", language="es"),
    ])

    result = backend.query([0.1], k=1, language_filter="es")

    assert result["ids"] == [["doc-2"]]
    assert result["metadatas"][0][0]["language"] == "es"


def test_zvec_query_filters_by_collection():
    from alcove.index.backend import ZvecBackend

    backend = ZvecBackend.__new__(ZvecBackend)
    backend._zvec = _FakeZvec
    backend._collection = _FakeZvecCollection([
        _FakeZvecDoc(document="hello", source="a.txt", collection="letters", language="en"),
        _FakeZvecDoc(doc_id="doc-2", document="hola", source="b.txt", collection="minutes", language="es"),
    ])

    result = backend.query([0.1], k=1, collections=["minutes"])

    assert result["ids"] == [["doc-2"]]
    assert result["metadatas"][0][0]["collection"] == "minutes"


def test_zvec_query_handles_old_schema_without_language():
    from alcove.index.backend import ZvecBackend

    backend = ZvecBackend.__new__(ZvecBackend)
    backend._zvec = _FakeZvec
    backend._collection = _FakeZvecCollection(
        [_FakeZvecDoc(document="hello", source="a.txt", collection="docs")],
        raise_on_language=True,
    )

    result = backend.query([0.1], k=1)

    assert result["ids"] == [["doc-1"]]
    assert result["metadatas"][0][0]["language"] == "unknown"

from __future__ import annotations

import ipaddress
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class LanguageDetection:
    language: str = "unknown"
    confidence: float | None = None
    provider: str = "unknown"


class LanguageDetector(Protocol):
    provider: str

    def detect(self, text: str) -> LanguageDetection:
        pass  # pragma: no cover


_ENGLISH_MARKERS = {
    "the", "and", "in", "of", "to", "with", "for", "from", "this", "that",
    "history", "family", "interview", "interviews", "traditions", "detail",
    "work", "community",
}
_SPANISH_MARKERS = {
    "el", "la", "las", "los", "de", "del", "y", "en", "con", "para", "por",
    "una", "un", "familia", "historia", "entrevista", "entrevistas",
    "tradiciones", "memoria", "migracion", "trabajo", "comunidad",
}
_FRENCH_MARKERS = {
    "le", "les", "des", "une", "et", "en", "du", "au", "aux", "ce",
    "est", "dans", "sur", "par", "pour", "avec", "que", "qui",
    "histoire", "famille", "entretien", "traditions", "memoire",
    "travail", "communaute", "recherche",
}


def _normalize_language(value: object) -> str:
    if value is None:
        return "unknown"
    normalized = str(value).strip().lower().replace("_", "-")
    return normalized or "unknown"


def _sample_text(text: str, max_chars: int = 4000) -> str:
    limit = max(1, max_chars)
    sample = (text or "").strip()
    return sample[:limit]


class NoneLanguageDetector:
    provider = "none"

    def detect(self, text: str) -> LanguageDetection:
        return LanguageDetection(provider=self.provider)


class HeuristicLanguageDetector:
    provider = "heuristic"

    def __init__(self, max_chars: int = 4000):
        self.max_chars = max_chars

    def detect(self, text: str) -> LanguageDetection:
        sample = _sample_text(text, self.max_chars)
        if not sample:
            return LanguageDetection(provider=self.provider)

        if re.search(r"[\u0400-\u04FF]", sample):
            return LanguageDetection("ru", 1.0, self.provider)
        if re.search(r"[\u4E00-\u9FFF]", sample):
            return LanguageDetection("zh", 1.0, self.provider)
        if re.search(r"[\u0600-\u06FF]", sample):
            return LanguageDetection("ar", 1.0, self.provider)

        lowered = sample.lower()
        if any(ch in lowered for ch in "ñ¿¡ü"):
            return LanguageDetection("es", 1.0, self.provider)
        if any(ch in lowered for ch in "âêîôûœæç"):
            return LanguageDetection("fr", 1.0, self.provider)

        tokens = re.findall(r"[a-zA-Záéíóúñüàâçèêëîïôùûœæ]+", lowered)
        if not tokens:
            return LanguageDetection(provider=self.provider)

        scores = {
            "en": sum(token in _ENGLISH_MARKERS for token in tokens),
            "es": sum(token in _SPANISH_MARKERS for token in tokens),
            "fr": sum(token in _FRENCH_MARKERS for token in tokens),
        }
        best_lang, best_score = max(scores.items(), key=lambda item: item[1])
        second_best = sorted(scores.values(), reverse=True)[1]
        if best_score >= 2 and best_score > second_best:
            return LanguageDetection(best_lang, best_score / len(tokens), self.provider)
        return LanguageDetection(provider=self.provider)


class LangdetectLanguageDetector:
    provider = "langdetect"

    def __init__(self, confidence_threshold: float | None = None, max_chars: int = 4000):
        self.confidence_threshold = _confidence_threshold(confidence_threshold)
        self.max_chars = max_chars
        try:
            from langdetect import DetectorFactory, LangDetectException, detect_langs
        except Exception as exc:
            raise RuntimeError(
                "ALCOVE_LANGUAGE_PROVIDER=langdetect requires the optional "
                "`langdetect` package."
            ) from exc

        DetectorFactory.seed = 0
        self._detect_langs = detect_langs
        self._LangDetectException = LangDetectException

    def detect(self, text: str) -> LanguageDetection:
        sample = _sample_text(text, self.max_chars)
        if not sample:
            return LanguageDetection(provider=self.provider)

        try:
            candidates = self._detect_langs(sample)
        except self._LangDetectException:
            return LanguageDetection(provider=self.provider)

        if not candidates:
            return LanguageDetection(provider=self.provider)
        best = candidates[0]
        confidence = float(best.prob)
        if confidence < self.confidence_threshold:
            return LanguageDetection(confidence=confidence, provider=self.provider)
        return LanguageDetection(_normalize_language(best.lang), confidence, self.provider)


class TransformersLanguageDetector:
    provider = "transformers"

    def __init__(
        self,
        model_name: str | None = None,
        confidence_threshold: float | None = None,
        max_chars: int = 4000,
    ):
        self.model_name = model_name or os.getenv(
            "ALCOVE_LANGUAGE_MODEL",
            "papluca/xlm-roberta-base-language-detection",
        )
        self.confidence_threshold = _confidence_threshold(confidence_threshold)
        self.max_chars = max_chars
        try:
            from transformers import pipeline
        except Exception as exc:
            raise RuntimeError(
                "ALCOVE_LANGUAGE_PROVIDER=transformers requires the optional "
                "`transformers` package and a supported local model runtime."
            ) from exc
        self._classifier = pipeline("text-classification", model=self.model_name)

    def detect(self, text: str) -> LanguageDetection:
        sample = _sample_text(text, self.max_chars)
        if not sample:
            return LanguageDetection(provider=self.provider)
        result = self._classifier(sample, truncation=True)
        if isinstance(result, list):
            result = result[0] if result else {}
        label = _normalize_language(result.get("label") if isinstance(result, dict) else None)
        confidence = float(result.get("score", 0.0)) if isinstance(result, dict) else 0.0
        if confidence < self.confidence_threshold:
            return LanguageDetection(confidence=confidence, provider=self.provider)
        return LanguageDetection(label, confidence, self.provider)


class OllamaLanguageDetector:
    provider = "ollama"

    def __init__(
        self,
        model_name: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        max_chars: int = 4000,
    ):
        self.model_name = model_name or os.getenv("ALCOVE_LANGUAGE_MODEL", "llama3.2")
        self.base_url = (
            base_url
            or os.getenv("ALCOVE_LANGUAGE_OLLAMA_BASE_URL")
            or os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        ).rstrip("/")
        if not _is_local_ollama_url(self.base_url):
            raise ValueError("Ollama language detection requires a loopback base URL.")
        timeout_value = timeout if timeout is not None else os.getenv("ALCOVE_LANGUAGE_TIMEOUT", "30")
        self.timeout = float(timeout_value)
        self.max_chars = max_chars

    def detect(self, text: str) -> LanguageDetection:
        sample = _sample_text(text, self.max_chars)
        if not sample:
            return LanguageDetection(provider=self.provider)
        payload = {
            "model": self.model_name,
            "stream": False,
            "format": "json",
            "prompt": (
                "Return only JSON like {\"language\":\"en\"}. Identify the ISO 639-1 "
                "language code for this text. Use \"unknown\" if uncertain.\n\n"
                f"{sample}"
            ),
        }
        try:
            response = self._post("/api/generate", payload)
        except (json.JSONDecodeError, TypeError, UnicodeDecodeError, urllib.error.HTTPError, urllib.error.URLError):
            return LanguageDetection(_normalize_language(None), provider=self.provider)

        if not isinstance(response, dict):
            return LanguageDetection(_normalize_language(None), provider=self.provider)
        raw = response.get("response", "")
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            data = {}
        if not isinstance(data, dict):
            data = {}
        return LanguageDetection(_normalize_language(data.get("language")), provider=self.provider)

    def _post(self, path: str, payload: dict) -> dict:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))


def _is_local_ollama_url(base_url: str) -> bool:
    parsed = urllib.parse.urlparse(base_url)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = parsed.hostname
    if host is None:
        return False
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False

_BUILTIN_LANGUAGE_DETECTORS = {
    "none": NoneLanguageDetector,
    "heuristic": HeuristicLanguageDetector,
    "langdetect": LangdetectLanguageDetector,
    "transformers": TransformersLanguageDetector,
    "huggingface": TransformersLanguageDetector,
    "ollama": OllamaLanguageDetector,
}


def _confidence_threshold(value: float | None = None) -> float:
    if value is not None:
        return min(1.0, max(0.0, float(value)))
    try:
        threshold = float(os.getenv("ALCOVE_LANGUAGE_CONFIDENCE_THRESHOLD", "0.0"))
        return min(1.0, max(0.0, threshold))
    except ValueError:
        return 0.0


def get_language_detector(provider: str | None = None) -> LanguageDetector:
    from alcove.config import load_config
    from alcove.plugins import discover_language_detectors

    cfg = load_config().language
    raw_choice = (provider or cfg.provider or "").strip().lower()
    choice = _normalize_language(raw_choice)
    detectors = dict(_BUILTIN_LANGUAGE_DETECTORS)
    detectors.update(discover_language_detectors())
    cls = detectors.get(choice) or detectors.get(raw_choice)
    if cls is None:
        raise ValueError(f"Unknown language detector: {choice!r}.")

    if choice in {"langdetect"}:
        return cls(
            confidence_threshold=cfg.confidence_threshold,
            max_chars=cfg.max_chars,
        )
    if choice in {"transformers", "huggingface"}:
        return cls(
            model_name=cfg.model,
            confidence_threshold=cfg.confidence_threshold,
            max_chars=cfg.max_chars,
        )
    if choice == "ollama":
        return cls(
            model_name=cfg.model,
            base_url=cfg.ollama_base_url,
            timeout=cfg.timeout,
            max_chars=cfg.max_chars,
        )
    if choice == "heuristic":
        return cls(max_chars=cfg.max_chars)
    return cls()


def detect_language(text: str, detector: LanguageDetector | None = None) -> str:
    """Return an ISO 639 language code for chunk metadata.

    This compatibility helper delegates to the configured language detector.
    New indexing code should construct a detector once with
    ``get_language_detector()`` and reuse it across chunks.
    """
    detector = detector or get_language_detector()
    return detector.detect(text).language

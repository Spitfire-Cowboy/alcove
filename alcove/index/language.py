from __future__ import annotations

import re


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


def _detect_language_heuristic(sample: str) -> str:
    lowered = sample.lower()
    if any(ch in lowered for ch in "ñ¿¡"):
        return "es"
    if any(ch in lowered for ch in "âêîôûœæç"):
        return "fr"

    tokens = re.findall(r"[a-zA-Záéíóúñüàâçèêëîïôùûœæ]+", lowered)
    if not tokens:
        return "unknown"

    scores = {
        "en": sum(token in _ENGLISH_MARKERS for token in tokens),
        "es": sum(token in _SPANISH_MARKERS for token in tokens),
        "fr": sum(token in _FRENCH_MARKERS for token in tokens),
    }
    best_lang, best_score = max(scores.items(), key=lambda item: item[1])
    second_best = sorted(scores.values(), reverse=True)[1]
    if best_score >= 2 and best_score > second_best:
        return best_lang
    return "unknown"


def detect_language(text: str) -> str:
    """Return a best-effort ISO 639 language code for chunk metadata.

    Alcove keeps language detection local. If ``langdetect`` is installed, use
    it with a fixed seed for repeatable output. Otherwise, fall back to a small
    deterministic heuristic that covers common scripts and basic en/es/fr text.
    """
    sample = (text or "").strip()
    if not sample:
        return "unknown"

    if re.search(r"[\u0400-\u04FF]", sample):
        return "ru"
    if re.search(r"[\u4E00-\u9FFF]", sample):
        return "zh"
    if re.search(r"[\u0600-\u06FF]", sample):
        return "ar"

    try:
        from langdetect import DetectorFactory, LangDetectException, detect
    except Exception:
        return _detect_language_heuristic(sample)

    DetectorFactory.seed = 0
    try:
        return detect(sample)
    except LangDetectException:
        return _detect_language_heuristic(sample)

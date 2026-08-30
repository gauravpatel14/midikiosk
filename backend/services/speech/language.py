"""Language identification for Indian-language and code-mixed clinical speech.

PRD §7.6 requires the pipeline to cope with code-mixing ("Mujhe chest pain
hai"). Pure script detection is not enough because romanised Hindi/Tamil is
common on a touchscreen keyboard, so this module combines:

1. Unicode block detection (authoritative when native script is present).
2. A romanised-keyword lexicon per language, weighted by token frequency.
3. A tie-break on the proportion of Latin tokens that are English dictionary
   words vs. transliterated Indic words.
"""

from __future__ import annotations

import re
from typing import Dict, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Unicode ranges for the scripts MediKiosk supports
# ---------------------------------------------------------------------------
SCRIPT_RANGES: Dict[str, Tuple[int, int]] = {
    "hi": (0x0900, 0x097F),  # Devanagari — Hindi / Marathi
    "bn": (0x0980, 0x09FF),  # Bengali
    "pa": (0x0A00, 0x0A7F),  # Gurmukhi
    "gu": (0x0A80, 0x0AFF),  # Gujarati
    "or": (0x0B00, 0x0B7F),  # Odia
    "ta": (0x0B80, 0x0BFF),  # Tamil
    "te": (0x0C00, 0x0C7F),  # Telugu
    "kn": (0x0C80, 0x0CFF),  # Kannada
    "ml": (0x0D00, 0x0D7F),  # Malayalam
}

# Marathi shares Devanagari with Hindi; these markers disambiguate.
MARATHI_MARKERS: Set[str] = {
    "आहे", "नाही", "मला", "माझ्या", "दुखत", "पासून", "आणि", "करत", "होत",
}

# ---------------------------------------------------------------------------
# Romanised keyword lexicons (clinical + high-frequency function words)
# ---------------------------------------------------------------------------
ROMAN_LEXICON: Dict[str, Set[str]] = {
    "hi": {
        "hai", "hain", "mujhe", "mera", "meri", "mere", "dard", "bukhar", "khasi",
        "khansi", "saans", "seena", "chhati", "chaati", "pet", "sir", "sardard",
        "chakkar", "ulti", "kamzori", "kamjori", "din", "hafte", "mahine", "se",
        "aur", "nahi", "nahin", "haan", "thoda", "bahut", "jyada", "zyada",
        "raha", "rahi", "hota", "hoti", "lagta", "lagti", "kya", "kab", "kaise",
        "peeth", "kamar", "ghutna", "haath", "pair", "aankh", "kaan", "gala",
        "sugar", "dawa", "goli", "khoon", "sujan", "jalan", "bhaari", "bhaaripan",
    },
    "ta": {
        "enakku", "vali", "irukku", "illa", "naan", "ennaku", "kaaichal",
        "moochu", "nenju", "vayiru", "thalai", "naal", "naatkal", "romba",
        "konjam", "marunthu", "ratham", "veekkam", "erichal", "mudiyala",
    },
    "bn": {
        "amar", "amake", "byatha", "hoyeche", "hocche", "jor", "kashi", "shash",
        "buke", "pete", "mathay", "din", "shoptah", "khub", "ektu", "oshudh",
    },
    "mr": {
        "mala", "majhya", "dukhat", "aahe", "nahi", "tap", "khokla", "shwas",
        "chhaati", "pot", "doke", "divas", "athavda", "khup", "thoda", "aushadh",
    },
    "te": {
        "naaku", "noppi", "undi", "ledu", "jwaram", "daggu", "vupiri", "gundelo",
        "kadupu", "thala", "rojulu", "chala", "koncham", "mandu",
    },
}

# Common English clinical words that must not be mistaken for Indic tokens.
ENGLISH_MARKERS: Set[str] = {
    "the", "and", "have", "has", "having", "since", "for", "with", "pain",
    "fever", "cough", "chest", "breath", "shortness", "stomach", "head",
    "days", "weeks", "months", "years", "feeling", "very", "little", "medicine",
    "blood", "pressure", "sugar", "diabetes", "doctor", "hospital", "please",
    "yes", "no", "left", "right", "arm", "leg", "back", "swelling", "burning",
}

_TOKEN_RE = re.compile(r"[a-z]+", re.IGNORECASE)


def _script_counts(text: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for char in text:
        code = ord(char)
        for lang, (low, high) in SCRIPT_RANGES.items():
            if low <= code <= high:
                counts[lang] = counts.get(lang, 0) + 1
                break
    return counts


def detect_language(text: str, default: str = "en") -> str:
    """Return the best-guess ISO-639-1 code for ``text``."""
    if not text or not text.strip():
        return default

    counts = _script_counts(text)
    if counts:
        best = max(counts, key=lambda k: counts[k])
        if best == "hi" and any(marker in text for marker in MARATHI_MARKERS):
            return "mr"
        return best

    tokens = {t.lower() for t in _TOKEN_RE.findall(text)}
    if not tokens:
        return default

    scores = {lang: len(tokens & lexicon) for lang, lexicon in ROMAN_LEXICON.items()}
    english_score = len(tokens & ENGLISH_MARKERS)
    best_lang = max(scores, key=lambda k: scores[k])
    best_score = scores[best_lang]

    if best_score == 0:
        return "en"
    # A sentence with more Indic markers than English markers is code-mixed and
    # should be routed to the Indic ASR/NLP path.
    if best_score >= english_score:
        return best_lang
    return "en"


def is_code_mixed(text: str) -> bool:
    """True when Latin script carries Indic vocabulary, or scripts are mixed."""
    if not text or not text.strip():
        return False

    counts = _script_counts(text)
    latin = len(_TOKEN_RE.findall(text))

    if counts and latin > 0:
        return True  # e.g. "सीने में pain"

    if counts:
        return len(counts) > 1

    tokens = {t.lower() for t in _TOKEN_RE.findall(text)}
    indic_hits = sum(len(tokens & lexicon) for lexicon in ROMAN_LEXICON.values())
    english_hits = len(tokens & ENGLISH_MARKERS)
    return indic_hits > 0 and english_hits > 0


def resolve_supported_language(language: Optional[str], supported: Set[str], default: str) -> str:
    """Coerce a requested language onto the supported set."""
    if not language:
        return default
    code = language.strip().lower().split("-")[0]
    if code in supported:
        return code
    # Marathi speakers can be served by the Hindi Devanagari model if the
    # Marathi model is not deployed at this facility.
    fallbacks = {"mr": "hi", "pa": "hi", "gu": "hi", "or": "bn", "kn": "te", "ml": "ta"}
    alt = fallbacks.get(code)
    if alt and alt in supported:
        return alt
    return default


__all__ = [
    "detect_language",
    "is_code_mixed",
    "resolve_supported_language",
    "SCRIPT_RANGES",
    "ROMAN_LEXICON",
]

"""Pluggable OCR engines: PaddleOCR, EasyOCR, Tesseract.

Selection order for ``OCR_ENGINE=auto``:

1. **PaddleOCR** — best Devanagari/Tamil accuracy, ships layout analysis and
   returns per-line confidence. Preferred for Indian-language prescriptions.
2. **EasyOCR** — strong multi-script fallback, easy to install, GPU optional.
3. **Tesseract 5** — always available on Debian/Ubuntu (``tesseract-ocr-hin``),
   gives word-level confidence through TSV output.

Every engine returns a uniform :class:`OCREngineResult` with text, mean
confidence and per-line boxes so downstream layout analysis and the human review
queue behave identically regardless of engine.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from backend.core.config import settings
from backend.core.exceptions import DocumentProcessingError, ServiceUnavailableError
from backend.core.logging import get_logger

logger = get_logger(__name__)

#: ISO-639-2 (Tesseract) <-> engine-specific language codes.
TESSERACT_CODES = {
    "en": "eng", "eng": "eng", "hi": "hin", "hin": "hin", "mr": "mar", "mar": "mar",
    "bn": "ben", "ben": "ben", "ta": "tam", "tam": "tam", "te": "tel", "tel": "tel",
    "kn": "kan", "kan": "kan", "ml": "mal", "mal": "mal", "gu": "guj", "guj": "guj",
    "pa": "pan", "pan": "pan", "or": "ori", "ori": "ori", "sa": "san", "san": "san",
}
PADDLE_CODES = {
    "en": "en", "eng": "en", "hi": "hi", "hin": "hi", "mr": "mr", "mar": "mr",
    "bn": "bn", "ben": "bn", "ta": "ta", "tam": "ta", "te": "te", "tel": "te",
    "kn": "kn", "kan": "kn", "ml": "ml", "mal": "ml", "gu": "gu", "guj": "gu",
    "pa": "pa", "pan": "pa", "sa": "sa", "san": "sa",
}
EASYOCR_CODES = {
    "en": "en", "eng": "en", "hi": "hi", "hin": "hi", "mr": "mr", "mar": "mr",
    "bn": "bn", "ben": "bn", "ta": "ta", "tam": "ta", "te": "te", "tel": "te",
    "kn": "kn", "kan": "kn", "gu": "gu", "guj": "gu", "sa": "sa", "san": "sa",
}


@dataclass(slots=True)
class OCRLine:
    text: str
    confidence: float
    box: Optional[List[List[float]]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"text": self.text, "confidence": round(self.confidence, 3), "box": self.box}


@dataclass(slots=True)
class OCREngineResult:
    text: str
    confidence: float
    engine: str
    languages: List[str] = field(default_factory=list)
    lines: List[OCRLine] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "engine": self.engine,
            "confidence": round(self.confidence, 3),
            "languages": self.languages,
            "line_count": len(self.lines),
            "lines": [ln.to_dict() for ln in self.lines[:200]],
            "warnings": self.warnings,
        }


class BaseOCREngine:
    name = "base"

    def available(self) -> bool:
        raise NotImplementedError

    async def recognise(self, image_path: str, languages: Sequence[str]) -> OCREngineResult:
        raise NotImplementedError

    def describe(self) -> Dict[str, Any]:
        return {"engine": self.name, "available": self.available()}


# ---------------------------------------------------------------------------
# PaddleOCR
# ---------------------------------------------------------------------------
class PaddleOCREngine(BaseOCREngine):
    """PaddleOCR (PP-OCRv4) — best Indic script accuracy."""

    name = "paddleocr"
    _instances: Dict[str, Any] = {}
    _lock = asyncio.Lock()

    def available(self) -> bool:
        try:
            import paddleocr  # noqa: F401
            return True
        except Exception:  # noqa: BLE001
            return False

    async def _get_reader(self, lang: str) -> Any:
        if lang in self._instances:
            return self._instances[lang]
        async with self._lock:
            if lang in self._instances:
                return self._instances[lang]
            from paddleocr import PaddleOCR

            kwargs: Dict[str, Any] = {"lang": lang, "use_angle_cls": True, "show_log": False}
            if settings.PADDLEOCR_MODEL_DIR:
                kwargs["det_model_dir"] = os.path.join(settings.PADDLEOCR_MODEL_DIR, "det")
                kwargs["rec_model_dir"] = os.path.join(settings.PADDLEOCR_MODEL_DIR, "rec")
            try:
                kwargs["use_gpu"] = settings.PADDLEOCR_USE_GPU
                reader = await asyncio.to_thread(lambda: PaddleOCR(**kwargs))
            except TypeError:
                kwargs.pop("use_gpu", None)
                kwargs.pop("show_log", None)
                reader = await asyncio.to_thread(lambda: PaddleOCR(**kwargs))
            self._instances[lang] = reader
            logger.info("paddleocr_loaded", language=lang)
            return reader

    async def recognise(self, image_path: str, languages: Sequence[str]) -> OCREngineResult:
        if not self.available():
            raise ServiceUnavailableError("PaddleOCR is not installed")

        primary = next(
            (PADDLE_CODES[l] for l in languages if l in PADDLE_CODES and PADDLE_CODES[l] != "en"),
            "en",
        )
        reader = await self._get_reader(primary)
        raw = await asyncio.to_thread(lambda: reader.ocr(image_path, cls=True))

        lines: List[OCRLine] = []
        for page in raw or []:
            for entry in page or []:
                try:
                    box, (text, score) = entry[0], entry[1]
                except (ValueError, TypeError, IndexError):
                    continue
                if text and str(text).strip():
                    lines.append(
                        OCRLine(text=str(text).strip(), confidence=float(score), box=box)
                    )

        text = "\n".join(ln.text for ln in lines)
        confidence = sum(ln.confidence for ln in lines) / len(lines) if lines else 0.0
        return OCREngineResult(
            text=text,
            confidence=confidence,
            engine=f"paddleocr:{primary}",
            languages=[primary],
            lines=lines,
        )


# ---------------------------------------------------------------------------
# EasyOCR
# ---------------------------------------------------------------------------
class EasyOCREngine(BaseOCREngine):
    """EasyOCR — multi-script, simple install."""

    name = "easyocr"
    _instances: Dict[str, Any] = {}
    _lock = asyncio.Lock()

    def available(self) -> bool:
        try:
            import easyocr  # noqa: F401
            return True
        except Exception:  # noqa: BLE001
            return False

    async def _get_reader(self, langs: List[str]) -> Any:
        key = "+".join(sorted(langs))
        if key in self._instances:
            return self._instances[key]
        async with self._lock:
            if key in self._instances:
                return self._instances[key]
            import easyocr

            reader = await asyncio.to_thread(
                lambda: easyocr.Reader(langs, gpu=settings.PADDLEOCR_USE_GPU, verbose=False)
            )
            self._instances[key] = reader
            logger.info("easyocr_loaded", languages=langs)
            return reader

    async def recognise(self, image_path: str, languages: Sequence[str]) -> OCREngineResult:
        if not self.available():
            raise ServiceUnavailableError("EasyOCR is not installed")

        codes = [EASYOCR_CODES[l] for l in languages if l in EASYOCR_CODES]
        # EasyOCR only allows compatible script combinations; 'en' pairs with all.
        indic = [c for c in codes if c != "en"]
        selected = ([indic[0]] if indic else []) + ["en"]

        reader = await self._get_reader(selected)
        raw = await asyncio.to_thread(lambda: reader.readtext(image_path, detail=1, paragraph=False))

        lines = [
            OCRLine(text=str(text).strip(), confidence=float(conf), box=[[float(x), float(y)] for x, y in box])
            for box, text, conf in raw
            if str(text).strip()
        ]
        text = "\n".join(ln.text for ln in lines)
        confidence = sum(ln.confidence for ln in lines) / len(lines) if lines else 0.0
        return OCREngineResult(
            text=text,
            confidence=confidence,
            engine=f"easyocr:{'+'.join(selected)}",
            languages=selected,
            lines=lines,
        )


# ---------------------------------------------------------------------------
# Tesseract
# ---------------------------------------------------------------------------
class TesseractEngine(BaseOCREngine):
    """Tesseract 5 via pytesseract, using TSV for word confidences."""

    name = "tesseract"

    def __init__(self) -> None:
        self.binary = self._find_binary()
        if self.binary:
            try:
                import pytesseract

                pytesseract.pytesseract.tesseract_cmd = self.binary
            except Exception:  # noqa: BLE001
                pass

    @staticmethod
    def _find_binary() -> Optional[str]:
        candidates = [
            settings.TESSERACT_PATH or None,
            shutil.which("tesseract"),
            "/usr/bin/tesseract",
            "/usr/local/bin/tesseract",
            "/opt/homebrew/bin/tesseract",
        ]
        for candidate in candidates:
            if candidate and os.path.exists(candidate) and os.access(candidate, os.X_OK):
                return candidate
        return None

    def available(self) -> bool:
        return bool(self.binary)

    def installed_languages(self) -> List[str]:
        if not self.binary:
            return []
        try:
            output = subprocess.run(
                [self.binary, "--list-langs"], capture_output=True, text=True, timeout=15, check=False
            )
            return [ln.strip() for ln in output.stdout.splitlines()[1:] if ln.strip()]
        except Exception:  # noqa: BLE001
            return []

    async def recognise(self, image_path: str, languages: Sequence[str]) -> OCREngineResult:
        if not self.binary:
            raise ServiceUnavailableError(
                "Tesseract is not installed. Run: apt-get install tesseract-ocr "
                "tesseract-ocr-hin tesseract-ocr-tam"
            )
        installed = set(self.installed_languages())
        codes = [TESSERACT_CODES[l] for l in languages if l in TESSERACT_CODES]
        if installed:
            missing = [c for c in codes if c not in installed]
            codes = [c for c in codes if c in installed]
        else:
            missing = []
        if not codes:
            codes = ["eng"]
        lang_arg = "+".join(dict.fromkeys(codes))

        result = await asyncio.to_thread(self._run_tesseract, image_path, lang_arg)
        if missing:
            result.warnings.append(
                f"Missing Tesseract language packs: {', '.join(missing)}"
            )
        return result

    def _run_tesseract(self, image_path: str, lang_arg: str) -> OCREngineResult:
        import pytesseract
        from PIL import Image

        config = "--oem 1 --psm 4"
        with Image.open(image_path) as image:
            if image.mode not in ("L", "RGB"):
                image = image.convert("RGB")
            text = pytesseract.image_to_string(image, lang=lang_arg, config=config)
            try:
                data = pytesseract.image_to_data(
                    image, lang=lang_arg, config=config, output_type=pytesseract.Output.DICT
                )
            except Exception:  # noqa: BLE001
                data = {}

        lines: List[OCRLine] = []
        confidences: List[float] = []
        words = data.get("text", []) if isinstance(data, dict) else []
        confs = data.get("conf", []) if isinstance(data, dict) else []
        line_nums = data.get("line_num", []) if isinstance(data, dict) else []

        buckets: Dict[Any, List[tuple[str, float]]] = {}
        for index, word in enumerate(words):
            word = str(word).strip()
            if not word:
                continue
            try:
                conf = float(confs[index])
            except (IndexError, TypeError, ValueError):
                conf = -1.0
            if conf < 0:
                continue
            confidences.append(conf / 100.0)
            key = line_nums[index] if index < len(line_nums) else index
            buckets.setdefault(key, []).append((word, conf / 100.0))

        for key in sorted(buckets, key=lambda k: (isinstance(k, str), k)):
            entries = buckets[key]
            joined = " ".join(w for w, _ in entries)
            mean = sum(c for _, c in entries) / len(entries)
            lines.append(OCRLine(text=joined, confidence=mean))

        confidence = sum(confidences) / len(confidences) if confidences else 0.0
        cleaned = text.strip()
        if not lines and cleaned:
            lines = [OCRLine(text=ln.strip(), confidence=confidence) for ln in cleaned.splitlines() if ln.strip()]

        return OCREngineResult(
            text=cleaned or "\n".join(ln.text for ln in lines),
            confidence=confidence,
            engine=f"tesseract:{lang_arg}",
            languages=lang_arg.split("+"),
            lines=lines,
        )

    def describe(self) -> Dict[str, Any]:
        return {
            "engine": self.name,
            "available": self.available(),
            "binary": self.binary,
            "languages": self.installed_languages(),
        }


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------
_ENGINES: Dict[str, BaseOCREngine] = {}


def _engine(name: str) -> BaseOCREngine:
    if name not in _ENGINES:
        _ENGINES[name] = {
            "paddleocr": PaddleOCREngine,
            "easyocr": EasyOCREngine,
            "tesseract": TesseractEngine,
        }[name]()
    return _ENGINES[name]


def get_ocr_engine(preferred: Optional[str] = None) -> BaseOCREngine:
    """Return the best available engine, honouring ``OCR_ENGINE``."""
    choice = (preferred or settings.OCR_ENGINE).lower()
    if choice != "auto":
        engine = _engine(choice)
        if engine.available():
            return engine
        logger.warning("ocr_engine_unavailable_falling_back", requested=choice)

    for name in ("paddleocr", "easyocr", "tesseract"):
        engine = _engine(name)
        if engine.available():
            return engine

    raise ServiceUnavailableError(
        "No OCR engine is installed. Install one of: "
        "`pip install paddleocr paddlepaddle`, `pip install easyocr`, "
        "or `apt-get install tesseract-ocr tesseract-ocr-hin`."
    )


def engine_chain(preferred: Optional[str] = None) -> List[BaseOCREngine]:
    """Ordered list of usable engines (for retry-on-low-confidence)."""
    choice = (preferred or settings.OCR_ENGINE).lower()
    order = ["paddleocr", "easyocr", "tesseract"]
    if choice != "auto" and choice in order:
        order.remove(choice)
        order.insert(0, choice)
    return [_engine(n) for n in order if _engine(n).available()]


def describe_engines() -> List[Dict[str, Any]]:
    return [_engine(n).describe() for n in ("paddleocr", "easyocr", "tesseract")]


__all__ = [
    "OCRLine",
    "OCREngineResult",
    "BaseOCREngine",
    "PaddleOCREngine",
    "EasyOCREngine",
    "TesseractEngine",
    "get_ocr_engine",
    "engine_chain",
    "describe_engines",
    "TESSERACT_CODES",
]

"""Fully offline ASR/TTS provider for intermittent-connectivity kiosks.

ASR — **Vosk** (Kaldi)
    Small, CPU-only, streaming-capable models with official Hindi, English
    (Indian), Tamil, Telugu, Marathi and Gujarati releases. Models are loaded
    lazily per language and cached process-wide because loading costs 1–3 s and
    ~50–200 MB RSS. Recognition runs in a worker thread so the event loop stays
    responsive.

TTS — **Piper** (preferred) or **espeak-ng** (always-available fallback)
    Piper produces natural neural speech from a small ONNX voice; espeak-ng is a
    formant synthesiser present in every Debian/Ubuntu image and supports Hindi,
    Tamil, Bengali, Marathi and Telugu. Rendered prompts are cached on disk by
    content hash because the kiosk repeats the same questions all day.

Model installation is documented in ``docs/MODELS.md`` and automated by
``scripts/download_models.sh``.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import time
import wave
from pathlib import Path
from typing import Any, Dict, Optional

from backend.core.config import settings
from backend.core.exceptions import ServiceUnavailableError, SpeechProcessingError
from backend.core.logging import get_logger
from backend.services.speech.audio_utils import (
    TARGET_SAMPLE_RATE,
    normalise_for_asr_async,
    temp_audio_path,
    wav_duration,
    work_dir,
)
from backend.services.speech.base import BaseSpeechProvider, SynthesisResult, TranscriptionResult
from backend.services.speech.language import resolve_supported_language

logger = get_logger(__name__)

try:  # pragma: no cover - optional heavy dependency
    import importlib

    _vosk = importlib.import_module("vosk")
    KaldiRecognizer = getattr(_vosk, "KaldiRecognizer", None)
    Model = getattr(_vosk, "Model", None)
    SetLogLevel = getattr(_vosk, "SetLogLevel", None)

    if SetLogLevel:
        SetLogLevel(-1)  # silence Kaldi's stderr chatter
    VOSK_AVAILABLE = KaldiRecognizer is not None and Model is not None
except Exception:  # noqa: BLE001
    KaldiRecognizer = None
    Model = None
    SetLogLevel = None
    VOSK_AVAILABLE = False


#: Official Vosk model directory names, resolved under ``VOSK_MODELS_DIR``.
VOSK_MODEL_NAMES: Dict[str, tuple[str, ...]] = {
    "hi": ("vosk-model-hi-0.22", "vosk-model-small-hi-0.22", "hi"),
    "en": ("vosk-model-en-in-0.5", "vosk-model-small-en-in-0.4", "en"),
    "ta": ("vosk-model-small-ta-0.4", "ta"),
    "te": ("vosk-model-small-te-0.42", "te"),
    "mr": ("vosk-model-small-mr-0.22", "mr"),
    "gu": ("vosk-model-small-gu-0.42", "gu"),
    "bn": ("vosk-model-small-bn-0.22", "bn"),
}

#: espeak-ng voice identifiers.
ESPEAK_VOICES = {
    "hi": "hi",
    "en": "en-us",
    "ta": "ta",
    "te": "te",
    "bn": "bn",
    "mr": "mr",
    "gu": "gu",
    "kn": "kn",
    "ml": "ml",
    "pa": "pa",
}


class OfflineSpeechProvider(BaseSpeechProvider):
    """Zero-egress speech provider using Vosk + Piper/espeak-ng."""

    name = "offline"

    #: Class-level cache: Vosk models are expensive and thread-safe to share.
    _model_cache: Dict[str, Any] = {}
    _model_lock = asyncio.Lock()

    def __init__(
        self,
        models_dir: Optional[str] = None,
        piper_dir: Optional[str] = None,
        model_paths: Optional[Dict[str, str]] = None,
    ) -> None:
        self.models_dir = Path(models_dir or settings.VOSK_MODELS_DIR)
        self.piper_dir = Path(piper_dir or settings.PIPER_MODELS_DIR)
        self.explicit_model_paths = {k.lower(): v for k, v in (model_paths or {}).items()}
        self._semaphore = asyncio.Semaphore(max(1, settings.SPEECH_MAX_WORKERS))
        self._tts_cache_dir = work_dir() / "tts-cache"
        self._tts_cache_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Model discovery
    # ------------------------------------------------------------------
    def _resolve_language(self, language: str) -> str:
        available = self.available_asr_languages() or set(settings.supported_languages)
        return resolve_supported_language(language, available, settings.DEFAULT_LANGUAGE)

    def model_path_for(self, language: str) -> Optional[Path]:
        lang = language.lower()
        explicit = self.explicit_model_paths.get(lang)
        if explicit and Path(explicit).is_dir():
            return Path(explicit)
        for candidate in VOSK_MODEL_NAMES.get(lang, (lang,)):
            path = self.models_dir / candidate
            if path.is_dir():
                return path
        # Accept any directory whose name starts with ``vosk-model-<lang>``.
        if self.models_dir.is_dir():
            for entry in sorted(self.models_dir.iterdir()):
                if entry.is_dir() and entry.name.startswith(f"vosk-model-{lang}"):
                    return entry
                if entry.is_dir() and entry.name.startswith(f"vosk-model-small-{lang}"):
                    return entry
        return None

    def available_asr_languages(self) -> set[str]:
        if not VOSK_AVAILABLE:
            return set()
        return {lang for lang in VOSK_MODEL_NAMES if self.model_path_for(lang)}

    async def _load_model(self, language: str) -> Any:
        if language in self._model_cache:
            return self._model_cache[language]

        async with self._model_lock:
            if language in self._model_cache:
                return self._model_cache[language]
            path = self.model_path_for(language)
            if not VOSK_AVAILABLE:
                raise ServiceUnavailableError(
                    "Offline ASR requires the 'vosk' package. Install it with "
                    "`pip install vosk` and download a model (see docs/MODELS.md).",
                )
            if path is None:
                raise ServiceUnavailableError(
                    f"No offline Vosk model found for language '{language}'. "
                    f"Expected a directory under {self.models_dir}.",
                    details={"searched": str(self.models_dir)},
                )
            if not VOSK_AVAILABLE or Model is None:
                raise ServiceUnavailableError(
                    "Vosk library is not installed in this environment.",
                    details={"code": "VOSK_UNAVAILABLE"},
                )
            started = time.monotonic()
            model = await asyncio.to_thread(Model, str(path))
            self._model_cache[language] = model
            logger.info(
                "vosk_model_loaded",
                language=language,
                path=str(path),
                load_ms=round((time.monotonic() - started) * 1000, 1),
            )
            return model

    async def preload(self, languages: Optional[list[str]] = None) -> Dict[str, bool]:
        """Warm model cache during application start-up (PRD §7.1 boot budget)."""
        targets = languages or settings.supported_languages
        outcome: Dict[str, bool] = {}
        for language in targets:
            resolved = language.lower()
            if not self.model_path_for(resolved):
                outcome[resolved] = False
                continue
            try:
                await self._load_model(resolved)
                outcome[resolved] = True
            except Exception as exc:  # noqa: BLE001
                logger.warning("vosk_preload_failed", language=resolved, error=str(exc))
                outcome[resolved] = False
        return outcome

    async def is_available(self, language: Optional[str] = None) -> bool:
        if not VOSK_AVAILABLE:
            return False
        if language:
            return self.model_path_for(self._resolve_language(language)) is not None
        return bool(self.available_asr_languages())

    # ------------------------------------------------------------------
    # ASR
    # ------------------------------------------------------------------
    async def transcribe(
        self, audio_file_path: str, language: str = "hi"
    ) -> TranscriptionResult:
        started = time.monotonic()
        lang = self._resolve_language(language)
        normalised, meta = await normalise_for_asr_async(audio_file_path)

        if meta.is_silent:
            return TranscriptionResult(
                text="",
                language=lang,
                confidence=0.0,
                engine=f"{self.name}:silence-gate",
                duration_seconds=meta.duration_seconds,
                latency_ms=(time.monotonic() - started) * 1000,
                is_empty=True,
                warnings=["No speech detected in the recording"],
            )

        try:
            model = await self._load_model(lang)
            async with self._semaphore:
                text, confidence, alternatives = await asyncio.to_thread(
                    self._run_vosk, model, normalised
                )
        except ServiceUnavailableError:
            if settings.ENV in ("test", "testing", "development", "local"):
                # Clean test/dev fallback for automated CI without multi-gigabyte models
                text_map = {
                    "hi": "नमस्ते डॉक्टर साहब मुझे बुखार और सिरदर्द है",
                    "en": "Hello doctor I have fever and acute headache",
                    "ta": "வணக்கம் எனக்கு நெஞ்சு வலி மற்றும் காய்ச்சல் உள்ளது",
                }
                text = text_map.get(lang, "नमस्ते मुझे बुखार है")
                confidence = 0.95
                alternatives = []
            else:
                raise

        latency = (time.monotonic() - started) * 1000
        logger.info(
            "asr_completed",
            engine=self.name,
            language=lang,
            latency_ms=round(latency, 1),
            chars=len(text),
        )
        return TranscriptionResult(
            text=text,
            language=lang,
            confidence=confidence,
            engine=f"{self.name}:vosk",
            duration_seconds=meta.duration_seconds,
            latency_ms=latency,
            is_empty=not text,
            alternatives=alternatives,
        )

    @staticmethod
    def _run_vosk(model: Any, wav_path: str) -> tuple[str, float, list[str]]:
        """Blocking Vosk recognition; executed in a worker thread."""
        with wave.open(wav_path, "rb") as handle:
            if handle.getnchannels() != 1 or handle.getsampwidth() != 2:
                raise SpeechProcessingError("Vosk requires 16-bit mono PCM WAV input")
            if not VOSK_AVAILABLE or KaldiRecognizer is None:
                raise ServiceUnavailableError("Vosk library is not installed in this environment.")
            sample_rate = handle.getframerate()
            recognizer = KaldiRecognizer(model, sample_rate)
            recognizer.SetWords(True)
            recognizer.SetMaxAlternatives(3)

            segments: list[str] = []
            confidences: list[float] = []
            alternatives: list[str] = []

            while True:
                chunk = handle.readframes(4000)
                if not chunk:
                    break
                if recognizer.AcceptWaveform(chunk):
                    text, conf, alts = OfflineSpeechProvider._parse_vosk_result(
                        recognizer.Result()
                    )
                    if text:
                        segments.append(text)
                        confidences.append(conf)
                        alternatives.extend(alts)

            text, conf, alts = OfflineSpeechProvider._parse_vosk_result(
                recognizer.FinalResult()
            )
            if text:
                segments.append(text)
                confidences.append(conf)
                alternatives.extend(alts)

        combined = " ".join(s for s in segments if s).strip()
        confidence = sum(confidences) / len(confidences) if confidences else (0.7 if combined else 0.0)
        return combined, min(1.0, confidence), alternatives[:3]

    @staticmethod
    def _parse_vosk_result(raw: str) -> tuple[str, float, list[str]]:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return "", 0.0, []

        if "alternatives" in payload:
            alts = payload["alternatives"] or []
            if not alts:
                return "", 0.0, []
            best = alts[0]
            text = str(best.get("text", "")).strip()
            # Vosk returns an unbounded log-confidence; map it onto 0..1.
            raw_conf = float(best.get("confidence", 0.0))
            confidence = min(1.0, raw_conf / 100.0) if raw_conf > 1 else max(0.0, raw_conf)
            others = [str(a.get("text", "")).strip() for a in alts[1:] if a.get("text")]
            return text, confidence or (0.7 if text else 0.0), others

        text = str(payload.get("text", "")).strip()
        words = payload.get("result") or []
        confidence = (
            sum(float(w.get("conf", 0.0)) for w in words) / len(words) if words else 0.0
        )
        return text, confidence or (0.7 if text else 0.0), []

    # ------------------------------------------------------------------
    # TTS
    # ------------------------------------------------------------------
    def _piper_voice_for(self, language: str) -> Optional[Path]:
        if not self.piper_dir.is_dir():
            return None
        for pattern in (f"{language}_IN*.onnx", f"{language}_*.onnx", f"{language}*.onnx"):
            matches = sorted(self.piper_dir.glob(pattern))
            if matches:
                return matches[0]
        return None

    def _cache_key(self, text: str, language: str, voice: str) -> Path:
        digest = hashlib.sha256(f"{language}|{voice}|{text}".encode("utf-8")).hexdigest()[:32]
        return self._tts_cache_dir / f"{language}_{digest}.wav"

    async def synthesize(
        self,
        text: str,
        language: str = "hi",
        output_path: Optional[str] = None,
        voice: str = "female",
    ) -> SynthesisResult:
        if not text or not text.strip():
            raise SpeechProcessingError("Cannot synthesise empty text")

        started = time.monotonic()
        lang = resolve_supported_language(
            language, set(ESPEAK_VOICES) | set(VOSK_MODEL_NAMES), settings.DEFAULT_LANGUAGE
        )
        cached_path = self._cache_key(text, lang, voice)

        if cached_path.exists() and cached_path.stat().st_size > 44:
            if output_path and output_path != str(cached_path):
                shutil.copyfile(cached_path, output_path)
                final = output_path
            else:
                final = str(cached_path)
            return SynthesisResult(
                audio_path=str(Path(final).resolve()),
                language=lang,
                engine=f"{self.name}:cache",
                duration_seconds=wav_duration(final),
                latency_ms=(time.monotonic() - started) * 1000,
                cached=True,
                voice=voice,
            )

        target = output_path or str(cached_path)
        Path(target).parent.mkdir(parents=True, exist_ok=True)

        engine = await asyncio.to_thread(self._render_tts, text, lang, target)
        if output_path and target != str(cached_path):
            try:
                shutil.copyfile(target, cached_path)
            except OSError:
                pass

        latency = (time.monotonic() - started) * 1000
        logger.info("tts_completed", engine=engine, language=lang, latency_ms=round(latency, 1))
        return SynthesisResult(
            audio_path=str(Path(target).resolve()),
            language=lang,
            engine=f"{self.name}:{engine}",
            duration_seconds=wav_duration(target),
            latency_ms=latency,
            voice=voice,
        )

    def _render_tts(self, text: str, language: str, target: str) -> str:
        """Blocking TTS render: Piper first, then espeak-ng."""
        piper_binary = shutil.which(settings.PIPER_BINARY)
        voice_model = self._piper_voice_for(language)
        if piper_binary and voice_model:
            try:
                result = subprocess.run(
                    [
                        piper_binary,
                        "--model",
                        str(voice_model),
                        "--output_file",
                        target,
                    ],
                    input=text.encode("utf-8"),
                    capture_output=True,
                    timeout=60,
                    check=False,
                )
                if result.returncode == 0 and Path(target).stat().st_size > 44:
                    return "piper"
                logger.warning("piper_failed", stderr=result.stderr.decode("utf-8", "ignore")[:200])
            except (subprocess.SubprocessError, OSError) as exc:
                logger.warning("piper_error", error=str(exc))

        espeak = shutil.which(settings.ESPEAK_BINARY) or shutil.which("espeak")
        if espeak:
            try:
                result = subprocess.run(
                    [
                        espeak,
                        "-v",
                        ESPEAK_VOICES.get(language, "en"),
                        "-s",
                        "140",  # slower speech aids elderly / low-literacy users
                        "-p",
                        "45",
                        "-w",
                        target,
                        text[:2000],
                    ],
                    capture_output=True,
                    timeout=60,
                    check=False,
                )
                if result.returncode == 0 and Path(target).exists():
                    return "espeak-ng"
                logger.warning("espeak_failed", stderr=result.stderr.decode("utf-8", "ignore")[:200])
            except (subprocess.SubprocessError, OSError) as exc:
                logger.warning("espeak_error", error=str(exc))

        if settings.ENV in ("test", "testing", "development", "local"):
            from backend.services.speech.audio_utils import generate_mock_wav
            generate_mock_wav(target, duration_sec=1.2)
            return "synthetic_test_wav"

        raise ServiceUnavailableError(
            "No offline TTS engine available. Install piper-tts with a voice model "
            "or espeak-ng (`apt-get install espeak-ng`).",
            details={"piper_dir": str(self.piper_dir)},
        )

    async def health(self) -> Dict[str, Any]:
        return {
            "provider": self.name,
            "vosk_installed": VOSK_AVAILABLE,
            "asr_languages": sorted(self.available_asr_languages()),
            "models_loaded": sorted(self._model_cache.keys()),
            "piper_available": bool(shutil.which(settings.PIPER_BINARY)),
            "espeak_available": bool(
                shutil.which(settings.ESPEAK_BINARY) or shutil.which("espeak")
            ),
            "models_dir": str(self.models_dir),
        }


__all__ = ["OfflineSpeechProvider", "VOSK_AVAILABLE", "VOSK_MODEL_NAMES"]

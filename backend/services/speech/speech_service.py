"""Unified speech service: provider selection, fallback and metrics.

Behaviour
---------
* ``SPEECH_PROVIDER=auto`` (default) prefers Bhashini when configured and the
  circuit is closed, and transparently falls back to the offline Vosk/Piper
  provider on any failure. This is what makes PRD §7.3 "graceful degradation"
  real: a network blip mid-interview does not end the session.
* ``SPEECH_PROVIDER=bhashini`` / ``offline`` pins one engine (used for
  air-gapped facilities and for load testing).
* Concurrency is bounded by ``SPEECH_MAX_WORKERS`` so 50 kiosks cannot exhaust
  the host's CPU with simultaneous Vosk decodes.
* Per-turn metrics (engine, latency, confidence, fallback count) are returned to
  the caller and persisted into ``history_sessions.dialogue_metrics``.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.core.config import settings
from backend.core.exceptions import (
    ConfigurationError,
    ExternalServiceError,
    ServiceUnavailableError,
    SpeechProcessingError,
)
from backend.core.logging import get_logger
from backend.services.speech.audio_utils import secure_delete, temp_audio_path
from backend.services.speech.base import BaseSpeechProvider, SynthesisResult, TranscriptionResult
from backend.services.speech.bhashini_provider import BhashiniSpeechProvider
from backend.services.speech.language import detect_language, is_code_mixed
from backend.services.speech.offline_provider import OfflineSpeechProvider

logger = get_logger(__name__)

DEFAULT_CONFIG: Dict[str, Any] = {
    "active_provider": "auto",
    "default_language": "hi",
    "supported_languages": ["hi", "en", "ta", "bn", "mr", "te"],
    "audio_preprocessing": {
        "sample_rate_hz": 16000,
        "channels": 1,
        "bit_depth": 16,
        "noise_suppression_enabled": True,
        "silence_cutoff_seconds": 5.0,
        "max_turn_duration_seconds": 45.0,
    },
    "tts_voice_preferences": {"gender": "female", "speaking_rate": 1.0, "output_format": "wav"},
}


class MediKioskSpeechService:
    """Front door for every ASR/TTS call in the platform."""

    def __init__(
        self,
        provider: Optional[BaseSpeechProvider] = None,
        config_path: Optional[str] = None,
    ) -> None:
        self.config = self._load_config(config_path or settings.SPEECH_CONFIG_PATH)
        speech_cfg = self.config

        self.bhashini = BhashiniSpeechProvider(
            user_id=(speech_cfg.get("bhashini") or {}).get("user_id") or None,
            api_key=(speech_cfg.get("bhashini") or {}).get("api_key") or None,
            pipeline_id=(speech_cfg.get("bhashini") or {}).get("pipeline_id") or None,
            inference_url=(speech_cfg.get("bhashini") or {}).get("inference_url") or None,
            config_url=(speech_cfg.get("bhashini") or {}).get("config_url") or None,
        )
        offline_cfg = speech_cfg.get("offline") or {}
        self.offline = OfflineSpeechProvider(
            models_dir=offline_cfg.get("models_dir"),
            piper_dir=offline_cfg.get("piper_models_dir"),
            model_paths=offline_cfg.get("vosk_model_paths"),
        )

        self._explicit_provider = provider
        self.mode = (
            "explicit"
            if provider is not None
            else str(speech_cfg.get("active_provider", settings.SPEECH_PROVIDER)).lower()
        )
        self._semaphore = asyncio.Semaphore(max(1, settings.SPEECH_MAX_WORKERS))
        self._metrics: Dict[str, Any] = {
            "asr_calls": 0,
            "asr_failures": 0,
            "asr_fallbacks": 0,
            "tts_calls": 0,
            "tts_failures": 0,
            "total_asr_latency_ms": 0.0,
        }

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        config = dict(DEFAULT_CONFIG)
        config["active_provider"] = settings.SPEECH_PROVIDER
        config["default_language"] = settings.DEFAULT_LANGUAGE
        config["supported_languages"] = settings.supported_languages

        if config_path and Path(config_path).exists():
            try:
                loaded = json.loads(Path(config_path).read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    config.update(loaded)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("speech_config_unreadable", path=config_path, error=str(exc))
        return config

    @property
    def supported_languages(self) -> List[str]:
        return [str(x).lower() for x in self.config.get("supported_languages", [])]

    # ------------------------------------------------------------------
    # Provider selection
    # ------------------------------------------------------------------
    async def _provider_chain(self, language: str) -> List[BaseSpeechProvider]:
        """Ordered providers to try for ``language``."""
        if self._explicit_provider is not None:
            return [self._explicit_provider]

        mode = self.mode
        if mode == "bhashini":
            return [self.bhashini, self.offline]
        if mode == "offline":
            return [self.offline]

        chain: List[BaseSpeechProvider] = []
        if await self.bhashini.is_available(language):
            chain.append(self.bhashini)
        chain.append(self.offline)
        if not chain:
            chain = [self.offline]
        return chain

    def set_provider(self, provider: BaseSpeechProvider) -> None:
        """Override the provider (used by tests and by the admin console)."""
        self._explicit_provider = provider
        self.mode = "explicit"

    @property
    def provider(self) -> BaseSpeechProvider:
        """Best-guess active provider, for introspection/back-compat."""
        if self._explicit_provider is not None:
            return self._explicit_provider
        if self.mode == "offline":
            return self.offline
        if self.mode == "bhashini":
            return self.bhashini
        return self.bhashini if self.bhashini.configured else self.offline

    # ------------------------------------------------------------------
    # ASR
    # ------------------------------------------------------------------
    async def transcribe_async(
        self, audio_file_path: str, language: str = "hi", *, delete_source: bool = False
    ) -> TranscriptionResult:
        """Transcribe with automatic provider fallback."""
        language = (language or settings.DEFAULT_LANGUAGE).lower()
        started = time.monotonic()
        chain = await self._provider_chain(language)
        errors: List[str] = []

        async with self._semaphore:
            for index, engine in enumerate(chain):
                try:
                    result = await engine.transcribe(audio_file_path, language)
                    self._metrics["asr_calls"] += 1
                    self._metrics["total_asr_latency_ms"] += result.latency_ms
                    if index > 0:
                        self._metrics["asr_fallbacks"] += 1
                        result.warnings.append(
                            f"Primary speech engine unavailable; used {engine.name}"
                        )
                    if delete_source:
                        secure_delete(audio_file_path)
                    return result
                except (
                    ExternalServiceError,
                    ServiceUnavailableError,
                    ConfigurationError,
                ) as exc:
                    errors.append(f"{engine.name}: {exc.message}")
                    logger.warning(
                        "asr_provider_failed", provider=engine.name, error=exc.message
                    )
                except SpeechProcessingError:
                    # Bad audio is not a provider problem — do not try the next one.
                    self._metrics["asr_failures"] += 1
                    if delete_source:
                        secure_delete(audio_file_path)
                    raise

        self._metrics["asr_failures"] += 1
        if delete_source:
            secure_delete(audio_file_path)
        raise ServiceUnavailableError(
            "Speech recognition is temporarily unavailable. Please use the touchscreen.",
            details={
                "attempts": errors,
                "elapsed_ms": round((time.monotonic() - started) * 1000, 1),
            },
        )

    def transcribe(self, audio_file_path: str, language: str = "hi") -> str:
        """Blocking convenience wrapper (scripts/CLI only)."""
        result = asyncio.run(self.transcribe_async(audio_file_path, language))
        return result.text

    # ------------------------------------------------------------------
    # TTS
    # ------------------------------------------------------------------
    async def synthesize_async(
        self,
        text: str,
        language: str = "hi",
        output_path: Optional[str] = None,
        voice: Optional[str] = None,
    ) -> SynthesisResult:
        language = (language or settings.DEFAULT_LANGUAGE).lower()
        voice = voice or str(
            (self.config.get("tts_voice_preferences") or {}).get("gender", "female")
        )
        chain = await self._provider_chain(language)
        errors: List[str] = []

        for index, engine in enumerate(chain):
            try:
                result = await engine.synthesize(text, language, output_path, voice)
                self._metrics["tts_calls"] += 1
                return result
            except (ExternalServiceError, ServiceUnavailableError, ConfigurationError) as exc:
                errors.append(f"{engine.name}: {exc.message}")
                logger.warning("tts_provider_failed", provider=engine.name, error=exc.message)

        self._metrics["tts_failures"] += 1
        raise ServiceUnavailableError(
            "Voice guidance is temporarily unavailable. On-screen text remains available.",
            details={"attempts": errors},
        )

    def synthesize(
        self, text: str, language: str = "hi", output_path: Optional[str] = None
    ) -> str:
        result = asyncio.run(self.synthesize_async(text, language, output_path))
        return result.audio_path

    async def synthesize_to_bytes(self, text: str, language: str = "hi") -> tuple[bytes, str]:
        """Render prompt audio and return raw WAV bytes (kiosk streams these)."""
        target = temp_audio_path(".wav", "prompt")
        result = await self.synthesize_async(text, language, target)
        data = Path(result.audio_path).read_bytes()
        if result.audio_path == target:
            secure_delete(target)
        return data, result.engine

    # ------------------------------------------------------------------
    # Language utilities
    # ------------------------------------------------------------------
    def detect_language(self, text: str) -> str:
        detected = detect_language(text, default="en")
        supported = self.supported_languages or settings.supported_languages
        if detected not in supported:
            from backend.services.speech.language import resolve_supported_language

            return resolve_supported_language(detected, set(supported), settings.DEFAULT_LANGUAGE)
        return detected

    def is_code_mixed(self, text: str) -> bool:
        return is_code_mixed(text)

    # ------------------------------------------------------------------
    # Lifecycle / observability
    # ------------------------------------------------------------------
    async def warmup(self) -> Dict[str, Any]:
        """Pre-load offline models so the first patient does not wait."""
        report: Dict[str, Any] = {"mode": self.mode}
        if self.mode in ("auto", "offline"):
            report["offline_models"] = await self.offline.preload(self.supported_languages)
        if self.mode in ("auto", "bhashini") and self.bhashini.configured:
            try:
                await self.bhashini._get_pipeline_config("asr", settings.DEFAULT_LANGUAGE)
                report["bhashini_pipeline"] = "warm"
            except Exception as exc:  # noqa: BLE001 - warmup must never block boot
                report["bhashini_pipeline"] = f"cold ({exc})"
        return report

    def metrics(self) -> Dict[str, Any]:
        calls = self._metrics["asr_calls"] or 1
        return {
            **self._metrics,
            "avg_asr_latency_ms": round(self._metrics["total_asr_latency_ms"] / calls, 1),
        }

    async def health(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "languages": self.supported_languages,
            "bhashini": await self.bhashini.health(),
            "offline": await self.offline.health(),
            "metrics": self.metrics(),
        }


#: Process-wide singleton (model caches make multiple instances wasteful).
speech_service = MediKioskSpeechService()

__all__ = ["MediKioskSpeechService", "speech_service"]

"""Speech provider contract.

Providers return rich result objects rather than bare strings so the dialogue
manager can act on confidence (PRD §6.6.3: "Clear instructions if voice not
understood; offer retry, use touch") and so ASR quality metrics land in
``history_sessions.dialogue_metrics``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(slots=True)
class TranscriptionResult:
    """Outcome of one ASR turn."""

    text: str
    language: str
    confidence: float = 0.0
    engine: str = "unknown"
    duration_seconds: float = 0.0
    latency_ms: float = 0.0
    is_final: bool = True
    alternatives: List[str] = field(default_factory=list)
    #: True when the audio contained no intelligible speech; the kiosk should
    #: re-prompt rather than record an empty answer.
    is_empty: bool = False
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transcription": self.text,
            "language": self.language,
            "confidence": round(self.confidence, 3),
            "engine": self.engine,
            "duration_seconds": round(self.duration_seconds, 2),
            "latency_ms": round(self.latency_ms, 1),
            "is_empty": self.is_empty,
            "alternatives": self.alternatives,
            "warnings": self.warnings,
        }


@dataclass(slots=True)
class SynthesisResult:
    """Outcome of one TTS request."""

    audio_path: str
    language: str
    engine: str
    duration_seconds: float = 0.0
    sample_rate: int = 16_000
    latency_ms: float = 0.0
    cached: bool = False
    voice: str = "female"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "audio_file_path": self.audio_path,
            "language": self.language,
            "engine": self.engine,
            "duration_seconds": round(self.duration_seconds, 2),
            "sample_rate": self.sample_rate,
            "latency_ms": round(self.latency_ms, 1),
            "cached": self.cached,
            "voice": self.voice,
        }


class BaseSpeechProvider(ABC):
    """Abstract ASR/TTS engine."""

    name: str = "base"

    @abstractmethod
    async def transcribe(
        self, audio_file_path: str, language: str = "hi"
    ) -> TranscriptionResult:
        """Transcribe an audio file to text in ``language``."""

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        language: str = "hi",
        output_path: Optional[str] = None,
        voice: str = "female",
    ) -> SynthesisResult:
        """Render ``text`` to a 16 kHz mono WAV file and return its path."""

    @abstractmethod
    async def is_available(self, language: Optional[str] = None) -> bool:
        """Whether this provider can currently serve requests."""

    def detect_language(self, text: str) -> str:
        """Script/keyword based language identification."""
        from backend.services.speech.language import detect_language

        return detect_language(text)

    async def health(self) -> Dict[str, Any]:
        return {"provider": self.name, "available": await self.is_available()}


__all__ = ["BaseSpeechProvider", "TranscriptionResult", "SynthesisResult"]

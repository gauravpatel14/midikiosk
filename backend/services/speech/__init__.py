"""MediKiosk speech package (ASR + TTS).

Providers
---------
:class:`~backend.services.speech.bhashini_provider.BhashiniSpeechProvider`
    Government of India Bhashini / AI4Bharat models via the Dhruva inference
    gateway. Data stays inside India, satisfying DPDP data-residency.
:class:`~backend.services.speech.offline_provider.OfflineSpeechProvider`
    Fully offline: Vosk (Kaldi) for ASR and Piper (or espeak-ng) for TTS. Used
    when connectivity drops or when a facility forbids any egress.

:class:`~backend.services.speech.speech_service.MediKioskSpeechService`
    Front door used by the routers. Chooses a provider, retries, falls back
    from Bhashini to offline, and never blocks the event loop.
"""

from backend.services.speech.audio_utils import (
    AudioMetadata,
    convert_to_pcm16,
    generate_silence_wav,
    generate_tone_wav,
    inspect_audio,
    normalise_for_asr,
)
from backend.services.speech.base import BaseSpeechProvider, TranscriptionResult, SynthesisResult
from backend.services.speech.bhashini_provider import BhashiniSpeechProvider
from backend.services.speech.language import detect_language, is_code_mixed
from backend.services.speech.offline_provider import OfflineSpeechProvider
from backend.services.speech.speech_service import MediKioskSpeechService, speech_service

#: Historical alias — older tests imported ``generate_mock_wav``.
generate_mock_wav = generate_tone_wav

__all__ = [
    "BaseSpeechProvider",
    "TranscriptionResult",
    "SynthesisResult",
    "BhashiniSpeechProvider",
    "OfflineSpeechProvider",
    "MediKioskSpeechService",
    "speech_service",
    "AudioMetadata",
    "inspect_audio",
    "normalise_for_asr",
    "convert_to_pcm16",
    "generate_tone_wav",
    "generate_silence_wav",
    "generate_mock_wav",
    "detect_language",
    "is_code_mixed",
]

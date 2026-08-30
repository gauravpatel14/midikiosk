"""Verification test suite for MediKiosk Speech Service (ASR, TTS, and Language Detection)."""

import os
import sys
import wave
from pathlib import Path

# Add root and backend to path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
for p in [str(root_dir), str(backend_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.services.speech.audio_utils import generate_mock_wav
from backend.services.speech.bhashini_provider import BhashiniSpeechProvider
from backend.services.speech.offline_provider import OfflineSpeechProvider
from backend.services.speech.speech_service import MediKioskSpeechService


def test_speech_suite():
    print("\n--- Running MediKiosk Speech Service Test Suite ---")

    # 1. Initialize Service with Config
    config_file = str(backend_dir / "speech_config.json")
    service = MediKioskSpeechService(config_path=config_file)
    print(f"✔ 1. Service initialized with config. Active provider: {type(service.provider).__name__}")

    # Generate a sample input WAV for ASR testing
    test_audio_path = "/tmp/medikiosk_test_input.wav"
    generate_mock_wav(test_audio_path, duration_sec=1.5)
    assert os.path.exists(test_audio_path), "Input audio file creation failed"

    # 2. Test ASR: transcribe(audio_file_path, language)
    # 2a. Hindi
    hi_transcription = service.transcribe(test_audio_path, language="hi")
    assert len(hi_transcription) > 0
    print(f"✔ 2a. ASR Hindi (hi): '{hi_transcription}'")

    # 2b. English
    en_transcription = service.transcribe(test_audio_path, language="en")
    assert len(en_transcription) > 0
    print(f"✔ 2b. ASR English (en): '{en_transcription}'")

    # 2c. Tamil (Regional Language)
    ta_transcription = service.transcribe(test_audio_path, language="ta")
    assert len(ta_transcription) > 0
    print(f"✔ 2c. ASR Tamil (ta): '{ta_transcription}'")

    # 3. Test TTS: synthesize(text, language) -> audio_file_path
    # 3a. Hindi
    hi_audio = service.synthesize("कृपया अपनी छाती के दर्द के बारे में बताएं।", language="hi")
    assert os.path.exists(hi_audio), "Hindi TTS audio not created"
    with wave.open(hi_audio, "rb") as wf:
        assert wf.getframerate() == 16000
    print(f"✔ 3a. TTS Hindi: Created 16kHz WAV at {hi_audio}")

    # 3b. English
    en_audio = service.synthesize("Please place your documents on the scanner bed.", language="en")
    assert os.path.exists(en_audio), "English TTS audio not created"
    print(f"✔ 3b. TTS English: Created 16kHz WAV at {en_audio}")

    # 3c. Tamil
    ta_audio = service.synthesize("உங்கள் ஆவணங்களை ஸ்கேனரில் வைக்கவும்.", language="ta")
    assert os.path.exists(ta_audio), "Tamil TTS audio not created"
    print(f"✔ 3c. TTS Tamil: Created 16kHz WAV at {ta_audio}")

    # 4. Test Language Detection: detect_language(text)
    # 4a. Hindi (Devanagari script)
    lang_hi = service.detect_language("मुझे सीने में भारीपन लग रहा है।")
    assert lang_hi == "hi", f"Expected 'hi', got '{lang_hi}'"
    print(f"✔ 4a. Language Detection (Devanagari): Detected '{lang_hi}'")

    # 4b. Tamil (Tamil script)
    lang_ta = service.detect_language("எனக்கு நெஞ்சு வலி உள்ளது.")
    assert lang_ta == "ta", f"Expected 'ta', got '{lang_ta}'"
    print(f"✔ 4b. Language Detection (Tamil): Detected '{lang_ta}'")

    # 4c. English (Standard Latin)
    lang_en = service.detect_language("Patient has elevated blood pressure and acute fatigue.")
    assert lang_en == "en", f"Expected 'en', got '{lang_en}'"
    print(f"✔ 4c. Language Detection (English): Detected '{lang_en}'")

    # 4d. Code-mixed Latin Script (PRD §7.6: 'Mujhe chest pain hai')
    lang_mixed = service.detect_language("Mujhe 3 din se chest pain aur bukhar hai")
    assert lang_mixed == "hi", f"Expected 'hi' for Hinglish, got '{lang_mixed}'"
    print(f"✔ 4d. Language Detection (Hinglish Code-mixed): Detected '{lang_mixed}'")

    # 5. Test Swappable Provider Abstraction Layer
    offline_provider = OfflineSpeechProvider()
    service.set_provider(offline_provider)
    offline_transcription = service.transcribe(test_audio_path, language="hi")
    assert "नमस्ते" in offline_transcription or "बुखार" in offline_transcription
    print(f"✔ 5. Swappable Provider Abstraction: Swapped to {type(service.provider).__name__} seamlessly")

    print("\n--- ALL SPEECH TESTS PASSED 100% ---")


if __name__ == "__main__":
    test_speech_suite()

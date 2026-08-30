"""Audio inspection, normalisation and synthetic-audio helpers.

OPD kiosks feed us whatever the browser or scanner produced: WebM/Opus from
Chrome, 44.1 kHz stereo WAV from a USB mic array, or MP3 from an assistive app.
Every ASR engine here expects **16 kHz, 16-bit, mono PCM WAV**, so
:func:`normalise_for_asr` performs that conversion:

* pure-Python path using :mod:`wave` + :mod:`audioop` for PCM WAV inputs
  (no external dependency, always available), and
* ``ffmpeg`` for compressed containers, when installed.

It also computes an RMS-based speech-presence check so a silent recording is
rejected before burning an ASR call (PRD §6.6.3 silence handling).
"""

from __future__ import annotations

import asyncio
import contextlib
import math
import os
import shutil
import struct
import subprocess
import uuid
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from backend.core.config import settings
from backend.core.exceptions import SpeechProcessingError
from backend.core.logging import get_logger

logger = get_logger(__name__)

TARGET_SAMPLE_RATE = 16_000
TARGET_CHANNELS = 1
TARGET_SAMPLE_WIDTH = 2  # 16-bit

#: Below this RMS (0..1 normalised) the clip is treated as silence.
SILENCE_RMS_THRESHOLD = 0.006

try:  # Python <3.13 ships audioop; 3.13+ moved it to the audioop-lts package.
    import audioop  # type: ignore[import-not-found]

    AUDIOOP_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on interpreter version
    try:
        import audioop_lts as audioop  # type: ignore[import-not-found,no-redef]

        AUDIOOP_AVAILABLE = True
    except ImportError:
        audioop = None  # type: ignore[assignment]
        AUDIOOP_AVAILABLE = False


@dataclass(slots=True)
class AudioMetadata:
    """Physical properties of an audio file plus a speech-presence verdict."""

    path: str
    format: str
    channels: int
    sample_rate: int
    sample_width: int
    duration_seconds: float
    rms: float
    is_silent: bool
    size_bytes: int

    @property
    def needs_conversion(self) -> bool:
        return (
            self.format != "wav"
            or self.sample_rate != TARGET_SAMPLE_RATE
            or self.channels != TARGET_CHANNELS
            or self.sample_width != TARGET_SAMPLE_WIDTH
        )


def _ffmpeg_path() -> Optional[str]:
    return shutil.which("ffmpeg")


def work_dir() -> Path:
    directory = Path(settings.AUDIO_WORK_DIR)
    try:
        directory.mkdir(parents=True, exist_ok=True)
        return directory
    except (PermissionError, OSError):
        fallback = Path(os.environ.get("TMPDIR", "/tmp")) / "medikiosk-audio"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def temp_audio_path(suffix: str = ".wav", prefix: str = "mk") -> str:
    return str(work_dir() / f"{prefix}_{uuid.uuid4().hex[:12]}{suffix}")


def inspect_audio(path: str) -> AudioMetadata:
    """Read header metadata and compute RMS energy."""
    file_path = Path(path)
    if not file_path.exists():
        raise SpeechProcessingError(f"Audio file not found: {path}")
    size = file_path.stat().st_size
    if size == 0:
        raise SpeechProcessingError("Audio file is empty (0 bytes)")

    try:
        with wave.open(str(file_path), "rb") as handle:
            channels = handle.getnchannels()
            sample_rate = handle.getframerate()
            sample_width = handle.getsampwidth()
            frames = handle.getnframes()
            duration = frames / float(sample_rate) if sample_rate else 0.0
            raw = handle.readframes(min(frames, sample_rate * 30))
        rms = _compute_rms(raw, sample_width)
        return AudioMetadata(
            path=str(file_path),
            format="wav",
            channels=channels,
            sample_rate=sample_rate,
            sample_width=sample_width,
            duration_seconds=duration,
            rms=rms,
            is_silent=rms < SILENCE_RMS_THRESHOLD,
            size_bytes=size,
        )
    except (wave.Error, EOFError):
        # Non-WAV container (webm/ogg/mp3/m4a) — probe with ffmpeg when present.
        return _inspect_with_ffprobe(file_path, size)


def _inspect_with_ffprobe(file_path: Path, size: int) -> AudioMetadata:
    ffprobe = shutil.which("ffprobe")
    fmt = file_path.suffix.lstrip(".").lower() or "unknown"
    if not ffprobe:
        return AudioMetadata(
            path=str(file_path),
            format=fmt,
            channels=1,
            sample_rate=0,
            sample_width=2,
            duration_seconds=0.0,
            rms=1.0,  # unknown — assume speech present so we do not drop audio
            is_silent=False,
            size_bytes=size,
        )
    try:
        output = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=channels,sample_rate:format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(file_path),
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        lines = [ln.strip() for ln in output.stdout.splitlines() if ln.strip()]
        channels = int(lines[0]) if len(lines) > 0 and lines[0].isdigit() else 1
        sample_rate = int(lines[1]) if len(lines) > 1 and lines[1].isdigit() else 0
        duration = float(lines[2]) if len(lines) > 2 else 0.0
    except Exception as exc:  # noqa: BLE001
        logger.warning("ffprobe_failed", error=str(exc))
        channels, sample_rate, duration = 1, 0, 0.0

    return AudioMetadata(
        path=str(file_path),
        format=fmt,
        channels=channels,
        sample_rate=sample_rate,
        sample_width=2,
        duration_seconds=duration,
        rms=1.0,
        is_silent=False,
        size_bytes=size,
    )


def _compute_rms(raw: bytes, sample_width: int) -> float:
    if not raw:
        return 0.0
    if AUDIOOP_AVAILABLE and audioop is not None:
        try:
            peak = float(1 << (8 * sample_width - 1))
            return audioop.rms(raw, sample_width) / peak
        except Exception:  # noqa: BLE001
            pass
    if sample_width != 2:
        return 1.0
    count = len(raw) // 2
    if count == 0:
        return 0.0
    samples = struct.unpack(f"<{count}h", raw[: count * 2])
    total = sum(float(s) * float(s) for s in samples)
    return math.sqrt(total / count) / 32768.0


def convert_to_pcm16(
    source: str,
    destination: Optional[str] = None,
    *,
    sample_rate: int = TARGET_SAMPLE_RATE,
) -> str:
    """Convert any supported audio file to 16 kHz mono 16-bit PCM WAV."""
    dest = destination or temp_audio_path(".wav", "norm")
    meta = inspect_audio(source)

    if meta.format == "wav" and AUDIOOP_AVAILABLE:
        try:
            return _convert_wav_pure_python(source, dest, sample_rate)
        except Exception as exc:  # noqa: BLE001 - fall through to ffmpeg
            logger.warning("wav_conversion_failed", error=str(exc))

    ffmpeg = _ffmpeg_path()
    if not ffmpeg:
        if meta.format == "wav":
            # Already WAV and we cannot resample; the engine may still cope.
            return source
        raise SpeechProcessingError(
            "ffmpeg is required to decode compressed audio. Install it with "
            "`apt-get install ffmpeg` on the kiosk backend host.",
            details={"format": meta.format},
        )

    result = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            source,
            "-ac",
            str(TARGET_CHANNELS),
            "-ar",
            str(sample_rate),
            "-sample_fmt",
            "s16",
            "-af",
            "highpass=f=80,lowpass=f=7500,dynaudnorm=f=200:g=5",
            dest,
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode != 0 or not Path(dest).exists():
        raise SpeechProcessingError(
            "Audio conversion failed", details={"stderr": result.stderr[:400]}
        )
    return dest


def _convert_wav_pure_python(source: str, dest: str, sample_rate: int) -> str:
    if not AUDIOOP_AVAILABLE or audioop is None:
        raise SpeechProcessingError(
            "PCM conversion requires audioop (install audioop-lts on Python 3.13+)",
            details={"code": "AUDIOOP_UNAVAILABLE"},
        )
    with wave.open(source, "rb") as src:
        channels = src.getnchannels()
        width = src.getsampwidth()
        rate = src.getframerate()
        frames = src.readframes(src.getnframes())

    if width != TARGET_SAMPLE_WIDTH:
        frames = audioop.lin2lin(frames, width, TARGET_SAMPLE_WIDTH)
        width = TARGET_SAMPLE_WIDTH
    if channels > 1:
        frames = audioop.tomono(frames, width, 0.5, 0.5)
    if rate != sample_rate:
        frames, _ = audioop.ratecv(frames, width, 1, rate, sample_rate, None)

    with wave.open(dest, "wb") as out:
        out.setnchannels(TARGET_CHANNELS)
        out.setsampwidth(TARGET_SAMPLE_WIDTH)
        out.setframerate(sample_rate)
        out.writeframes(frames)
    return dest


def normalise_for_asr(path: str, *, sample_rate: int = TARGET_SAMPLE_RATE) -> Tuple[str, AudioMetadata]:
    """Validate + convert audio, returning the ASR-ready path and metadata."""
    meta = inspect_audio(path)

    max_bytes = 40 * 1024 * 1024
    if meta.size_bytes > max_bytes:
        raise SpeechProcessingError(
            "Audio recording exceeds the 40 MB limit",
            details={"size_bytes": meta.size_bytes},
        )

    if not meta.needs_conversion:
        return path, meta

    converted = convert_to_pcm16(path, sample_rate=sample_rate)
    return converted, inspect_audio(converted)


async def normalise_for_asr_async(
    path: str, *, sample_rate: int = TARGET_SAMPLE_RATE
) -> Tuple[str, AudioMetadata]:
    """Off-thread wrapper so conversion never blocks the event loop."""
    return await asyncio.to_thread(normalise_for_asr, path, sample_rate=sample_rate)


# ---------------------------------------------------------------------------
# Synthetic audio (used by TTS fallbacks and the test-suite)
# ---------------------------------------------------------------------------
def generate_tone_wav(
    destination_path: str,
    duration_sec: float = 1.5,
    frequency_hz: float = 440.0,
    sample_rate: int = TARGET_SAMPLE_RATE,
) -> str:
    """Write a decaying sine tone as valid 16 kHz mono PCM WAV."""
    parent = Path(destination_path).parent
    if str(parent) not in ("", "."):
        parent.mkdir(parents=True, exist_ok=True)

    num_samples = max(1, int(sample_rate * duration_sec))
    with wave.open(destination_path, "wb") as handle:
        handle.setnchannels(TARGET_CHANNELS)
        handle.setsampwidth(TARGET_SAMPLE_WIDTH)
        handle.setframerate(sample_rate)
        payload = bytearray()
        for index in range(num_samples):
            t = index / sample_rate
            amplitude = 32767 * 0.45 * math.exp(-t / max(0.2, duration_sec))
            payload.extend(
                struct.pack("<h", int(amplitude * math.sin(2.0 * math.pi * frequency_hz * t)))
            )
        handle.writeframes(bytes(payload))
    return destination_path


def generate_silence_wav(
    destination_path: str, duration_sec: float = 0.5, sample_rate: int = TARGET_SAMPLE_RATE
) -> str:
    parent = Path(destination_path).parent
    if str(parent) not in ("", "."):
        parent.mkdir(parents=True, exist_ok=True)
    with wave.open(destination_path, "wb") as handle:
        handle.setnchannels(TARGET_CHANNELS)
        handle.setsampwidth(TARGET_SAMPLE_WIDTH)
        handle.setframerate(sample_rate)
        handle.writeframes(b"\x00\x00" * int(sample_rate * duration_sec))
    return destination_path


def wav_duration(path: str) -> float:
    with contextlib.suppress(Exception):
        with wave.open(path, "rb") as handle:
            rate = handle.getframerate()
            return handle.getnframes() / float(rate) if rate else 0.0
    return 0.0


def secure_delete(path: str) -> None:
    """Best-effort removal of temporary raw media (PRD §6.5.3, 24 h retention)."""
    with contextlib.suppress(FileNotFoundError, PermissionError, OSError):
        target = Path(path)
        if target.is_file():
            size = target.stat().st_size
            if 0 < size <= 8 * 1024 * 1024:
                with open(target, "r+b") as handle:
                    handle.write(os.urandom(size))
                    handle.flush()
                    os.fsync(handle.fileno())
            target.unlink()


#: Legacy name kept for the historical test-suite.
validate_and_preprocess_audio = lambda path: normalise_for_asr(path)[0]  # noqa: E731
generate_mock_wav = generate_tone_wav


__all__ = [
    "AudioMetadata",
    "TARGET_SAMPLE_RATE",
    "inspect_audio",
    "normalise_for_asr",
    "normalise_for_asr_async",
    "convert_to_pcm16",
    "generate_tone_wav",
    "generate_silence_wav",
    "generate_mock_wav",
    "validate_and_preprocess_audio",
    "wav_duration",
    "secure_delete",
    "temp_audio_path",
    "work_dir",
]

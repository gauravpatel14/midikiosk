"""FastAPI Router for Speech Recognition (ASR), Text-to-Speech (TTS), and Language Detection."""

import os
from typing import Dict, Optional
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

try:
    from services.speech.speech_service import MediKioskSpeechService
except ImportError:
    from ..services.speech.speech_service import MediKioskSpeechService

router = APIRouter(prefix="/speech", tags=["Multimodal Speech (ASR & TTS)"])
speech_service = MediKioskSpeechService()


class LanguageDetectRequest(BaseModel):
    text: str = Field(..., description="Text to analyze for language or code-mixing")


class LanguageDetectResponse(BaseModel):
    detected_language: str
    is_code_mixed: bool


class SynthesisRequest(BaseModel):
    text: str = Field(..., description="Clinical prompt or message to synthesize")
    language: str = Field(default="hi", description="Target ISO code ('hi', 'en', 'ta', 'bn', 'mr')")


class SynthesisResponse(BaseModel):
    status: str
    language: str
    audio_file_path: str


class TranscriptionResponse(BaseModel):
    transcription: str
    language: str


@router.post("/transcribe", response_model=TranscriptionResponse, summary="Transcribe Audio (ASR)")
async def transcribe_audio_endpoint(
    file: UploadFile = File(...),
    language: str = Form("hi"),
) -> TranscriptionResponse:
    """Upload patient speech recording and return transcribed clinical text."""
    temp_dir = "/tmp/medikiosk_uploads"
    os.makedirs(temp_dir, exist_ok=True)
    temp_file = os.path.join(temp_dir, file.filename or "input.wav")

    with open(temp_file, "wb") as buffer:
        content = await file.read()
        buffer.write(content)

    result = await speech_service.transcribe_async(temp_file, language=language)
    return TranscriptionResponse(transcription=result.text, language=language)


@router.post("/synthesize", response_model=SynthesisResponse, summary="Synthesize Text to Speech (TTS)")
async def synthesize_speech_endpoint(payload: SynthesisRequest) -> SynthesisResponse:
    """Convert text instructions to vocalized 16kHz WAV audio."""
    res = await speech_service.synthesize_async(payload.text, language=payload.language)
    return SynthesisResponse(status="success", language=payload.language, audio_file_path=res.audio_path)


@router.post("/detect-language", response_model=LanguageDetectResponse, summary="Detect Language & Code-mixing")
def detect_language_endpoint(payload: LanguageDetectRequest) -> LanguageDetectResponse:
    """Analyze script and phonetic keywords to identify Hindi, Tamil, English, or code-mixing."""
    lang = speech_service.detect_language(payload.text)
    # Check if text uses Latin script but contains Hindi vocabulary (Hinglish)
    is_mixed = lang == "hi" and payload.text.isascii()
    return LanguageDetectResponse(detected_language=lang, is_code_mixed=is_mixed)

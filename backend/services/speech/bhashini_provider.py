"""Bhashini / AI4Bharat speech provider (Dhruva inference gateway).

Bhashini is the Government of India's national language-technology platform. It
hosts AI4Bharat's IndicConformer (ASR) and IndicTTS (FastSpeech2 + HiFi-GAN)
models. Using it satisfies two PRD constraints simultaneously:

* §7.4 — all AI processing happens inside India, DPDP-compliant.
* §7.6 — Hindi, English plus regional languages with Indian-accent training.

Two-stage protocol
------------------
1. **Pipeline configuration** (``ULCA getModelsPipeline``): given a pipeline id
   and the desired task/language, ULCA returns the *inference* endpoint, the
   ``serviceId`` for each task, and a short-lived inference API key. This is
   slow (~1 s) and stable, so the result is cached in Redis for 12 hours per
   ``(task, language)`` pair.
2. **Inference** (``/services/inference/pipeline``): the actual ASR/TTS call
   using the resolved ``serviceId``.

Failures raise :class:`ExternalServiceError`; the orchestrating
:class:`MediKioskSpeechService` then falls back to the offline provider. This
module never fabricates a transcript.
"""

from __future__ import annotations

import base64
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.core.cache import cache
from backend.core.config import settings
from backend.core.exceptions import ConfigurationError, ExternalServiceError, SpeechProcessingError
from backend.core.http import ResilientHttpClient
from backend.core.logging import get_logger
from backend.services.speech.audio_utils import (
    normalise_for_asr_async,
    temp_audio_path,
    wav_duration,
)
from backend.services.speech.base import BaseSpeechProvider, SynthesisResult, TranscriptionResult
from backend.services.speech.language import resolve_supported_language

logger = get_logger(__name__)

PIPELINE_CACHE_TTL = 12 * 3600

#: Bhashini/ULCA language codes match ISO-639-1 for the languages we support.
BHASHINI_LANGUAGES = {"hi", "en", "ta", "bn", "mr", "te", "kn", "ml", "gu", "pa", "or", "as"}

#: Preferred voice gender per language, overridable through speech_config.json.
DEFAULT_VOICE_GENDER = "female"


class BhashiniSpeechProvider(BaseSpeechProvider):
    """ASR + TTS through Bhashini's Dhruva inference gateway."""

    name = "bhashini"

    def __init__(
        self,
        user_id: Optional[str] = None,
        api_key: Optional[str] = None,
        pipeline_id: Optional[str] = None,
        inference_url: Optional[str] = None,
        config_url: Optional[str] = None,
    ) -> None:
        self.user_id = user_id or settings.BHASHINI_USER_ID
        self.api_key = api_key or settings.BHASHINI_API_KEY
        self.pipeline_id = pipeline_id or settings.BHASHINI_PIPELINE_ID
        self.inference_url = inference_url or settings.BHASHINI_INFERENCE_URL
        self.config_url = config_url or settings.BHASHINI_CONFIG_URL
        self.supported_languages = BHASHINI_LANGUAGES & set(settings.supported_languages)

        self._config_http = ResilientHttpClient.get(
            "bhashini-config", timeout=settings.BHASHINI_TIMEOUT, max_retries=2
        )
        self._inference_http = ResilientHttpClient.get(
            "bhashini-inference",
            timeout=settings.BHASHINI_TIMEOUT,
            max_retries=2,
            failure_threshold=4,
            recovery_seconds=30.0,
        )

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------
    @property
    def configured(self) -> bool:
        return bool(
            settings.BHASHINI_ENABLED
            and self.user_id
            and self.api_key
            and not self.api_key.startswith("mock_")
        )

    async def is_available(self, language: Optional[str] = None) -> bool:
        if not self.configured or settings.OFFLINE_MODE:
            return False
        if language and self._resolve_language(language) not in self.supported_languages:
            return False
        return self._inference_http.breaker.state != "open"

    def _resolve_language(self, language: str) -> str:
        return resolve_supported_language(
            language, self.supported_languages or BHASHINI_LANGUAGES, settings.DEFAULT_LANGUAGE
        )

    def _require_configured(self) -> None:
        if not self.configured:
            raise ConfigurationError(
                "Bhashini is not configured. Set BHASHINI_USER_ID, BHASHINI_API_KEY "
                "and BHASHINI_PIPELINE_ID, or set SPEECH_PROVIDER=offline.",
            )

    # ------------------------------------------------------------------
    # Stage 1 — pipeline configuration
    # ------------------------------------------------------------------
    async def _get_pipeline_config(self, task: str, language: str) -> Dict[str, Any]:
        """Resolve ``serviceId`` + inference endpoint for ``task``/``language``."""
        cache_key = f"bhashini:pipeline:{self.pipeline_id}:{task}:{language}"
        cached = await cache.get(cache_key)
        if isinstance(cached, dict) and cached.get("service_id"):
            return cached

        self._require_configured()

        task_config: Dict[str, Any] = {
            "taskType": task,
            "config": {"language": {"sourceLanguage": language}},
        }
        payload = {
            "pipelineTasks": [task_config],
            "pipelineRequestConfig": {"pipelineId": self.pipeline_id},
        }
        headers = {
            "userID": self.user_id,
            "ulcaApiKey": self.api_key,
            "Content-Type": "application/json",
        }

        data = await self._config_http.post_json(self.config_url, json_body=payload, headers=headers)

        pipeline_config = (data.get("pipelineResponseConfig") or [{}])[0]
        configs: List[Dict[str, Any]] = pipeline_config.get("config") or []
        if not configs:
            raise ExternalServiceError(
                "bhashini-config",
                f"No Bhashini model available for task={task} language={language}",
                details={"pipeline_id": self.pipeline_id},
            )

        chosen = configs[0]
        if task == "tts":
            preferred = [c for c in configs if c.get("modelId") and DEFAULT_VOICE_GENDER in str(c)]
            chosen = preferred[0] if preferred else configs[0]

        inference_cfg = data.get("pipelineInferenceAPIEndPoint") or {}
        auth = inference_cfg.get("inferenceApiKey") or {}
        resolved = {
            "service_id": chosen.get("serviceId"),
            "model_id": chosen.get("modelId"),
            "endpoint": inference_cfg.get("callbackUrl") or self.inference_url,
            "auth_header": auth.get("name") or "Authorization",
            "auth_value": auth.get("value") or settings.BHASHINI_INFERENCE_API_KEY,
            "supported_voices": chosen.get("supportedVoices") or [],
            "sample_rate": (chosen.get("samplingRate") or [settings.ASR_SAMPLE_RATE])[0]
            if isinstance(chosen.get("samplingRate"), list)
            else chosen.get("samplingRate", settings.ASR_SAMPLE_RATE),
        }
        if not resolved["service_id"]:
            raise ExternalServiceError(
                "bhashini-config", "Bhashini pipeline response omitted serviceId"
            )

        await cache.set(cache_key, resolved, PIPELINE_CACHE_TTL)
        logger.info(
            "bhashini_pipeline_resolved",
            task=task,
            language=language,
            service_id=resolved["service_id"],
        )
        return resolved

    # ------------------------------------------------------------------
    # Stage 2 — inference
    # ------------------------------------------------------------------
    async def _infer(self, config: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        headers = {
            "Content-Type": "application/json",
            str(config["auth_header"]): str(config["auth_value"] or self.api_key),
        }
        return await self._inference_http.post_json(
            str(config["endpoint"]), json_body=payload, headers=headers
        )

    # ------------------------------------------------------------------
    # ASR
    # ------------------------------------------------------------------
    async def transcribe(
        self, audio_file_path: str, language: str = "hi"
    ) -> TranscriptionResult:
        started = time.monotonic()
        lang = self._resolve_language(language)
        normalised_path, meta = await normalise_for_asr_async(audio_file_path)

        if meta.is_silent:
            logger.info("asr_silence_detected", duration=meta.duration_seconds)
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

        config = await self._get_pipeline_config("asr", lang)
        audio_b64 = base64.b64encode(Path(normalised_path).read_bytes()).decode("ascii")

        payload = {
            "pipelineTasks": [
                {
                    "taskType": "asr",
                    "config": {
                        "language": {"sourceLanguage": lang},
                        "serviceId": config["service_id"],
                        "audioFormat": "wav",
                        "samplingRate": meta.sample_rate or settings.ASR_SAMPLE_RATE,
                        "preProcessors": ["vad"],
                        "postProcessors": ["itn", "punctuation"],
                    },
                }
            ],
            "inputData": {"audio": [{"audioContent": audio_b64}]},
        }

        data = await self._infer(config, payload)
        text, confidence = self._extract_transcript(data)

        latency = (time.monotonic() - started) * 1000
        logger.info(
            "asr_completed",
            engine=self.name,
            language=lang,
            latency_ms=round(latency, 1),
            chars=len(text),
        )
        return TranscriptionResult(
            text=text.strip(),
            language=lang,
            confidence=confidence,
            engine=f"{self.name}:{config.get('model_id') or config['service_id']}",
            duration_seconds=meta.duration_seconds,
            latency_ms=latency,
            is_empty=not text.strip(),
        )

    @staticmethod
    def _extract_transcript(data: Dict[str, Any]) -> tuple[str, float]:
        responses = data.get("pipelineResponse") or []
        for response in responses:
            if response.get("taskType") not in (None, "asr"):
                continue
            outputs = response.get("output") or []
            if outputs:
                first = outputs[0]
                text = str(first.get("source") or first.get("target") or "")
                # Dhruva does not always return a score; a returned transcript
                # from a VAD-gated request is high confidence in practice.
                confidence = float(first.get("confidence") or 0.0) or (0.9 if text else 0.0)
                return text, min(1.0, confidence)
        return "", 0.0

    # ------------------------------------------------------------------
    # TTS
    # ------------------------------------------------------------------
    async def synthesize(
        self,
        text: str,
        language: str = "hi",
        output_path: Optional[str] = None,
        voice: str = DEFAULT_VOICE_GENDER,
    ) -> SynthesisResult:
        if not text or not text.strip():
            raise SpeechProcessingError("Cannot synthesise empty text")

        started = time.monotonic()
        lang = self._resolve_language(language)
        config = await self._get_pipeline_config("tts", lang)
        target = output_path or temp_audio_path(".wav", "tts")

        payload = {
            "pipelineTasks": [
                {
                    "taskType": "tts",
                    "config": {
                        "language": {"sourceLanguage": lang},
                        "serviceId": config["service_id"],
                        "gender": voice,
                        "samplingRate": int(config.get("sample_rate") or settings.ASR_SAMPLE_RATE),
                    },
                }
            ],
            "inputData": {"input": [{"source": text[:2000]}]},
        }

        data = await self._infer(config, payload)
        audio_b64 = self._extract_audio(data)
        if not audio_b64:
            raise ExternalServiceError("bhashini-inference", "TTS response contained no audio")

        Path(target).parent.mkdir(parents=True, exist_ok=True)
        Path(target).write_bytes(base64.b64decode(audio_b64))

        latency = (time.monotonic() - started) * 1000
        logger.info("tts_completed", engine=self.name, language=lang, latency_ms=round(latency, 1))
        return SynthesisResult(
            audio_path=str(Path(target).resolve()),
            language=lang,
            engine=f"{self.name}:{config.get('model_id') or config['service_id']}",
            duration_seconds=wav_duration(target),
            sample_rate=int(config.get("sample_rate") or settings.ASR_SAMPLE_RATE),
            latency_ms=latency,
            voice=voice,
        )

    @staticmethod
    def _extract_audio(data: Dict[str, Any]) -> Optional[str]:
        for response in data.get("pipelineResponse") or []:
            audio = response.get("audio") or []
            if audio:
                content = audio[0].get("audioContent")
                if content:
                    return str(content)
        return None

    async def health(self) -> Dict[str, Any]:
        return {
            "provider": self.name,
            "configured": self.configured,
            "languages": sorted(self.supported_languages),
            "circuit": self._inference_http.breaker.snapshot(),
        }


__all__ = ["BhashiniSpeechProvider", "BHASHINI_LANGUAGES"]

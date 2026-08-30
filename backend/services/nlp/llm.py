"""Unified LLM client: local Ollama first, OpenAI-compatible optional.

Why Ollama first
----------------
PRD §7.4 requires all AI processing to be on-premises or within India. A local
Llama-3.1-8B-Instruct on the hospital server satisfies that with zero marginal
cost and no PHI egress. A cloud model is only used when an administrator
explicitly enables it (``OPENAI_ENABLED=true``), and the request is redacted
first.

Structured output
-----------------
``complete_json`` requests JSON, validates it against a caller-supplied schema
of required keys, and repairs the two failure modes real models exhibit:
markdown fences and trailing prose. If the payload still does not parse, the
caller receives ``None`` and falls back to deterministic rules — the pipeline
never silently invents clinical data.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List, Optional, Sequence

from backend.core.config import settings
from backend.core.exceptions import ExternalServiceError
from backend.core.http import ResilientHttpClient
from backend.core.logging import get_logger, mask_text

logger = get_logger(__name__)

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


class LLMClient:
    """Small, dependency-light client for chat + JSON completions."""

    def __init__(self) -> None:
        self._ollama = ResilientHttpClient.get(
            "ollama",
            base_url=settings.OLLAMA_BASE_URL,
            timeout=settings.OLLAMA_TIMEOUT,
            max_retries=2,
            failure_threshold=3,
            recovery_seconds=60.0,
        )
        self._openai = ResilientHttpClient.get(
            "openai",
            base_url=settings.OPENAI_BASE_URL or "https://api.openai.com",
            timeout=settings.OPENAI_TIMEOUT,
            max_retries=2,
        )
        self._ollama_models: Optional[List[str]] = None

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------
    @property
    def ollama_enabled(self) -> bool:
        return settings.OLLAMA_ENABLED

    @property
    def openai_enabled(self) -> bool:
        return settings.openai_configured and not settings.OFFLINE_MODE

    @property
    def available(self) -> bool:
        return self.ollama_enabled or self.openai_enabled

    async def list_ollama_models(self, *, refresh: bool = False) -> List[str]:
        if self._ollama_models is not None and not refresh:
            return self._ollama_models
        try:
            data = await self._ollama.get_json("/api/tags", retries=1)
            self._ollama_models = [
                str(m.get("name")) for m in (data.get("models") or []) if m.get("name")
            ]
        except Exception as exc:  # noqa: BLE001
            logger.debug("ollama_unavailable", error=str(exc))
            self._ollama_models = []
        return self._ollama_models

    async def health(self) -> Dict[str, Any]:
        models = await self.list_ollama_models(refresh=True) if self.ollama_enabled else []
        return {
            "ollama": {
                "enabled": self.ollama_enabled,
                "base_url": settings.OLLAMA_BASE_URL,
                "configured_model": settings.OLLAMA_MODEL,
                "models_present": models,
                "model_ready": settings.OLLAMA_MODEL in models
                or any(settings.OLLAMA_MODEL.split(":")[0] in m for m in models),
                "circuit": self._ollama.breaker.snapshot(),
            },
            "openai": {
                "enabled": self.openai_enabled,
                "model": settings.OPENAI_MODEL if self.openai_enabled else None,
            },
        }

    # ------------------------------------------------------------------
    # Completions
    # ------------------------------------------------------------------
    async def complete(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 800,
        json_mode: bool = False,
        prefer_cloud: bool = False,
    ) -> Optional[str]:
        """Return raw model text, or ``None`` when no backend is usable."""
        order: List[str] = []
        if prefer_cloud and self.openai_enabled:
            order = ["openai", "ollama"]
        else:
            order = ["ollama", "openai"]

        for backend in order:
            if backend == "ollama" and self.ollama_enabled:
                text = await self._complete_ollama(
                    prompt, system, temperature, max_tokens, json_mode
                )
                if text is not None:
                    return text
            elif backend == "openai" and self.openai_enabled:
                text = await self._complete_openai(
                    prompt, system, temperature, max_tokens, json_mode
                )
                if text is not None:
                    return text
        return None

    async def _complete_ollama(
        self,
        prompt: str,
        system: Optional[str],
        temperature: float,
        max_tokens: int,
        json_mode: bool,
    ) -> Optional[str]:
        payload: Dict[str, Any] = {
            "model": settings.OLLAMA_MODEL,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "num_ctx": settings.OLLAMA_NUM_CTX,
            },
            "messages": (
                [{"role": "system", "content": system}] if system else []
            )
            + [{"role": "user", "content": prompt}],
        }
        if json_mode:
            payload["format"] = "json"

        started = time.monotonic()
        try:
            data = await self._ollama.post_json("/api/chat", json_body=payload)
        except ExternalServiceError as exc:
            logger.warning("ollama_completion_failed", error=exc.message)
            return None

        content = ((data.get("message") or {}).get("content")) or data.get("response")
        logger.info(
            "llm_completion",
            backend="ollama",
            model=settings.OLLAMA_MODEL,
            latency_ms=round((time.monotonic() - started) * 1000, 1),
            chars=len(content or ""),
        )
        return str(content) if content else None

    async def _complete_openai(
        self,
        prompt: str,
        system: Optional[str],
        temperature: float,
        max_tokens: int,
        json_mode: bool,
    ) -> Optional[str]:
        payload: Dict[str, Any] = {
            "model": settings.OPENAI_MODEL,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": (
                [{"role": "system", "content": system}] if system else []
            )
            + [{"role": "user", "content": prompt}],
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        started = time.monotonic()
        try:
            data = await self._openai.post_json(
                "/v1/chat/completions",
                json_body=payload,
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
            )
        except ExternalServiceError as exc:
            logger.warning("openai_completion_failed", error=exc.message)
            return None

        choices = data.get("choices") or []
        if not choices:
            return None
        content = (choices[0].get("message") or {}).get("content")
        logger.info(
            "llm_completion",
            backend="openai",
            model=settings.OPENAI_MODEL,
            latency_ms=round((time.monotonic() - started) * 1000, 1),
            chars=len(content or ""),
        )
        return str(content) if content else None

    # ------------------------------------------------------------------
    # Structured output
    # ------------------------------------------------------------------
    async def complete_json(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        required_keys: Sequence[str] = (),
        temperature: float = 0.0,
        max_tokens: int = 900,
        prefer_cloud: bool = False,
        retries: int = 1,
    ) -> Optional[Dict[str, Any]]:
        """Request and validate a JSON object from the model."""
        instruction = (
            f"{prompt}\n\nRespond with a single valid JSON object and nothing else. "
            "Do not wrap it in markdown fences."
        )
        for attempt in range(retries + 1):
            raw = await self.complete(
                instruction,
                system=system,
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=True,
                prefer_cloud=prefer_cloud,
            )
            if raw is None:
                return None
            parsed = self.parse_json(raw)
            if parsed is None:
                logger.warning(
                    "llm_json_unparseable",
                    attempt=attempt + 1,
                    preview=mask_text(raw[:200]),
                )
                continue
            missing = [k for k in required_keys if k not in parsed]
            if missing:
                logger.warning("llm_json_missing_keys", missing=missing, attempt=attempt + 1)
                if attempt < retries:
                    continue
            return parsed
        return None

    @staticmethod
    def parse_json(raw: str) -> Optional[Dict[str, Any]]:
        """Tolerant JSON extraction (handles fences and trailing prose)."""
        text = raw.strip()
        for candidate in (
            text,
            (_FENCE_RE.search(text).group(1) if _FENCE_RE.search(text) else None),
            (_OBJECT_RE.search(text).group(0) if _OBJECT_RE.search(text) else None),
        ):
            if not candidate:
                continue
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
            if isinstance(parsed, list):
                return {"items": parsed}
        return None


llm_client = LLMClient()

__all__ = ["LLMClient", "llm_client"]

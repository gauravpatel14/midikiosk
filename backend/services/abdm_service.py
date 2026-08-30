"""Deprecated shim — ABDM logic now lives in :mod:`backend.services.abdm`.

Kept so existing imports (``from backend.services.abdm_service import
abdm_service``) continue to resolve. The mocked search/create helpers that used
to live here were removed: they fabricated patient identities, which is unsafe
in a clinical system. Use :mod:`backend.services.abdm.abha` instead.
"""

from __future__ import annotations

from backend.services.abdm import (
    AbdmClient,
    AbdmConsentService,
    AbdmHieService,
    AbhaService,
    abdm_client,
    abdm_consent_service,
    abdm_hie_service,
    abha_service,
)

#: Historical name.
abdm_service = abha_service
AbdmSandboxService = AbhaService

__all__ = [
    "AbdmClient",
    "abdm_client",
    "AbhaService",
    "abha_service",
    "AbdmSandboxService",
    "abdm_service",
    "AbdmConsentService",
    "abdm_consent_service",
    "AbdmHieService",
    "abdm_hie_service",
]

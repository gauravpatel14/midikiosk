"""ABDM (Ayushman Bharat Digital Mission) integration package.

Modules
-------
``client``
    OAuth2 session management against the ABDM gateway with token caching and
    RSA encryption of Aadhaar/OTP payloads.
``abha``
    ABHA number/address search, Aadhaar & mobile eKYC enrolment (OTP flow),
    profile retrieval and ABHA card download.
``consent``
    HIP-side consent artefact handling: request notification, artefact fetch,
    storage and revocation.
``hie``
    Health Information Exchange: care-context linking and FHIR bundle transfer
    with the ABDM-mandated ECDH/AES encryption envelope.
"""

from backend.services.abdm.abha import AbhaService, abha_service
from backend.services.abdm.client import AbdmClient, abdm_client
from backend.services.abdm.consent import AbdmConsentService, abdm_consent_service
from backend.services.abdm.hie import AbdmHieService, abdm_hie_service

#: Historical alias retained so ``from backend.services.abdm_service import
#: abdm_service`` keeps working.
abdm_service = abha_service

__all__ = [
    "AbdmClient",
    "abdm_client",
    "AbhaService",
    "abha_service",
    "AbdmConsentService",
    "abdm_consent_service",
    "AbdmHieService",
    "abdm_hie_service",
    "abdm_service",
]

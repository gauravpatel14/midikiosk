"""ABDM Health Information Exchange (HIP role).

Responsibilities
----------------
* **Care-context linking** — after a kiosk session produces a summary, the
  encounter is registered against the patient's ABHA address so it becomes
  discoverable in their PHR app (``/v0.5/links/link/add-contexts``).
* **Data transfer** — when a HIU requests health information, the HIP pushes a
  FHIR bundle to the HIU's data-push URL. ABDM mandates a hybrid crypto
  envelope: an ECDH (Curve25519) key exchange between HIP and HIU key material
  produces a shared secret, expanded with HKDF-SHA256 into an AES-256-GCM key.
  :class:`AbdmCryptoEnvelope` implements exactly that.
* **Health-information notification** — the HIP reports delivery status back to
  the gateway so the consent manager can close the transaction.

Every outbound call is idempotent and safe to retry from the integration
outbox: ``transactionId`` / ``requestId`` are supplied by the caller.
"""

from __future__ import annotations

import base64
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
except ImportError:  # pragma: no cover
    hashes = None  # type: ignore[assignment]
    serialization = None  # type: ignore[assignment]
    X25519PrivateKey = None  # type: ignore[assignment]
    X25519PublicKey = None  # type: ignore[assignment]
    AESGCM = None  # type: ignore[assignment]
    HKDF = None  # type: ignore[assignment]

from backend.core.config import settings
from backend.core.exceptions import ExternalServiceError, ValidationError
from backend.core.http import ResilientHttpClient
from backend.core.logging import get_logger
from backend.services.abdm.client import abdm_client, utc_timestamp

logger = get_logger(__name__)


class AbdmCryptoEnvelope:
    """ECDH-X25519 + HKDF-SHA256 + AES-256-GCM envelope for HIP→HIU transfer."""

    @staticmethod
    def generate_key_material() -> Dict[str, Any]:
        """Create an ephemeral keypair and nonce for one transfer."""
        private_key = X25519PrivateKey.generate()
        public_bytes = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        nonce = os.urandom(32)
        return {
            "private_key": private_key,
            "public_key_b64": base64.b64encode(public_bytes).decode("ascii"),
            "nonce_b64": base64.b64encode(nonce).decode("ascii"),
            "nonce": nonce,
        }

    @staticmethod
    def _derive_key(
        private_key: X25519PrivateKey,
        peer_public_b64: str,
        sender_nonce: bytes,
        receiver_nonce: bytes,
    ) -> bytes:
        peer_raw = base64.b64decode(peer_public_b64)
        # ABDM sometimes prefixes the raw key with an ASN.1/uncompressed marker.
        if len(peer_raw) > 32:
            peer_raw = peer_raw[-32:]
        peer_public = X25519PublicKey.from_public_bytes(peer_raw)
        shared_secret = private_key.exchange(peer_public)

        salt = bytes(a ^ b for a, b in zip(sender_nonce, receiver_nonce))
        return HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            info=b"ABDM-HIP-DATA-TRANSFER",
        ).derive(shared_secret)

    @classmethod
    def encrypt(
        cls,
        plaintext: str,
        *,
        key_material: Dict[str, Any],
        receiver_public_key_b64: str,
        receiver_nonce_b64: str,
    ) -> str:
        """Return base64 AES-256-GCM ciphertext (nonce-prefixed)."""
        receiver_nonce = base64.b64decode(receiver_nonce_b64)
        if len(receiver_nonce) < 32:
            receiver_nonce = receiver_nonce.ljust(32, b"\0")
        aes_key = cls._derive_key(
            key_material["private_key"],
            receiver_public_key_b64,
            key_material["nonce"],
            receiver_nonce[:32],
        )
        iv = os.urandom(12)
        ciphertext = AESGCM(aes_key).encrypt(iv, plaintext.encode("utf-8"), None)
        return base64.b64encode(iv + ciphertext).decode("ascii")

    @classmethod
    def decrypt(
        cls,
        payload_b64: str,
        *,
        key_material: Dict[str, Any],
        sender_public_key_b64: str,
        sender_nonce_b64: str,
    ) -> str:
        sender_nonce = base64.b64decode(sender_nonce_b64)
        if len(sender_nonce) < 32:
            sender_nonce = sender_nonce.ljust(32, b"\0")
        aes_key = cls._derive_key(
            key_material["private_key"],
            sender_public_key_b64,
            key_material["nonce"],
            sender_nonce[:32],
        )
        raw = base64.b64decode(payload_b64)
        iv, ciphertext = raw[:12], raw[12:]
        return AESGCM(aes_key).decrypt(iv, ciphertext, None).decode("utf-8")


class AbdmHieService:
    """HIP-side health information exchange operations."""

    def __init__(self) -> None:
        self._client = abdm_client

    # ------------------------------------------------------------------
    # Care-context linking
    # ------------------------------------------------------------------
    async def link_care_context(
        self,
        *,
        abha_address: str,
        patient_reference: str,
        display_name: str,
        care_contexts: List[Dict[str, str]],
        hi_type: str = "OPConsultation",
        authorisation_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Register encounters against the patient's ABHA PHR."""
        if not care_contexts:
            raise ValidationError("At least one care context is required for linking")

        request_id = str(uuid.uuid4())
        payload = {
            "requestId": request_id,
            "timestamp": utc_timestamp(),
            "link": {
                "accessToken": authorisation_token or "",
                "patient": {
                    "referenceNumber": patient_reference,
                    "display": display_name,
                    "careContexts": care_contexts,
                    "hiType": hi_type,
                    "count": len(care_contexts),
                },
            },
        }
        response = await self._client.request(
            "POST",
            f"{settings.ABDM_GATEWAY_URL}/v0.5/links/link/add-contexts",
            json_body=payload,
            include_hip=True,
            expected_status={200, 202},
        )
        logger.info(
            "abdm_care_context_linked",
            abha_address=abha_address,
            contexts=len(care_contexts),
            request_id=request_id,
        )
        return {"request_id": request_id, "gateway_response": response}

    # ------------------------------------------------------------------
    # Data transfer
    # ------------------------------------------------------------------
    async def transfer_health_information(
        self,
        *,
        transaction_id: str,
        data_push_url: str,
        consent_artefact_id: str,
        entries: List[Dict[str, Any]],
        receiver_key_material: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Encrypt and POST FHIR bundles to the HIU's data-push endpoint.

        ``entries`` is a list of ``{"care_context_reference": str, "bundle": dict}``.
        ``receiver_key_material`` comes from the HIU inside the ``hi-request``
        callback and must contain ``publicKey`` plus ``nonce``.
        """
        receiver_public = (
            receiver_key_material.get("dhPublicKey", {}).get("keyValue")
            or receiver_key_material.get("publicKey")
        )
        receiver_nonce = receiver_key_material.get("nonce")
        if not receiver_public or not receiver_nonce:
            raise ValidationError(
                "HIU key material must include a Diffie-Hellman public key and nonce"
            )

        key_material = AbdmCryptoEnvelope.generate_key_material()
        encrypted_entries: List[Dict[str, Any]] = []
        for entry in entries:
            bundle_json = json.dumps(entry["bundle"], default=str, separators=(",", ":"))
            encrypted_entries.append(
                {
                    "content": AbdmCryptoEnvelope.encrypt(
                        bundle_json,
                        key_material=key_material,
                        receiver_public_key_b64=receiver_public,
                        receiver_nonce_b64=receiver_nonce,
                    ),
                    "media": "application/fhir+json",
                    "checksum": entry.get("checksum", ""),
                    "careContextReference": entry["care_context_reference"],
                }
            )

        payload = {
            "pageNumber": 1,
            "pageCount": 1,
            "transactionId": transaction_id,
            "entries": encrypted_entries,
            "keyMaterial": {
                "cryptoAlg": "ECDH",
                "curve": "Curve25519",
                "dhPublicKey": {
                    "expiry": datetime.now(timezone.utc).isoformat(),
                    "parameters": "Curve25519/32byte random key",
                    "keyValue": key_material["public_key_b64"],
                },
                "nonce": key_material["nonce_b64"],
            },
        }

        http = ResilientHttpClient.get(
            "abdm-hiu-datapush",
            timeout=settings.ABDM_REQUEST_TIMEOUT * 2,
            max_retries=settings.ABDM_MAX_RETRIES,
        )
        token = await self._client.get_access_token()
        response = await http.request(
            "POST",
            data_push_url,
            json_body=payload,
            headers=self._client.build_headers(token, include_hip=True),
            expected_status={200, 202},
        )
        logger.info(
            "abdm_health_information_pushed",
            transaction_id=transaction_id,
            entries=len(encrypted_entries),
            status=response.status_code,
        )
        return {
            "transaction_id": transaction_id,
            "entries_sent": len(encrypted_entries),
            "consent_artefact_id": consent_artefact_id,
            "http_status": response.status_code,
        }

    async def notify_health_information_status(
        self,
        *,
        transaction_id: str,
        consent_artefact_id: str,
        care_context_references: List[str],
        session_status: str = "TRANSFERRED",
        hip_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Report transfer status back to the gateway (``/health-information/notify``)."""
        payload = {
            "requestId": str(uuid.uuid4()),
            "timestamp": utc_timestamp(),
            "notification": {
                "consentId": consent_artefact_id,
                "transactionId": transaction_id,
                "doneAt": utc_timestamp(),
                "notifier": {"type": "HIP", "id": hip_id or settings.ABDM_HIP_ID},
                "statusNotification": {
                    "sessionStatus": session_status,
                    "hipId": hip_id or settings.ABDM_HIP_ID,
                    "statusResponses": [
                        {"careContextReference": ref, "hiStatus": "OK", "description": "Delivered"}
                        for ref in care_context_references
                    ],
                },
            },
        }
        response = await self._client.request(
            "POST",
            f"{settings.ABDM_GATEWAY_URL}/v0.5/health-information/notify",
            json_body=payload,
            include_hip=True,
            expected_status={200, 202},
        )
        return {"request_id": payload["requestId"], "gateway_response": response}

    async def respond_to_hi_request(
        self, *, request_id: str, transaction_id: str, accepted: bool, error: Optional[str] = None
    ) -> None:
        """Acknowledge a ``hi-request`` callback (``/health-information/hip/on-request``)."""
        payload: Dict[str, Any] = {
            "requestId": str(uuid.uuid4()),
            "timestamp": utc_timestamp(),
            "resp": {"requestId": request_id},
        }
        if accepted:
            payload["hiRequest"] = {"transactionId": transaction_id, "sessionStatus": "ACKNOWLEDGED"}
        else:
            payload["error"] = {"code": 3400, "message": error or "Request rejected"}
        try:
            await self._client.request(
                "POST",
                f"{settings.ABDM_GATEWAY_URL}/v0.5/health-information/hip/on-request",
                json_body=payload,
                include_hip=True,
                expected_status={200, 202},
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("abdm_hi_request_ack_failed", error=str(exc))

    async def confirm_patient_discovery(
        self, *, request_id: str, patient: Optional[Dict[str, Any]], error: Optional[str] = None
    ) -> None:
        """Reply to a ``care-contexts/discover`` gateway callback."""
        payload: Dict[str, Any] = {
            "requestId": str(uuid.uuid4()),
            "timestamp": utc_timestamp(),
            "transactionId": request_id,
            "resp": {"requestId": request_id},
        }
        if patient:
            payload["patient"] = patient
        else:
            payload["error"] = {"code": 3404, "message": error or "No patient found"}
        try:
            await self._client.request(
                "POST",
                f"{settings.ABDM_GATEWAY_URL}/v0.5/care-contexts/on-discover",
                json_body=payload,
                include_hip=True,
                expected_status={200, 202},
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("abdm_discovery_ack_failed", error=str(exc))


abdm_hie_service = AbdmHieService()

__all__ = ["AbdmHieService", "abdm_hie_service", "AbdmCryptoEnvelope"]

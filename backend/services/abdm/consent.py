"""ABDM consent artefact management (HIP side).

Flow implemented (ABDM M2 "Consent" specification):

1. The Consent Manager notifies the HIP at
   ``POST /v0.5/consents/hip/notify`` with a consent artefact id and status.
   MediKiosk exposes this as the ``/abdm/webhooks/consents/hip/notify``
   endpoint; this service persists the artefact and acknowledges the gateway
   with ``POST {gateway}/v0.5/consents/hip/on-notify``.
2. When a HIU later requests data, the HIP validates the referenced artefact is
   ``GRANTED``, unexpired, and covers the requested hi-types/date-range before
   releasing any bundle. :meth:`assert_active_artefact` performs that check.
3. Revocation arrives through the same notify channel with ``status=REVOKED``;
   the artefact is marked revoked and dependent care-contexts stop being served.

Everything is persisted in :class:`~backend.models.AbdmConsentArtefact` so the
decision to release data is auditable years later.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.exceptions import ConsentRequiredError, NotFoundError
from backend.core.logging import get_logger
from backend.services.abdm.client import abdm_client, utc_timestamp

logger = get_logger(__name__)


def _parse_iso(value: Any) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


class AbdmConsentService:
    """Persist and evaluate ABDM consent artefacts."""

    def __init__(self) -> None:
        self._client = abdm_client

    # ------------------------------------------------------------------
    # Inbound notification handling
    # ------------------------------------------------------------------
    async def handle_hip_notification(
        self, db: AsyncSession, notification: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Persist a consent artefact notification from the Consent Manager."""
        from backend.models import AbdmConsentArtefact, Patient

        notify = notification.get("notification") or {}
        status = str(notify.get("status") or "GRANTED").upper()
        artefacts: List[Dict[str, Any]] = notify.get("consentArtefacts") or []
        consent_detail = notify.get("consentDetail") or {}

        # Revocations carry only ids; grants carry ids that must be fetched.
        artefact_ids = [
            str(a.get("id"))
            for a in artefacts
            if isinstance(a, dict) and a.get("id")
        ]
        if not artefact_ids and consent_detail.get("consentId"):
            artefact_ids = [str(consent_detail["consentId"])]

        processed: List[str] = []
        for artefact_id in artefact_ids:
            detail: Dict[str, Any] = {}
            if status == "GRANTED":
                try:
                    detail = await self.fetch_artefact(artefact_id)
                except Exception as exc:  # noqa: BLE001 - keep processing others
                    logger.error(
                        "abdm_artefact_fetch_failed", artefact_id=artefact_id, error=str(exc)
                    )

            payload = detail.get("consentDetail") or detail or consent_detail
            abha_address = None
            patient_block = payload.get("patient") if isinstance(payload, dict) else None
            if isinstance(patient_block, dict):
                abha_address = patient_block.get("id")

            existing = await db.scalar(
                select(AbdmConsentArtefact).where(
                    AbdmConsentArtefact.consent_artefact_id == artefact_id
                )
            )
            permission = payload.get("permission") if isinstance(payload, dict) else None
            purpose = payload.get("purpose") if isinstance(payload, dict) else None
            expires_at = None
            if isinstance(permission, dict):
                expires_at = _parse_iso(permission.get("dataEraseAt"))

            patient_id = None
            if abha_address:
                patient_id = await db.scalar(
                    select(Patient.id).where(Patient.abha_address == abha_address)
                )

            if existing is None:
                existing = AbdmConsentArtefact(
                    id=uuid.uuid4(),
                    consent_artefact_id=artefact_id,
                    consent_request_id=str(notify.get("consentRequestId") or "") or None,
                )
                db.add(existing)

            existing.status = status
            existing.abha_address = abha_address
            existing.patient_id = patient_id
            existing.purpose_code = (
                purpose.get("code") if isinstance(purpose, dict) else None
            )
            existing.hi_types = {"hiTypes": payload.get("hiTypes")} if isinstance(payload, dict) else None
            existing.permission = permission if isinstance(permission, dict) else None
            existing.signature = detail.get("signature")
            existing.raw_artefact = detail or notification
            existing.expires_at = expires_at
            if status == "GRANTED":
                existing.granted_at = _parse_iso(
                    payload.get("consentDetail", {}).get("createdAt")
                    if isinstance(payload, dict)
                    else None
                ) or datetime.now(timezone.utc)
            if status in {"REVOKED", "EXPIRED", "DENIED"}:
                existing.revoked_at = datetime.now(timezone.utc)

            processed.append(artefact_id)

        await db.flush()
        logger.info("abdm_consent_notification_processed", status=status, count=len(processed))

        # Acknowledge the gateway (best-effort; failure is retried by the outbox).
        await self.acknowledge_notification(
            request_id=str(notification.get("requestId") or uuid.uuid4()),
            artefact_ids=processed,
        )
        return {"processed": processed, "status": status}

    async def acknowledge_notification(
        self, *, request_id: str, artefact_ids: List[str]
    ) -> None:
        """Send ``consents/hip/on-notify`` back to the gateway."""
        if not self._client.enabled or not artefact_ids:
            return
        payload = {
            "requestId": str(uuid.uuid4()),
            "timestamp": utc_timestamp(),
            "acknowledgement": [
                {"status": "OK", "consentId": artefact_id} for artefact_id in artefact_ids
            ],
            "resp": {"requestId": request_id},
        }
        try:
            await self._client.request(
                "POST",
                f"{settings.ABDM_GATEWAY_URL}/v0.5/consents/hip/on-notify",
                json_body=payload,
                include_hip=True,
                expected_status={200, 202},
            )
        except Exception as exc:  # noqa: BLE001 - ack failure must not break intake
            logger.warning("abdm_consent_ack_failed", error=str(exc))

    async def fetch_artefact(self, artefact_id: str) -> Dict[str, Any]:
        """Fetch the full artefact from the Consent Manager."""
        return await self._client.request(
            "GET",
            f"{settings.ABDM_GATEWAY_URL}/v0.5/consents/{artefact_id}",
            include_hip=True,
        )

    async def revoke_consent(
        self, consent_id: str, reason: str = "Patient requested revocation"
    ) -> Dict[str, Any]:
        """Send a consent revocation request to the ABDM Consent Manager (v0.5 POST /v0.5/consents/revoke)."""
        if not self._client.enabled:
            logger.info("abdm_revocation_skipped_client_disabled", consent_id=consent_id)
            return {"status": "SKIPPED", "consentId": consent_id}

        payload = {
            "requestId": str(uuid.uuid4()),
            "timestamp": utc_timestamp(),
            "consent": {
                "consentId": consent_id,
                "reason": reason,
            },
        }
        return await self._client.request(
            "POST",
            f"{settings.ABDM_GATEWAY_URL}/v0.5/consents/revoke",
            json_body=payload,
            include_hip=True,
            expected_status={200, 202},
        )

    # ------------------------------------------------------------------
    # Authorisation checks
    # ------------------------------------------------------------------
    async def get_artefact(
        self, db: AsyncSession, artefact_id: str
    ) -> "AbdmConsentArtefact":
        from backend.models import AbdmConsentArtefact

        artefact = await db.scalar(
            select(AbdmConsentArtefact).where(
                AbdmConsentArtefact.consent_artefact_id == artefact_id
            )
        )
        if artefact is None:
            raise NotFoundError(f"Consent artefact {artefact_id} is not known to this HIP")
        return artefact

    async def assert_active_artefact(
        self,
        db: AsyncSession,
        artefact_id: str,
        *,
        required_hi_types: Optional[List[str]] = None,
        at: Optional[datetime] = None,
    ) -> "AbdmConsentArtefact":
        """Raise unless the artefact permits the requested data flow right now."""
        artefact = await self.get_artefact(db, artefact_id)
        moment = at or datetime.now(timezone.utc)

        if not artefact.is_active(moment):
            raise ConsentRequiredError(
                "The referenced ABDM consent artefact is not active",
                details={
                    "artefact_id": artefact_id,
                    "status": artefact.status,
                    "expires_at": artefact.expires_at.isoformat()
                    if artefact.expires_at
                    else None,
                },
            )

        if required_hi_types:
            granted = set()
            if isinstance(artefact.hi_types, dict):
                granted = {str(x) for x in (artefact.hi_types.get("hiTypes") or [])}
            missing = [t for t in required_hi_types if t not in granted]
            if granted and missing:
                raise ConsentRequiredError(
                    "The consent artefact does not cover the requested health information types",
                    details={"artefact_id": artefact_id, "missing_hi_types": missing},
                )
        return artefact

    async def list_artefacts_for_patient(
        self, db: AsyncSession, patient_id: uuid.UUID, *, active_only: bool = True
    ) -> List["AbdmConsentArtefact"]:
        from backend.models import AbdmConsentArtefact

        stmt = select(AbdmConsentArtefact).where(AbdmConsentArtefact.patient_id == patient_id)
        if active_only:
            stmt = stmt.where(AbdmConsentArtefact.status == "GRANTED")
        stmt = stmt.order_by(AbdmConsentArtefact.created_at.desc())
        rows = await db.execute(stmt)
        artefacts = list(rows.scalars())
        if active_only:
            now = datetime.now(timezone.utc)
            artefacts = [a for a in artefacts if a.is_active(now)]
        return artefacts

    # ------------------------------------------------------------------
    # HIU-initiated consent request (used when the hospital pulls history)
    # ------------------------------------------------------------------
    async def request_consent(
        self,
        *,
        abha_address: str,
        purpose_code: str = "CAREMGT",
        hi_types: Optional[List[str]] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        expiry_days: int = 30,
        requester_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Raise a consent request as a Health Information User."""
        now = datetime.now(timezone.utc)
        hi_types = hi_types or [
            "OPConsultation",
            "Prescription",
            "DiagnosticReport",
            "DischargeSummary",
        ]
        payload = {
            "requestId": str(uuid.uuid4()),
            "timestamp": utc_timestamp(),
            "consent": {
                "purpose": {
                    "text": "Care Management",
                    "code": purpose_code,
                    "refUri": "http://terminology.hl7.org/ValueSet/v3-PurposeOfUse",
                },
                "patient": {"id": abha_address},
                "hiu": {"id": settings.ABDM_HIP_ID},
                "requester": {
                    "name": requester_name or settings.ABDM_HIP_NAME,
                    "identifier": {
                        "type": "REGNO",
                        "value": settings.HOSPITAL_FACILITY_ID,
                        "system": "https://facility.abdm.gov.in",
                    },
                },
                "hiTypes": hi_types,
                "permission": {
                    "accessMode": "VIEW",
                    "dateRange": {
                        "from": (from_date or (now - timedelta(days=365 * 3))).isoformat(),
                        "to": (to_date or now).isoformat(),
                    },
                    "dataEraseAt": (now + timedelta(days=expiry_days)).isoformat(),
                    "frequency": {"unit": "HOUR", "value": 1, "repeats": 0},
                },
            },
        }
        response = await self._client.request(
            "POST",
            f"{settings.ABDM_GATEWAY_URL}/v0.5/consent-requests/init",
            json_body=payload,
            include_hip=True,
            expected_status={200, 202},
        )
        logger.info("abdm_consent_requested", abha_address=abha_address)
        return {"request_id": payload["requestId"], "gateway_response": response}


abdm_consent_service = AbdmConsentService()

__all__ = ["AbdmConsentService", "abdm_consent_service"]

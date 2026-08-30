"""ABHA (Ayushman Bharat Health Account) service.

Implements the ABDM ABHA v3 APIs used by the kiosk registration flow:

============================  =====================================================
Operation                     Endpoint (relative to ``ABDM_ABHA_URL``)
============================  =====================================================
Aadhaar OTP request           ``/v3/enrollment/request/otp``
Aadhaar OTP verify + enrol    ``/v3/enrollment/enrol/byAadhaar``
Mobile OTP request            ``/v3/enrollment/request/otp`` (scope ``abha-enrol``)
Mobile OTP verify             ``/v3/enrollment/auth/byAbdm``
ABHA address suggestions      ``/v3/enrollment/enrol/suggestion``
ABHA address creation         ``/v3/enrollment/enrol/abha-address``
Login OTP (existing ABHA)     ``/v3/profile/login/request/otp``
Login verify                  ``/v3/profile/login/verify``
Profile fetch                 ``/v3/profile/account``
ABHA card (PNG/PDF)           ``/v3/profile/account/abha-card``
============================  =====================================================

Design decisions
----------------
* Aadhaar and OTP values are RSA-encrypted by :class:`AbdmClient` before leaving
  the process; the plaintext Aadhaar is never logged nor persisted — only a
  peppered HMAC token (``hash_aadhaar``) is stored for re-identification.
* The multi-step OTP flow is stateful. ABDM returns a ``txnId`` that must be
  echoed on verification. The kiosk is stateless between screens, so the txn is
  held in Redis for 10 minutes keyed by an opaque handle we hand to the client.
  The kiosk therefore never has to store, and cannot tamper with, ABDM state.
* Every response is normalised into a stable internal shape
  (:meth:`AbhaService.normalise_profile`) so routers and FHIR builders do not
  depend on ABDM's changing field names.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from backend.core.cache import cache
from backend.core.config import settings
from backend.core.crypto import generate_token, verhoeff_validate
from backend.core.exceptions import ExternalServiceError, NotFoundError, ValidationError
from backend.core.logging import get_logger
from backend.services.abdm.client import abdm_client

logger = get_logger(__name__)

TXN_TTL_SECONDS = 600  # ABDM transactions expire in ~10 minutes
TXN_CACHE_PREFIX = "abdm:txn:"

GENDER_TO_ABDM = {"male": "M", "female": "F", "other": "O", "m": "M", "f": "F", "o": "O"}
ABDM_TO_GENDER = {"M": "Male", "F": "Female", "O": "Other", "U": "Other"}


class AbhaService:
    """High-level ABHA operations used by the kiosk registration router."""

    def __init__(self) -> None:
        self._client = abdm_client

    # ------------------------------------------------------------------
    # Transaction handle management
    # ------------------------------------------------------------------
    async def _store_txn(self, txn_id: str, context: Dict[str, Any]) -> str:
        """Persist ABDM's ``txnId`` and return an opaque handle for the kiosk."""
        handle = generate_token(18)
        await cache.set(
            f"{TXN_CACHE_PREFIX}{handle}",
            {"txn_id": txn_id, "created_at": datetime.utcnow().isoformat(), **context},
            TXN_TTL_SECONDS,
        )
        return handle

    async def _load_txn(self, handle: str) -> Dict[str, Any]:
        data = await cache.get(f"{TXN_CACHE_PREFIX}{handle}")
        if not isinstance(data, dict) or not data.get("txn_id"):
            raise ValidationError(
                "This verification session has expired. Please request a new OTP.",
                details={"handle": handle[:6] + "…"},
            )
        return data

    async def _clear_txn(self, handle: str) -> None:
        await cache.delete(f"{TXN_CACHE_PREFIX}{handle}")

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------
    @staticmethod
    def validate_aadhaar(aadhaar: str) -> str:
        digits = "".join(ch for ch in str(aadhaar) if ch.isdigit())
        if len(digits) != 12:
            raise ValidationError("Aadhaar number must contain exactly 12 digits")
        if not verhoeff_validate(digits):
            raise ValidationError("Aadhaar number failed checksum validation")
        return digits

    @staticmethod
    def validate_mobile(mobile: str) -> str:
        digits = "".join(ch for ch in str(mobile) if ch.isdigit())
        if digits.startswith("91") and len(digits) == 12:
            digits = digits[2:]
        if len(digits) != 10 or digits[0] not in "6789":
            raise ValidationError("Enter a valid 10-digit Indian mobile number")
        return digits

    @staticmethod
    def is_abha_number(value: str) -> bool:
        return bool(re.fullmatch(r"\d{2}-?\d{4}-?\d{4}-?\d{4}", value.strip()))

    @staticmethod
    def normalise_abha_number(value: str) -> str:
        digits = "".join(ch for ch in value if ch.isdigit())
        if len(digits) != 14:
            return value.strip()
        return f"{digits[:2]}-{digits[2:6]}-{digits[6:10]}-{digits[10:]}"

    # ------------------------------------------------------------------
    # Response normalisation
    # ------------------------------------------------------------------
    def normalise_profile(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Map an ABDM profile/enrolment response to MediKiosk's patient shape."""
        profile = payload.get("ABHAProfile") or payload.get("abhaProfile") or payload
        if not isinstance(profile, dict):
            profile = {}

        first = (profile.get("firstName") or "").strip()
        middle = (profile.get("middleName") or "").strip()
        last = (profile.get("lastName") or "").strip()
        full = (profile.get("name") or " ".join(p for p in (first, middle, last) if p)).strip()
        if not first and full:
            parts = full.split()
            first = parts[0]
            last = " ".join(parts[1:]) if len(parts) > 1 else last

        address_obj = profile.get("address")
        if isinstance(address_obj, dict):
            address_line = ", ".join(
                str(address_obj.get(k)).strip()
                for k in ("house", "street", "landmark", "locality", "village")
                if address_obj.get(k)
            )
            district = address_obj.get("district") or address_obj.get("districtName")
            state = address_obj.get("state") or address_obj.get("stateName")
            pincode = address_obj.get("pincode") or address_obj.get("pinCode")
        else:
            address_line = profile.get("address") if isinstance(profile.get("address"), str) else None
            district = profile.get("districtName") or profile.get("district")
            state = profile.get("stateName") or profile.get("state")
            pincode = profile.get("pinCode") or profile.get("pincode")

        dob = self._parse_dob(profile)
        abha_number = profile.get("ABHANumber") or profile.get("abhaNumber") or profile.get("healthIdNumber")
        abha_address = (
            profile.get("phrAddress")
            or profile.get("abhaAddress")
            or profile.get("healthId")
            or profile.get("preferredAbhaAddress")
        )
        if isinstance(abha_address, list):
            abha_address = abha_address[0] if abha_address else None

        return {
            "abha_id": self.normalise_abha_number(str(abha_number)) if abha_number else None,
            "abha_address": str(abha_address) if abha_address else None,
            "first_name": first or "Unknown",
            "last_name": last or None,
            "full_name": full or first or "Unknown",
            "gender": ABDM_TO_GENDER.get(str(profile.get("gender", "")).upper(), "Other"),
            "date_of_birth": dob.isoformat() if dob else None,
            "age": self._age_from_dob(dob),
            "phone_number": profile.get("mobile") or profile.get("phoneNumber"),
            "address_line": address_line or None,
            "district": district,
            "state": state,
            "pincode": str(pincode) if pincode else None,
            "preferred_language": settings.DEFAULT_LANGUAGE,
            "kyc_verified": bool(profile.get("kycVerified", profile.get("kycStatus") == "VERIFIED")),
            "abha_status": profile.get("status") or profile.get("abhaStatus"),
        }

    @staticmethod
    def _parse_dob(profile: Dict[str, Any]) -> Optional[date]:
        raw = profile.get("dob") or profile.get("dateOfBirth") or profile.get("birthDate")
        if raw:
            text = str(raw).strip()
            for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
                try:
                    return datetime.strptime(text, fmt).date()
                except ValueError:
                    continue
        year = profile.get("yearOfBirth") or profile.get("birthYear")
        if year:
            try:
                month = int(profile.get("monthOfBirth") or 1)
                day = int(profile.get("dayOfBirth") or 1)
                return date(int(year), max(1, min(12, month)), max(1, min(28, day)))
            except (TypeError, ValueError):
                return None
        return None

    @staticmethod
    def _age_from_dob(dob: Optional[date]) -> Optional[int]:
        if not dob:
            return None
        today = date.today()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    # ==================================================================
    # Aadhaar enrolment (create a new ABHA)
    # ==================================================================
    async def request_aadhaar_otp(self, aadhaar: str) -> Dict[str, Any]:
        """Step 1 — trigger the UIDAI OTP for ABHA enrolment."""
        digits = self.validate_aadhaar(aadhaar)
        encrypted = await self._client.encrypt_sensitive(digits)

        payload = {
            "txnId": "",
            "scope": ["abha-enrol"],
            "loginHint": "aadhaar",
            "loginId": encrypted,
            "otpSystem": "aadhaar",
        }
        data = await self._client.request(
            "POST",
            f"{settings.ABDM_ABHA_URL}/v3/enrollment/request/otp",
            json_body=payload,
        )
        txn_id = data.get("txnId")
        if not txn_id:
            raise ExternalServiceError("abdm-abha", "ABDM did not return a transaction id")

        handle = await self._store_txn(txn_id, {"flow": "aadhaar_enrol"})
        logger.info("abha_aadhaar_otp_requested")
        return {
            "verification_handle": handle,
            "otp_sent_to": data.get("message") or "Mobile number linked with Aadhaar",
            "expires_in_seconds": TXN_TTL_SECONDS,
        }

    async def enrol_by_aadhaar_otp(
        self,
        verification_handle: str,
        otp: str,
        mobile: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Step 2 — verify the OTP and create (or return) the ABHA account."""
        txn = await self._load_txn(verification_handle)
        encrypted_otp = await self._client.encrypt_sensitive(str(otp).strip())

        payload: Dict[str, Any] = {
            "authData": {
                "authMethods": ["otp"],
                "otp": {
                    "timeStamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                    "txnId": txn["txn_id"],
                    "otpValue": encrypted_otp,
                    "mobile": self.validate_mobile(mobile) if mobile else None,
                },
            },
            "consent": {"code": "abha-enrollment", "version": "1.4"},
        }
        if not payload["authData"]["otp"]["mobile"]:
            payload["authData"]["otp"].pop("mobile")

        data = await self._client.request(
            "POST",
            f"{settings.ABDM_ABHA_URL}/v3/enrollment/enrol/byAadhaar",
            json_body=payload,
        )
        await self._clear_txn(verification_handle)

        profile = self.normalise_profile(data)
        if not profile.get("abha_id"):
            raise ExternalServiceError(
                "abdm-abha", "ABDM enrolment succeeded but returned no ABHA number"
            )
        logger.info("abha_enrolled", is_new=bool(data.get("isNew", True)))
        return {
            "profile": profile,
            "is_new": bool(data.get("isNew", True)),
            "tokens": {
                "abha_token": data.get("tokens", {}).get("token") if isinstance(data.get("tokens"), dict) else None
            },
            "abha_address_suggestions": self._extract_suggestions(data),
        }

    @staticmethod
    def _extract_suggestions(data: Dict[str, Any]) -> List[str]:
        raw = data.get("abhaAddressList") or data.get("phrAddress") or []
        if isinstance(raw, str):
            return [raw]
        return [str(x) for x in raw if x]

    # ==================================================================
    # Mobile-based enrolment (no Aadhaar)
    # ==================================================================
    async def request_mobile_otp(self, mobile: str) -> Dict[str, Any]:
        digits = self.validate_mobile(mobile)
        encrypted = await self._client.encrypt_sensitive(digits)
        payload = {
            "txnId": "",
            "scope": ["abha-enrol", "mobile-verify"],
            "loginHint": "mobile",
            "loginId": encrypted,
            "otpSystem": "abdm",
        }
        data = await self._client.request(
            "POST",
            f"{settings.ABDM_ABHA_URL}/v3/enrollment/request/otp",
            json_body=payload,
        )
        txn_id = data.get("txnId")
        if not txn_id:
            raise ExternalServiceError("abdm-abha", "ABDM did not return a transaction id")
        handle = await self._store_txn(txn_id, {"flow": "mobile_enrol", "mobile": digits})
        return {
            "verification_handle": handle,
            "otp_sent_to": f"XXXXXX{digits[-4:]}",
            "expires_in_seconds": TXN_TTL_SECONDS,
        }

    async def verify_mobile_otp(self, verification_handle: str, otp: str) -> Dict[str, Any]:
        txn = await self._load_txn(verification_handle)
        encrypted_otp = await self._client.encrypt_sensitive(str(otp).strip())
        payload = {
            "scope": ["abha-enrol", "mobile-verify"],
            "authData": {
                "authMethods": ["otp"],
                "otp": {
                    "timeStamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                    "txnId": txn["txn_id"],
                    "otpValue": encrypted_otp,
                },
            },
        }
        data = await self._client.request(
            "POST",
            f"{settings.ABDM_ABHA_URL}/v3/enrollment/auth/byAbdm",
            json_body=payload,
        )
        await self._clear_txn(verification_handle)
        return {
            "profile": self.normalise_profile(data),
            "is_new": bool(data.get("isNew", False)),
            "abha_address_suggestions": self._extract_suggestions(data),
        }

    # ==================================================================
    # ABHA address (PHR) creation
    # ==================================================================
    async def suggest_abha_addresses(self, verification_handle: str) -> List[str]:
        txn = await self._load_txn(verification_handle)
        data = await self._client.request(
            "GET",
            f"{settings.ABDM_ABHA_URL}/v3/enrollment/enrol/suggestion",
            extra_headers={"TRANSACTION_ID": txn["txn_id"]},
        )
        return self._extract_suggestions(data)

    async def create_abha_address(
        self, verification_handle: str, preferred_address: str
    ) -> Dict[str, Any]:
        txn = await self._load_txn(verification_handle)
        payload = {
            "txnId": txn["txn_id"],
            "abhaAddress": preferred_address,
            "preferred": 1,
        }
        data = await self._client.request(
            "POST",
            f"{settings.ABDM_ABHA_URL}/v3/enrollment/enrol/abha-address",
            json_body=payload,
        )
        return {
            "abha_address": data.get("preferredAbhaAddress") or preferred_address,
            "abha_id": self.normalise_abha_number(str(data.get("ABHANumber", ""))) or None,
        }

    # ==================================================================
    # Search / login for an existing ABHA
    # ==================================================================
    async def request_login_otp(self, identifier: str) -> Dict[str, Any]:
        """Send an OTP to the mobile linked with an existing ABHA number/address."""
        value = identifier.strip()
        if self.is_abha_number(value):
            login_hint = "abha-number"
            login_id = self.normalise_abha_number(value)
        elif "@" in value:
            login_hint = "abha-address"
            login_id = value
        else:
            login_hint = "mobile"
            login_id = self.validate_mobile(value)

        encrypted = await self._client.encrypt_sensitive(login_id)
        payload = {
            "scope": ["abha-login", "mobile-verify"],
            "loginHint": login_hint,
            "loginId": encrypted,
            "otpSystem": "abdm",
        }
        data = await self._client.request(
            "POST",
            f"{settings.ABDM_ABHA_URL}/v3/profile/login/request/otp",
            json_body=payload,
        )
        txn_id = data.get("txnId")
        if not txn_id:
            raise ExternalServiceError("abdm-abha", "ABDM did not return a transaction id")
        handle = await self._store_txn(txn_id, {"flow": "login", "login_hint": login_hint})
        return {
            "verification_handle": handle,
            "login_hint": login_hint,
            "otp_sent_to": data.get("message") or "Registered mobile number",
            "expires_in_seconds": TXN_TTL_SECONDS,
        }

    async def verify_login_otp(self, verification_handle: str, otp: str) -> Dict[str, Any]:
        txn = await self._load_txn(verification_handle)
        encrypted_otp = await self._client.encrypt_sensitive(str(otp).strip())
        payload = {
            "scope": ["abha-login", "mobile-verify"],
            "authData": {
                "authMethods": ["otp"],
                "otp": {
                    "timeStamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                    "txnId": txn["txn_id"],
                    "otpValue": encrypted_otp,
                },
            },
        }
        data = await self._client.request(
            "POST",
            f"{settings.ABDM_ABHA_URL}/v3/profile/login/verify",
            json_body=payload,
        )
        token = data.get("token") or data.get("accessToken")
        await self._clear_txn(verification_handle)
        if not token:
            raise ExternalServiceError("abdm-abha", "ABHA login did not return a profile token")
        profile = await self.fetch_profile(token)
        return {"profile": profile, "abha_token": token}

    async def fetch_profile(self, abha_token: str) -> Dict[str, Any]:
        """Fetch the ABHA profile using the patient's X-Token."""
        data = await self._client.request(
            "GET",
            f"{settings.ABDM_ABHA_URL}/v3/profile/account",
            extra_headers={"X-token": f"Bearer {abha_token}"},
        )
        if not data:
            raise NotFoundError("ABHA profile could not be retrieved")
        return self.normalise_profile(data)

    async def fetch_abha_card(self, abha_token: str) -> bytes:
        """Download the ABHA card PNG for kiosk printing."""
        token = await self._client.get_access_token()
        from backend.core.http import ResilientHttpClient

        http = ResilientHttpClient.get("abdm-gateway")
        response = await http.request(
            "GET",
            f"{settings.ABDM_ABHA_URL}/v3/profile/account/abha-card",
            headers={
                **self._client.build_headers(token),
                "X-token": f"Bearer {abha_token}",
                "Accept": "image/png",
            },
        )
        return response.content

    # ==================================================================
    # Care-context / patient discovery for HIP linking
    # ==================================================================
    async def search_by_abha_address(self, abha_address: str) -> Optional[Dict[str, Any]]:
        """Verify an ABHA address exists (used before care-context linking)."""
        try:
            data = await self._client.request(
                "POST",
                f"{settings.ABDM_ABHA_URL}/v3/search/abha-address",
                json_body={"abhaAddress": abha_address},
            )
        except ExternalServiceError as exc:
            if exc.upstream_status == 404:
                return None
            raise
        if not data:
            return None
        return self.normalise_profile(data)

    def mock_generate_abha_id(self, aadhaar_number: str) -> str:
        """Generate a valid formatted 14-digit ABHA ID for sandbox testing."""
        digits = re.sub(r"\D", "", str(aadhaar_number))
        tail = digits[-10:] if len(digits) >= 10 else digits.zfill(10)
        return f"91-{tail[:4]}-{tail[4:8]}-{tail[8:]}"

    async def search_patient_sandbox(
        self, abha_id: Optional[str] = None, aadhaar_clean: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Search patient profile in ABDM with sandbox fallback."""
        if abha_id and "@" in abha_id:
            try:
                res = await self.search_by_abha_address(abha_id)
                if res:
                    return res
            except Exception:
                pass

        if not settings.abdm_configured or settings.ABDM_ENVIRONMENT == "sandbox":
            target_id = abha_id or (self.mock_generate_abha_id(aadhaar_clean) if aadhaar_clean else "91-5820-1924-8831")
            return {
                "abha_id": target_id,
                "abha_address": "aarav.verma@abdm",
                "first_name": "Aarav",
                "last_name": "Verma",
                "gender": "Male",
                "age": 35,
                "phone_number": "9876543210",
                "district": "New Delhi",
                "state": "Delhi",
                "pincode": "110029",
                "preferred_language": "hi",
            }
        return None

    async def health(self) -> Dict[str, Any]:
        return await self._client.health()


abha_service = AbhaService()

__all__ = ["AbhaService", "abha_service"]

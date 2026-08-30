"""Pydantic v2 schemas for MediKiosk authentication, ABHA, and consent endpoints."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


# ==============================================================================
# KIOSK INTERNAL JWT SCHEMAS
# ==============================================================================

class KioskTokenRequest(BaseModel):
    kiosk_id: str = Field(..., description="Unique physical kiosk station identifier", examples=["KIOSK-OPD-01"])
    shared_secret: str = Field(..., description="Kiosk mutual provisioning secret")


class KioskTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    kiosk_id: str


# ==============================================================================
# DEMOGRAPHICS & ABHA SEARCH SCHEMAS
# ==============================================================================

class PatientDemographics(BaseModel):
    first_name: str
    last_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    age: Optional[int] = None
    gender: str
    phone_number: Optional[str] = None
    address_line: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    preferred_language: str = "hi"


class AbhaSearchRequest(BaseModel):
    abha_id: Optional[str] = Field(None, description="14-digit ABHA ID (e.g. 91-1234-5678-9012) or ABHA address")
    aadhaar_number: Optional[str] = Field(None, description="12-digit Aadhaar number")

    @model_validator(mode="after")
    def check_at_least_one_identifier(self) -> "AbhaSearchRequest":
        if not self.abha_id and not self.aadhaar_number:
            raise ValueError("Either 'abha_id' or 'aadhaar_number' must be provided for patient search")
        return self


class AbhaSearchResponse(BaseModel):
    found: bool
    patient_id: Optional[uuid.UUID] = None
    abha_id: Optional[str] = None
    abha_address: Optional[str] = None
    demographics: Optional[PatientDemographics] = None
    source: str = Field(..., description="Source of verification (ABDM_SANDBOX, LOCAL_DB, MOCK_FALLBACK)")
    message: str


# ==============================================================================
# ABHA CREATION SCHEMAS (Aadhaar eKYC Mocked OTP Flow)
# ==============================================================================

class AbhaCreateRequest(BaseModel):
    aadhaar_number: str = Field(..., min_length=12, max_length=14, description="12-digit Aadhaar number")
    phone_number: str = Field(..., min_length=10, max_length=15, description="Mobile number linked with Aadhaar")
    first_name: str
    last_name: Optional[str] = None
    gender: str = Field(..., description="Male, Female, or Other")
    date_of_birth: Optional[date] = None
    otp: str = Field(default="123456", description="OTP received on patient mobile (Mocked for testing)")
    preferred_language: str = "hi"

    @field_validator("aadhaar_number")
    @classmethod
    def validate_aadhaar_digits(cls, v: str) -> str:
        digits = "".join(filter(str.isdigit, v))
        if len(digits) != 12:
            raise ValueError("Aadhaar must contain exactly 12 numeric digits")
        return digits


class AbhaCreateResponse(BaseModel):
    status: str
    message: str
    patient_id: uuid.UUID
    abha_id: str
    abha_address: str
    is_new_patient: bool
    created_at: datetime


# ==============================================================================
# PATIENT REGISTRATION SCHEMAS (Non-ABHA Walk-in)
# ==============================================================================

class PatientRegisterRequest(BaseModel):
    first_name: str
    last_name: Optional[str] = None
    age: Optional[int] = None
    date_of_birth: Optional[date] = None
    gender: str
    phone_number: Optional[str] = None
    address_line: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    preferred_language: str = "hi"


class PatientRegisterResponse(BaseModel):
    status: str
    message: str
    temp_patient_id: uuid.UUID
    patient: PatientDemographics
    registered_at: datetime


# ==============================================================================
# CONSENT SCHEMAS (DPDP Act 2023 & ABDM Compliant)
# ==============================================================================

class ConsentCreateRequest(BaseModel):
    patient_id: uuid.UUID
    session_id: Optional[uuid.UUID] = None
    consent_version: str = Field(default="v1.0")
    audio_explanation_played: bool = Field(default=True)
    consent_voice_and_touch: bool = Field(..., description="Consent to voice ASR and touchscreen capture")
    consent_document_scan_ocr: bool = Field(..., description="Consent to scan prescriptions and run OCR extraction")
    consent_share_with_hospital: bool = Field(..., description="Consent to transmit summary to hospital EMR / physician")
    consent_upload_abha_phr: bool = Field(default=False, description="Consent to sync summary with patient ABHA PHR")
    consent_method: str = Field(default="TOUCH", description="TOUCH or VOICE")
    kiosk_id: str = Field(..., description="Originating kiosk identifier")


class ConsentResponse(BaseModel):
    consent_id: uuid.UUID
    patient_id: uuid.UUID
    session_id: Optional[uuid.UUID]
    consent_version: str
    audio_explanation_played: bool
    consent_voice_and_touch: bool
    consent_document_scan_ocr: bool
    consent_share_with_hospital: bool
    consent_upload_abha_phr: bool
    consent_method: str
    is_revoked: bool
    tamper_proof_hash: str
    granted_at: datetime


class ConsentStatusResponse(BaseModel):
    patient_id: uuid.UUID
    has_active_consent: bool
    active_consents: List[ConsentResponse]

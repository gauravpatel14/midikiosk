"""FastAPI Router for MediKiosk Authentication, ABHA Integration, and DPDP Consent."""

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

try:
    from backend.config import settings
    from backend.database import get_db
    from backend.models import AuditLog, Consent, Patient
    from backend.schemas import (
        AbhaCreateRequest,
        AbhaCreateResponse,
        AbhaSearchRequest,
        AbhaSearchResponse,
        ConsentCreateRequest,
        ConsentResponse,
        ConsentStatusResponse,
        KioskTokenRequest,
        KioskTokenResponse,
        PatientDemographics,
        PatientRegisterRequest,
        PatientRegisterResponse,
    )
    from backend.security import (
        compute_consent_hash,
        create_kiosk_access_token,
        hash_aadhaar,
        verify_kiosk_token,
    )
    from backend.services.abdm_service import abdm_service
except ImportError:
    from config import settings
    from database import get_db
    from models import AuditLog, Consent, Patient
    from schemas import (
        AbhaCreateRequest,
        AbhaCreateResponse,
        AbhaSearchRequest,
        AbhaSearchResponse,
        ConsentCreateRequest,
        ConsentResponse,
        ConsentStatusResponse,
        KioskTokenRequest,
        KioskTokenResponse,
        PatientDemographics,
        PatientRegisterRequest,
        PatientRegisterResponse,
    )
    from security import (
        compute_consent_hash,
        create_kiosk_access_token,
        hash_aadhaar,
        verify_kiosk_token,
    )
    from services.abdm_service import abdm_service

router = APIRouter(prefix="/auth", tags=["Authentication, ABHA & Consent"])


# ==============================================================================
# 0. INTERNAL KIOSK JWT TOKEN ENDPOINT
# ==============================================================================

@router.post("/kiosk/token", response_model=KioskTokenResponse, summary="Issue Kiosk Internal JWT")
def issue_kiosk_jwt_token(payload: KioskTokenRequest) -> KioskTokenResponse:
    """Issue JWT for internal communication between hardware kiosk and backend services."""
    if payload.shared_secret != settings.KIOSK_SHARED_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid kiosk shared provisioning secret",
        )

    token = create_kiosk_access_token(kiosk_id=payload.kiosk_id)
    return KioskTokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in_seconds=settings.JWT_EXPIRY_MINUTES * 60,
        kiosk_id=payload.kiosk_id,
    )


# ==============================================================================
# 1. POST /auth/abha/search
# ==============================================================================

@router.post("/abha/search", response_model=AbhaSearchResponse, summary="Search Patient by ABHA or Aadhaar")
async def search_abha_patient(
    payload: AbhaSearchRequest,
    db: Session = Depends(get_db),
    kiosk_auth: Dict[str, Any] = Depends(verify_kiosk_token),
) -> AbhaSearchResponse:
    """Search patient profile using ABHA ID or Aadhaar via ABDM Sandbox & local cache."""
    clean_aadhaar = "".join(filter(str.isdigit, payload.aadhaar_number)) if payload.aadhaar_number else None
    aadhaar_token = hash_aadhaar(clean_aadhaar) if clean_aadhaar else None

    # Step 1: Check Local DB Cache First
    patient: Optional[Patient] = None
    if payload.abha_id:
        patient = db.query(Patient).filter(
            (Patient.abha_id == payload.abha_id) | (Patient.abha_address == payload.abha_id)
        ).first()

    if not patient and aadhaar_token:
        patient = db.query(Patient).filter(Patient.aadhaar_hash == aadhaar_token).first()

    if patient:
        return AbhaSearchResponse(
            found=True,
            patient_id=patient.id,
            abha_id=patient.abha_id,
            abha_address=patient.abha_address,
            demographics=PatientDemographics(
                first_name=patient.first_name,
                last_name=patient.last_name,
                date_of_birth=patient.date_of_birth,
                age=patient.age,
                gender=patient.gender,
                phone_number=patient.phone_number,
                address_line=patient.address_line,
                district=patient.district,
                state=patient.state,
                pincode=patient.pincode,
                preferred_language=patient.preferred_language,
            ),
            source="LOCAL_DB",
            message="Patient record located in hospital database.",
        )

    # Step 2: Query ABDM Sandbox API
    abdm_data = await abdm_service.search_patient_sandbox(
        abha_id=payload.abha_id, aadhaar_clean=clean_aadhaar
    )

    if abdm_data:
        # Create local patient record linked to ABHA profile
        new_patient = Patient(
            id=uuid.uuid4(),
            abha_id=abdm_data.get("abha_id"),
            abha_address=abdm_data.get("abha_address"),
            aadhaar_hash=aadhaar_token,
            first_name=abdm_data.get("first_name", "Unknown"),
            last_name=abdm_data.get("last_name"),
            gender=abdm_data.get("gender", "Male"),
            age=abdm_data.get("age"),
            phone_number=abdm_data.get("phone_number"),
            address_line=abdm_data.get("address_line"),
            district=abdm_data.get("district"),
            state=abdm_data.get("state"),
            pincode=abdm_data.get("pincode"),
            preferred_language=abdm_data.get("preferred_language", "hi"),
        )
        db.add(new_patient)
        db.commit()
        db.refresh(new_patient)

        return AbhaSearchResponse(
            found=True,
            patient_id=new_patient.id,
            abha_id=new_patient.abha_id,
            abha_address=new_patient.abha_address,
            demographics=PatientDemographics(
                first_name=new_patient.first_name,
                last_name=new_patient.last_name,
                age=new_patient.age,
                gender=new_patient.gender,
                phone_number=new_patient.phone_number,
                address_line=new_patient.address_line,
                district=new_patient.district,
                state=new_patient.state,
                pincode=new_patient.pincode,
                preferred_language=new_patient.preferred_language,
            ),
            source="ABDM_SANDBOX",
            message="Patient verified from ABDM Sandbox and synchronized locally.",
        )

    return AbhaSearchResponse(
        found=False,
        patient_id=None,
        abha_id=payload.abha_id,
        abha_address=None,
        demographics=None,
        source="ABDM_SANDBOX",
        message="No matching ABHA or Aadhaar record found in ABDM sandbox registry.",
    )


# ==============================================================================
# 2. POST /auth/abha/create
# ==============================================================================

@router.post("/abha/create", response_model=AbhaCreateResponse, summary="Create ABHA via Aadhaar eKYC")
def create_abha_with_ekyc(
    payload: AbhaCreateRequest,
    db: Session = Depends(get_db),
    kiosk_auth: Dict[str, Any] = Depends(verify_kiosk_token),
) -> AbhaCreateResponse:
    """Create a new 14-digit ABHA ID using mocked Aadhaar eKYC OTP verification."""
    # Mock OTP verification flow
    if payload.otp != "123456" and len(payload.otp) != 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Aadhaar eKYC OTP. Please use default test OTP 123456.",
        )

    aadhaar_token = hash_aadhaar(payload.aadhaar_number)
    
    # Check if patient already exists
    patient = db.query(Patient).filter(Patient.aadhaar_hash == aadhaar_token).first()
    is_new = False

    if not patient:
        generated_abha_id = abdm_service.mock_generate_abha_id(payload.aadhaar_number)
        generated_address = f"{payload.first_name.lower()}{payload.aadhaar_number[-4:]}@abdm"
        
        patient = Patient(
            id=uuid.uuid4(),
            abha_id=generated_abha_id,
            abha_address=generated_address,
            aadhaar_hash=aadhaar_token,
            first_name=payload.first_name,
            last_name=payload.last_name,
            gender=payload.gender,
            date_of_birth=payload.date_of_birth,
            phone_number=payload.phone_number,
            preferred_language=payload.preferred_language,
        )
        db.add(patient)
        is_new = True
    else:
        if not patient.abha_id:
            patient.abha_id = abdm_service.mock_generate_abha_id(payload.aadhaar_number)
            patient.abha_address = f"{patient.first_name.lower()}{payload.aadhaar_number[-4:]}@abdm"

    db.commit()
    db.refresh(patient)

    # Record Audit Log
    db.add(
        AuditLog(
            id=uuid.uuid4(),
            patient_id=patient.id,
            kiosk_id=kiosk_auth.get("kiosk_id", "KIOSK-UNKNOWN"),
            action="ABHA_CREATED",
            entity_name="patients",
            entity_id=str(patient.id),
            new_state={"abha_id": patient.abha_id, "is_new": is_new},
            timestamp=datetime.now(timezone.utc),
        )
    )
    db.commit()

    return AbhaCreateResponse(
        status="success",
        message="ABHA successfully issued through Aadhaar eKYC.",
        patient_id=patient.id,
        abha_id=str(patient.abha_id or ""),
        abha_address=patient.abha_address or "",
        is_new_patient=is_new,
        created_at=patient.created_at or datetime.now(timezone.utc),
    )


# ==============================================================================
# 3. POST /auth/patient/register
# ==============================================================================

@router.post("/patient/register", response_model=PatientRegisterResponse, summary="Register Walk-in Patient")
def register_walkin_patient(
    payload: PatientRegisterRequest,
    db: Session = Depends(get_db),
    kiosk_auth: Dict[str, Any] = Depends(verify_kiosk_token),
) -> PatientRegisterResponse:
    """Register a new patient when no ABHA ID or Aadhaar is present."""
    now = datetime.now(timezone.utc)
    patient = Patient(
        id=uuid.uuid4(),
        abha_id=None,
        abha_address=None,
        aadhaar_hash=None,
        first_name=payload.first_name,
        last_name=payload.last_name,
        age=payload.age,
        date_of_birth=payload.date_of_birth,
        gender=payload.gender,
        phone_number=payload.phone_number,
        address_line=payload.address_line,
        district=payload.district,
        state=payload.state,
        pincode=payload.pincode,
        preferred_language=payload.preferred_language,
        created_at=now,
        updated_at=now,
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)

    # DPDP Audit Log
    db.add(
        AuditLog(
            id=uuid.uuid4(),
            patient_id=patient.id,
            kiosk_id=kiosk_auth.get("kiosk_id", "KIOSK-UNKNOWN"),
            action="PATIENT_REGISTER",
            entity_name="patients",
            entity_id=str(patient.id),
            new_state={"name": f"{patient.first_name} {patient.last_name or ''}".strip()},
            timestamp=now,
        )
    )
    db.commit()

    return PatientRegisterResponse(
        status="success",
        message="Patient registered with temporary hospital identifier.",
        temp_patient_id=patient.id,
        patient=PatientDemographics(
            first_name=patient.first_name,
            last_name=patient.last_name,
            age=patient.age,
            gender=patient.gender,
            phone_number=patient.phone_number,
            address_line=patient.address_line,
            district=patient.district,
            state=patient.state,
            pincode=patient.pincode,
            preferred_language=patient.preferred_language,
        ),
        registered_at=patient.created_at or now,
    )


# ==============================================================================
# 4. POST /auth/consent
# ==============================================================================

@router.post("/consent", response_model=ConsentResponse, summary="Record Granular Patient Consent")
def record_patient_consent(
    payload: ConsentCreateRequest,
    db: Session = Depends(get_db),
    kiosk_auth: Dict[str, Any] = Depends(verify_kiosk_token),
) -> ConsentResponse:
    """Record DPDP Act 2023 & ABDM compliant consent with cryptographic tamper hash."""
    patient = db.query(Patient).filter(Patient.id == payload.patient_id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with ID {payload.patient_id} does not exist.",
        )

    now = datetime.now(timezone.utc)
    tamper_hash = compute_consent_hash(
        patient_id=str(payload.patient_id),
        granted_at=now,
        version=payload.consent_version,
        v_and_t=payload.consent_voice_and_touch,
        ocr=payload.consent_document_scan_ocr,
        emr=payload.consent_share_with_hospital,
        phr=payload.consent_upload_abha_phr,
    )

    consent_record = Consent(
        id=uuid.uuid4(),
        patient_id=payload.patient_id,
        session_id=payload.session_id,
        consent_version=payload.consent_version,
        audio_explanation_played=payload.audio_explanation_played,
        consent_voice_and_touch=payload.consent_voice_and_touch,
        consent_document_scan_ocr=payload.consent_document_scan_ocr,
        consent_share_with_hospital=payload.consent_share_with_hospital,
        consent_upload_abha_phr=payload.consent_upload_abha_phr,
        consent_method=payload.consent_method.upper(),
        ip_or_kiosk_id=payload.kiosk_id,
        is_revoked=False,
        tamper_proof_hash=tamper_hash,
        granted_at=now,
    )
    db.add(consent_record)
    db.commit()
    db.refresh(consent_record)

    # Immutable Audit Log
    db.add(
        AuditLog(
            id=uuid.uuid4(),
            patient_id=patient.id,
            session_id=payload.session_id,
            kiosk_id=payload.kiosk_id,
            action="CONSENT_GRANT",
            entity_name="consents",
            entity_id=str(consent_record.id),
            new_state={
                "version": payload.consent_version,
                "voice_touch": payload.consent_voice_and_touch,
                "ocr": payload.consent_document_scan_ocr,
                "share_hospital": payload.consent_share_with_hospital,
                "upload_phr": payload.consent_upload_abha_phr,
                "tamper_hash": tamper_hash,
            },
            timestamp=now,
        )
    )
    db.commit()

    return ConsentResponse(
        consent_id=consent_record.id,
        patient_id=consent_record.patient_id,
        session_id=consent_record.session_id,
        consent_version=consent_record.consent_version,
        audio_explanation_played=consent_record.audio_explanation_played,
        consent_voice_and_touch=consent_record.consent_voice_and_touch,
        consent_document_scan_ocr=consent_record.consent_document_scan_ocr,
        consent_share_with_hospital=consent_record.consent_share_with_hospital,
        consent_upload_abha_phr=consent_record.consent_upload_abha_phr,
        consent_method=consent_record.consent_method,
        is_revoked=consent_record.is_revoked,
        tamper_proof_hash=consent_record.tamper_proof_hash,
        granted_at=consent_record.granted_at,
    )


# ==============================================================================
# 5. GET /auth/consent/{patient_id}
# ==============================================================================

@router.get("/consent/{patient_id}", response_model=ConsentStatusResponse, summary="Retrieve Consent Status")
def get_patient_consent_status(
    patient_id: uuid.UUID,
    db: Session = Depends(get_db),
    kiosk_auth: Dict[str, Any] = Depends(verify_kiosk_token),
) -> ConsentStatusResponse:
    """Retrieve all active, unrevoked consent records for a specified patient."""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient {patient_id} not found.",
        )

    consents = (
        db.query(Consent)
        .filter(Consent.patient_id == patient_id, Consent.is_revoked == False)
        .order_by(Consent.granted_at.desc())
        .all()
    )

    consent_list = [
        ConsentResponse(
            consent_id=c.id,
            patient_id=c.patient_id,
            session_id=c.session_id,
            consent_version=c.consent_version,
            audio_explanation_played=c.audio_explanation_played,
            consent_voice_and_touch=c.consent_voice_and_touch,
            consent_document_scan_ocr=c.consent_document_scan_ocr,
            consent_share_with_hospital=c.consent_share_with_hospital,
            consent_upload_abha_phr=c.consent_upload_abha_phr,
            consent_method=c.consent_method,
            is_revoked=c.is_revoked,
            tamper_proof_hash=c.tamper_proof_hash,
            granted_at=c.granted_at,
        )
        for c in consents
    ]

    return ConsentStatusResponse(
        patient_id=patient_id,
        has_active_consent=len(consent_list) > 0,
        active_consents=consent_list,
    )


# ==============================================================================
# 6. POST /auth/consent/revoke/{patient_id} (DPDP Act 2023 Compliant)
# ==============================================================================

class ConsentRevocationRequest(BaseModel):
    reason: str = Field(
        default="Patient requested complete revocation and data deletion under DPDP Act 2023",
        description="Reason for consent revocation",
    )
    kiosk_id: Optional[str] = Field(default="KIOSK-01", description="Kiosk or terminal identifier")


class ConsentRevocationResponse(BaseModel):
    status: str
    patient_id: uuid.UUID
    revoked_at: datetime
    purged_sessions_count: int
    purged_documents_count: int
    abdm_revocation_status: Optional[str] = "SUCCESS"
    message: str


async def retry_abdm_revocation(consent_id: str, reason: str) -> None:
    """Background retry for ABDM consent revocation."""
    from backend.services.abdm.consent import AbdmConsentService
    from backend.core.logging import get_logger
    log = get_logger(__name__)
    service = AbdmConsentService()
    try:
        res = await service.revoke_consent(consent_id, reason=reason)
        log.info("abdm_revocation_retry_success", consent_id=consent_id, result=res)
    except Exception as exc:
        log.error("abdm_revocation_retry_failed", consent_id=consent_id, error=str(exc))


@router.post(
    "/consent/revoke/{patient_id}",
    response_model=ConsentRevocationResponse,
    summary="Revoke Consent & Purge Patient Intake Data",
)
async def revoke_patient_consent_endpoint(
    patient_id: uuid.UUID,
    payload: Optional[ConsentRevocationRequest] = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    kiosk_auth: Dict[str, Any] = Depends(verify_kiosk_token),
) -> ConsentRevocationResponse:
    """DPDP Act 2023 compliant consent revocation:
    1. Deletes all patient session data (history, documents, entities, summaries) transactionally.
    2. Deletes or archives associated document files from disk.
    3. Updates Consent records to is_revoked = True with timestamp and reason.
    4. Writes an immutable entry to the AuditLog.
    5. Propagates consent revocation to the ABDM ecosystem (v0.5 POST /v0.5/consents/revoke).
    """
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with ID {patient_id} not found.",
        )

    reason = payload.reason if payload else "Patient requested data deletion under DPDP Act 2023"
    kiosk_id = payload.kiosk_id if payload else "KIOSK-AUTH"
    now = datetime.now(timezone.utc)

    # 1. Query all sessions and clinical documents for this patient
    try:
        from backend.models import (
            Document,
            ExtractedEntity,
            HistorySession,
            RedFlag,
            Summary,
        )
    except ImportError:
        from models import (
            Document,
            ExtractedEntity,
            HistorySession,
            RedFlag,
            Summary,
        )

    sessions = db.query(HistorySession).filter(HistorySession.patient_id == patient_id).all()
    session_ids = [s.id for s in sessions]

    # 2. Query all clinical documents and securely archive/delete from disk
    docs = db.query(Document).filter(Document.patient_id == patient_id).all()
    purged_docs_count = 0
    from backend.services.cleanup import archive_or_delete_file
    for doc in docs:
        doc_path = getattr(doc, "storage_path", None) or getattr(doc, "file_path", None)
        if doc_path and os.path.exists(doc_path):
            archive_or_delete_file(doc_path, patient_id=str(patient_id))
            purged_docs_count += 1

    # 3. Transactionally delete child records
    if session_ids:
        db.query(ExtractedEntity).filter(ExtractedEntity.session_id.in_(session_ids)).delete(synchronize_session=False)
        db.query(Summary).filter(Summary.session_id.in_(session_ids)).delete(synchronize_session=False)
        db.query(RedFlag).filter(RedFlag.session_id.in_(session_ids)).delete(synchronize_session=False)
    db.query(Document).filter(Document.patient_id == patient_id).delete(synchronize_session=False)
    db.query(HistorySession).filter(HistorySession.patient_id == patient_id).delete(synchronize_session=False)

    # 4. Mark all consents as revoked
    consents = db.query(Consent).filter(Consent.patient_id == patient_id, Consent.is_revoked == False).all()
    for c in consents:
        c.is_revoked = True
        c.revoked_at = now
        c.revocation_reason = reason

    # 5. Write to Immutable Audit Log
    db.add(
        AuditLog(
            id=uuid.uuid4(),
            patient_id=patient_id,
            kiosk_id=kiosk_id,
            action="CONSENT_REVOCATION",
            entity_name="consents",
            entity_id=str(patient_id),
            new_state={
                "status": "REVOKED",
                "reason": reason,
                "purged_sessions": len(sessions),
                "purged_documents": purged_docs_count,
            },
            timestamp=now,
        )
    )
    db.commit()

    # 6. Propagate Revocation to ABDM Consent Manager
    from backend.services.abdm.consent import AbdmConsentService
    from backend.core.logging import get_logger
    logger = get_logger(__name__)
    abdm_consent_svc = AbdmConsentService()

    consent_ids_to_revoke = [str(c.id) for c in consents]
    if not consent_ids_to_revoke:
        consent_ids_to_revoke.append(str(patient_id))

    abdm_status = "SUCCESS"
    for consent_target_id in consent_ids_to_revoke:
        try:
            res = await abdm_consent_svc.revoke_consent(consent_target_id, reason=reason)
            logger.info("abdm_revocation_success", consent_id=consent_target_id, result=res)
        except Exception as exc:
            logger.warning("abdm_revocation_failed_pending_retry", consent_id=consent_target_id, error=str(exc))
            abdm_status = "REVOKED_PENDING_ABDM"
            if getattr(settings, "ABDM_REVOCATION_RETRY_ENABLED", True):
                background_tasks.add_task(retry_abdm_revocation, consent_target_id, reason)

    for c in consents:
        c.abdm_revocation_status = abdm_status
        c.abdm_revocation_timestamp = now
    db.commit()

    return ConsentRevocationResponse(
        status="success",
        patient_id=patient_id,
        revoked_at=now,
        purged_sessions_count=len(sessions),
        purged_documents_count=purged_docs_count,
        abdm_revocation_status=abdm_status,
        message="Patient consent successfully revoked and all associated intake session records purged.",
    )

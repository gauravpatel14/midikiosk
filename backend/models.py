"""SQLAlchemy models for MediKiosk clinical history platform.

Comprehensive data models covering patient demographics, ABDM consents,
multimodal history interview (Allopathic & AYUSH Dashavidha Pariksha),
OCR document digitization, entity extraction, clinical summaries,
red flags, user management, and DPDP-compliant audit logging.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime, timezone
from typing import Any, List, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base
from backend.db.types import GUID as UUID_TYPE
from backend.db.types import EncryptedString
from backend.db.types import JSONBType as JSONB


def UUID(as_uuid: bool = True):  # noqa: N802 - keeps historical call signature
    """Portable UUID column type (native ``uuid`` on PostgreSQL, CHAR(36) on SQLite)."""
    return UUID_TYPE()


# ==============================================================================
# ENUM DEFINITIONS
# ==============================================================================

class UserRole(str, enum.Enum):
    """Staff and clinician roles operating MediKiosk and hospital HIS."""
    PHYSICIAN = "PHYSICIAN"
    AYUSH_PRACTITIONER = "AYUSH_PRACTITIONER"
    TRIAGE_NURSE = "TRIAGE_NURSE"
    KIOSK_ASSISTANT = "KIOSK_ASSISTANT"
    ADMINISTRATOR = "ADMINISTRATOR"
    AUDITOR = "AUDITOR"


class SessionMode(str, enum.Enum):
    """Clinical history collection framework mode."""
    ALLOPATHIC = "ALLOPATHIC"
    AYUSH = "AYUSH"
    HYBRID = "HYBRID"


class SessionStatus(str, enum.Enum):
    """Lifecycle status of a patient history collection session."""
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    ABANDONED = "ABANDONED"
    RED_FLAG_HALTED = "RED_FLAG_HALTED"
    EXPIRED = "EXPIRED"


class SummaryStatus(str, enum.Enum):
    """Review and confirmation status of the generated clinical summary."""
    DRAFT = "DRAFT"
    PHYSICIAN_EDITED = "PHYSICIAN_EDITED"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"


class DocumentType(str, enum.Enum):
    """Categories of prior physical documents scanned at the kiosk."""
    PRESCRIPTION = "PRESCRIPTION"
    LAB_REPORT = "LAB_REPORT"
    DISCHARGE_SUMMARY = "DISCHARGE_SUMMARY"
    AYUSH_PRESCRIPTION = "AYUSH_PRESCRIPTION"
    IMAGING_REPORT = "IMAGING_REPORT"
    OTHER = "OTHER"


class DocumentProcessingStatus(str, enum.Enum):
    """OCR and extraction pipeline stages for physical documents."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"
    FLAGGED_REVIEW = "FLAGGED_REVIEW"


class EntityType(str, enum.Enum):
    """Clinical entity classes extracted via NLP from documents and speech."""
    DIAGNOSIS = "DIAGNOSIS"
    MEDICATION = "MEDICATION"
    INVESTIGATION = "INVESTIGATION"
    PROCEDURE = "PROCEDURE"
    VITAL_SIGN = "VITAL_SIGN"
    ALLERGY = "ALLERGY"


class RedFlagSeverity(str, enum.Enum):
    """Triage priority levels for critical clinical alerts."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


class AbdmSyncStatus(str, enum.Enum):
    """Synchronization states with ABDM Gateway / Health Information Exchange."""
    NOT_SYNCED = "NOT_SYNCED"
    QUEUED = "QUEUED"
    SYNCED = "SYNCED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"


# ==============================================================================
# 1. USERS TABLE
# ==============================================================================

class User(Base):
    """Clinicians, nurses, attendants, and administrators."""
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role_enum"), nullable=False, default=UserRole.PHYSICIAN
    )
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    specialization: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    abdm_hpr_id: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="ABDM Healthcare Professional Registry ID"
    )
    phone_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    password_changed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_users_role_active", "role", "is_active"),
    )

    # Relationships
    confirmed_summaries: Mapped[List[Summary]] = relationship(
        "Summary", back_populates="confirmed_by_user"
    )
    acknowledged_red_flags: Mapped[List[RedFlag]] = relationship(
        "RedFlag", back_populates="triage_acknowledged_by_user"
    )
    audit_logs: Mapped[List[AuditLog]] = relationship("AuditLog", back_populates="user")


# ==============================================================================
# 2. PATIENTS TABLE
# ==============================================================================

class Patient(Base):
    """Patient demographic records registered at kiosk or linked via ABHA."""
    __tablename__ = "patients"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    abha_id: Mapped[Optional[str]] = mapped_column(
        String(32), unique=True, nullable=True, index=True, comment="14-digit ABHA ID number"
    )
    abha_address: Mapped[Optional[str]] = mapped_column(
        String(100), unique=True, nullable=True, index=True, comment="Unique ABHA PHR address"
    )
    aadhaar_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        unique=True,
        index=True,
        comment="Peppered HMAC-SHA256 token; raw Aadhaar is never stored (DPDP Act 2023)",
    )
    first_name: Mapped[str] = mapped_column(EncryptedString(255), nullable=False)
    last_name: Mapped[Optional[str]] = mapped_column(EncryptedString(255), nullable=True)
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    gender: Mapped[str] = mapped_column(String(20), nullable=False)  # Male, Female, Other
    phone_number: Mapped[Optional[str]] = mapped_column(EncryptedString(255), nullable=True)
    phone_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment="Peppered hash enabling phone lookup without storing plaintext",
    )
    address_line: Mapped[Optional[str]] = mapped_column(EncryptedString(1024), nullable=True)
    district: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    pincode: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    preferred_language: Mapped[str] = mapped_column(String(20), default="hi", nullable=False)
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Soft delete flag supporting DPDP right-to-erasure while retaining audit integrity",
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_patients_name_dob", "date_of_birth", "gender"),
        Index("idx_patients_created", "created_at"),
    )

    # Relationships
    consents: Mapped[List[Consent]] = relationship(
        "Consent", back_populates="patient", cascade="all, delete-orphan"
    )
    sessions: Mapped[List[HistorySession]] = relationship(
        "HistorySession", back_populates="patient", cascade="all, delete-orphan"
    )
    chief_complaints: Mapped[List[ChiefComplaint]] = relationship(
        "ChiefComplaint", back_populates="patient", cascade="all, delete-orphan"
    )
    past_medical_history: Mapped[List[PastMedicalHistory]] = relationship(
        "PastMedicalHistory", back_populates="patient", cascade="all, delete-orphan"
    )
    medications: Mapped[List[Medication]] = relationship(
        "Medication", back_populates="patient", cascade="all, delete-orphan"
    )
    allergies: Mapped[List[Allergy]] = relationship(
        "Allergy", back_populates="patient", cascade="all, delete-orphan"
    )
    family_histories: Mapped[List[FamilyHistory]] = relationship(
        "FamilyHistory", back_populates="patient", cascade="all, delete-orphan"
    )
    personal_histories: Mapped[List[PersonalHistory]] = relationship(
        "PersonalHistory", back_populates="patient", cascade="all, delete-orphan"
    )
    review_of_systems: Mapped[List[ReviewOfSystems]] = relationship(
        "ReviewOfSystems", back_populates="patient", cascade="all, delete-orphan"
    )
    ayush_assessments: Mapped[List[AyushAssessment]] = relationship(
        "AyushAssessment", back_populates="patient", cascade="all, delete-orphan"
    )
    documents: Mapped[List[Document]] = relationship(
        "Document", back_populates="patient", cascade="all, delete-orphan"
    )
    extracted_entities: Mapped[List[ExtractedEntity]] = relationship(
        "ExtractedEntity", back_populates="patient", cascade="all, delete-orphan"
    )
    summaries: Mapped[List[Summary]] = relationship(
        "Summary", back_populates="patient", cascade="all, delete-orphan"
    )
    red_flags: Mapped[List[RedFlag]] = relationship(
        "RedFlag", back_populates="patient", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[List[AuditLog]] = relationship("AuditLog", back_populates="patient")


# ==============================================================================
# 3. CONSENTS TABLE
# ==============================================================================

class Consent(Base):
    """Granular consent records compliant with DPDP Act 2023 & ABDM."""
    __tablename__ = "consents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("history_sessions.id", ondelete="SET NULL"), nullable=True
    )
    consent_version: Mapped[str] = mapped_column(String(20), default="v1.0", nullable=False)
    audio_explanation_played: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    consent_voice_and_touch: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    consent_document_scan_ocr: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    consent_share_with_hospital: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    consent_upload_abha_phr: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    consent_method: Mapped[str] = mapped_column(String(30), default="TOUCH", nullable=False)  # TOUCH, VOICE
    ip_or_kiosk_id: Mapped[str] = mapped_column(String(100), nullable=False)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revocation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    abdm_revocation_status: Mapped[Optional[str]] = mapped_column(
        String(32), default=None, nullable=True, comment="PENDING, SUCCESS, FAILED, REVOKED_PENDING_ABDM"
    )
    abdm_revocation_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    tamper_proof_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="SHA-256 hash of consent record for audit verification"
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    patient: Mapped[Patient] = relationship("Patient", back_populates="consents")
    session: Mapped[Optional[HistorySession]] = relationship("HistorySession", back_populates="consents")


# ==============================================================================
# 4. HISTORY SESSIONS TABLE
# ==============================================================================

class HistorySession(Base):
    """Discrete patient interaction session at a physical kiosk."""
    __tablename__ = "history_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kiosk_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    session_token: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    mode: Mapped[SessionMode] = mapped_column(
        Enum(SessionMode, name="session_mode_enum"), nullable=False, default=SessionMode.ALLOPATHIC
    )
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, name="session_status_enum"), nullable=False, default=SessionStatus.IN_PROGRESS, index=True
    )
    interaction_language: Mapped[str] = mapped_column(String(20), default="hi", nullable=False)
    is_priority: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    question_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    session_timeout_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    offline_captured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    his_push_status: Mapped[AbdmSyncStatus] = mapped_column(
        Enum(AbdmSyncStatus, name="abdm_sync_status_enum"), default=AbdmSyncStatus.NOT_SYNCED, nullable=False
    )
    abdm_sync_status: Mapped[AbdmSyncStatus] = mapped_column(
        Enum(AbdmSyncStatus, name="abdm_sync_status_enum", create_type=False),
        default=AbdmSyncStatus.NOT_SYNCED,
        nullable=False,
    )
    dialogue_metrics: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, comment="ASR confidence, latency, barge-in counts, turn count"
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    patient: Mapped[Patient] = relationship("Patient", back_populates="sessions")
    consents: Mapped[List[Consent]] = relationship("Consent", back_populates="session")
    chief_complaints: Mapped[List[ChiefComplaint]] = relationship(
        "ChiefComplaint", back_populates="session", cascade="all, delete-orphan"
    )
    hpi_details: Mapped[List[HPIDetail]] = relationship(
        "HPIDetail", back_populates="session", cascade="all, delete-orphan"
    )
    past_medical_history: Mapped[List[PastMedicalHistory]] = relationship(
        "PastMedicalHistory", back_populates="session", cascade="all, delete-orphan"
    )
    medications: Mapped[List[Medication]] = relationship(
        "Medication", back_populates="session", cascade="all, delete-orphan"
    )
    allergies: Mapped[List[Allergy]] = relationship(
        "Allergy", back_populates="session", cascade="all, delete-orphan"
    )
    family_history: Mapped[List[FamilyHistory]] = relationship(
        "FamilyHistory", back_populates="session", cascade="all, delete-orphan"
    )
    personal_history: Mapped[Optional[PersonalHistory]] = relationship(
        "PersonalHistory", back_populates="session", uselist=False, cascade="all, delete-orphan"
    )
    review_of_systems: Mapped[List[ReviewOfSystems]] = relationship(
        "ReviewOfSystems", back_populates="session", cascade="all, delete-orphan"
    )
    ayush_assessment: Mapped[Optional[AyushAssessment]] = relationship(
        "AyushAssessment", back_populates="session", uselist=False, cascade="all, delete-orphan"
    )
    documents: Mapped[List[Document]] = relationship(
        "Document", back_populates="session", cascade="all, delete-orphan"
    )
    extracted_entities: Mapped[List[ExtractedEntity]] = relationship(
        "ExtractedEntity", back_populates="session", cascade="all, delete-orphan"
    )
    summaries: Mapped[List[Summary]] = relationship(
        "Summary", back_populates="session", cascade="all, delete-orphan"
    )
    red_flags: Mapped[List[RedFlag]] = relationship(
        "RedFlag", back_populates="session", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[List[AuditLog]] = relationship("AuditLog", back_populates="session")


# ==============================================================================
# 5. CHIEF COMPLAINTS TABLE
# ==============================================================================

class ChiefComplaint(Base):
    """Primary and secondary symptoms stated by the patient."""
    __tablename__ = "chief_complaints"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("history_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    complaint_text: Mapped[str] = mapped_column(Text, nullable=False)
    duration_value: Mapped[Optional[float]] = mapped_column(Numeric(5, 1), nullable=True)
    duration_unit: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="HOURS, DAYS, WEEKS, MONTHS, YEARS"
    )
    severity_scale: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    priority_rank: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    icd10_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    snomed_ct_code: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, index=True)
    ayush_term: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("severity_scale >= 1 AND severity_scale <= 10", name="chk_severity_scale"),
        Index("idx_chief_complaints_session_priority", "session_id", "priority_rank"),
    )

    # Relationships
    session: Mapped[HistorySession] = relationship("HistorySession", back_populates="chief_complaints")
    patient: Mapped[Patient] = relationship("Patient", back_populates="chief_complaints")
    hpi_details: Mapped[List[HPIDetail]] = relationship(
        "HPIDetail", back_populates="chief_complaint", cascade="all, delete-orphan"
    )


# ==============================================================================
# 6. HPI DETAILS TABLE (SOCRATES / OLDCARTS)
# ==============================================================================

class HPIDetail(Base):
    """History of Present Illness attributes mapped to SOCRATES / OLDCARTS."""
    __tablename__ = "hpi_details"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    chief_complaint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chief_complaints.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("history_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    site: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="Site / anatomical location")
    onset_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="SUDDEN, GRADUAL, INSIDIOUS"
    )
    character: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="SHARP, DULL, THROBBING, BURNING, COLICKY"
    )
    radiation: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Radiation pattern (e.g. left arm, jaw, back)"
    )
    associated_symptoms: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Nausea, diaphoresis, dyspnea, fever"
    )
    timing_pattern: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="CONSTANT, INTERMITTENT, NOCTURNAL"
    )
    exacerbating_factors: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    relieving_factors: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    severity_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    narrative_synthesis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    structured_answers: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, comment="Raw conversational question-answer pairs"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("severity_score >= 1 AND severity_score <= 10", name="chk_hpi_severity_score"),
    )

    # Relationships
    chief_complaint: Mapped[ChiefComplaint] = relationship("ChiefComplaint", back_populates="hpi_details")
    session: Mapped[HistorySession] = relationship("HistorySession", back_populates="hpi_details")


# ==============================================================================
# 7. PAST MEDICAL HISTORY TABLE
# ==============================================================================

class PastMedicalHistory(Base):
    """Pre-existing conditions, surgeries, and previous hospitalizations."""
    __tablename__ = "past_medical_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("history_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    condition_name: Mapped[str] = mapped_column(String(255), nullable=False)
    icd10_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    snomed_ct_code: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, index=True)
    onset_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    onset_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), default="ACTIVE", nullable=False, comment="ACTIVE, RESOLVED, CHRONIC, RECURRENT"
    )
    is_surgical: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    surgery_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    hospitalization_history: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    treatment_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(
        String(30), default="SELF_REPORTED", nullable=False, comment="SELF_REPORTED, SCANNED_DOCUMENT"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    session: Mapped[HistorySession] = relationship("HistorySession", back_populates="past_medical_history")
    patient: Mapped[Patient] = relationship("Patient", back_populates="past_medical_history")


# ==============================================================================
# 8. MEDICATIONS TABLE
# ==============================================================================

class Medication(Base):
    """Current and past medications, including AYUSH formulations."""
    __tablename__ = "medications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("history_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    drug_name: Mapped[str] = mapped_column(String(255), nullable=False)
    generic_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    rxnorm_code: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, index=True)
    dosage: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # e.g., 500mg
    frequency: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="ONCE_DAILY, BID, TID, QID, PRN"
    )
    route: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="ORAL, TOPICAL, INHALATION, IV"
    )
    duration: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_currently_taking: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_ayush_formulation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ayush_formulation_type: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="Churna, Vati, Kwatha, Asava, Bhasma, Taila"
    )
    source: Mapped[str] = mapped_column(
        String(30), default="SELF_REPORTED", nullable=False, comment="SELF_REPORTED, SCANNED_DOCUMENT"
    )
    drug_interaction_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    drug_interaction_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    session: Mapped[HistorySession] = relationship("HistorySession", back_populates="medications")
    patient: Mapped[Patient] = relationship("Patient", back_populates="medications")
    document: Mapped[Optional[Document]] = relationship("Document", back_populates="medications")


# ==============================================================================
# 9. ALLERGIES TABLE
# ==============================================================================

class Allergy(Base):
    """Known drug, food, and environmental hypersensitivities."""
    __tablename__ = "allergies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("history_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    allergen_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="DRUG, FOOD, ENVIRONMENTAL, CONTACT, OTHER"
    )
    allergen_name: Mapped[str] = mapped_column(String(255), nullable=False)
    reaction_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(
        String(30), default="MODERATE", nullable=False, comment="MILD, MODERATE, SEVERE, ANAPHYLACTIC"
    )
    snomed_ct_code: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, index=True)
    source: Mapped[str] = mapped_column(
        String(30), default="SELF_REPORTED", nullable=False, comment="SELF_REPORTED, SCANNED_DOCUMENT"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    session: Mapped[HistorySession] = relationship("HistorySession", back_populates="allergies")
    patient: Mapped[Patient] = relationship("Patient", back_populates="allergies")


# ==============================================================================
# 10. FAMILY HISTORY TABLE
# ==============================================================================

class FamilyHistory(Base):
    """Familial and hereditary conditions reported by the patient."""
    __tablename__ = "family_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("history_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    condition_name: Mapped[str] = mapped_column(String(255), nullable=False)
    relationship_to_patient: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="FATHER, MOTHER, SIBLING, PATERNAL_GRANDPARENT, etc."
    )
    icd10_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    snomed_ct_code: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, index=True)
    age_at_onset: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_deceased: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    session: Mapped[HistorySession] = relationship("HistorySession", back_populates="family_history")
    patient: Mapped[Patient] = relationship("Patient", back_populates="family_histories")


# ==============================================================================
# 11. PERSONAL HISTORY TABLE
# ==============================================================================

class PersonalHistory(Base):
    """Lifestyle, habits, substance use, occupation, and obstetric history."""
    __tablename__ = "personal_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("history_sessions.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    diet_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="VEGETARIAN, NON_VEGETARIAN, VEGAN, EGGETARIAN"
    )
    dietary_patterns: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sleep_hours_per_day: Mapped[Optional[float]] = mapped_column(Numeric(3, 1), nullable=True)
    sleep_quality: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="RESTFUL, DISTURBED, INSOMNIA"
    )
    exercise_frequency: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="SEDENTARY, LIGHT, MODERATE, VIGOROUS"
    )
    tobacco_use: Mapped[str] = mapped_column(
        String(30), default="NEVER", nullable=False, comment="NEVER, FORMER, ACTIVE_SMOKING, ACTIVE_CHEWING"
    )
    tobacco_frequency: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    alcohol_use: Mapped[str] = mapped_column(
        String(30), default="NEVER", nullable=False, comment="NEVER, OCCASIONAL, REGULAR, HEAVY"
    )
    alcohol_frequency: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    substance_use_other: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    occupation: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    # Obstetric / Gynecological section (for female patients)
    is_pregnant: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    gravida: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    para: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    abortions: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    living_children: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_menstrual_period: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    obstetric_history_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    session: Mapped[HistorySession] = relationship("HistorySession", back_populates="personal_history")
    patient: Mapped[Patient] = relationship("Patient", back_populates="personal_histories")


# ==============================================================================
# 12. REVIEW OF SYSTEMS (ROS) TABLE
# ==============================================================================

class ReviewOfSystems(Base):
    """Systematic review of organ systems capturing comorbid symptoms."""
    __tablename__ = "review_of_systems"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("history_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    system_name: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="CARDIOVASCULAR, RESPIRATORY, GI, NEUROLOGICAL, etc."
    )
    symptom_name: Mapped[str] = mapped_column(String(150), nullable=False)
    is_present: Mapped[bool] = mapped_column(Boolean, nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    snomed_ct_code: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_ros_session_system", "session_id", "system_name"),
    )

    # Relationships
    session: Mapped[HistorySession] = relationship("HistorySession", back_populates="review_of_systems")
    patient: Mapped[Patient] = relationship("Patient", back_populates="review_of_systems")


# ==============================================================================
# 13. AYUSH ASSESSMENTS TABLE (DASHAVIDHA PARIKSHA)
# ==============================================================================

class AyushAssessment(Base):
    """Ayurvedic clinical examination parameters including Dashavidha Pariksha."""
    __tablename__ = "ayush_assessments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("history_sessions.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # 1. Prakriti (Constitutional type)
    prakriti_primary: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="VATA, PITTA, KAPHA, VATA_PITTA, PITTA_KAPHA, VATA_KAPHA, SANNIPATAJA"
    )
    prakriti_confidence_score: Mapped[Optional[float]] = mapped_column(
        Numeric(4, 3), nullable=True, comment="Model confidence 0.000 to 1.000"
    )
    prakriti_breakdown: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, comment="Vata/Pitta/Kapha percentage breakdown"
    )
    # 2. Vikriti (Imbalance state)
    vikriti_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 3. Sara (Tissue excellence / Dhatu quality)
    sara_assessment: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="Twak Sara, Rakta Sara, Mamsa Sara, Asthi Sara, etc."
    )
    # 4. Samhanana (Compactness of body build)
    samhanana_build: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="Pravara (Stout), Madhyama (Medium), Avara (Thin)"
    )
    # 5. Pramana (Anthropometric measurements)
    pramana_height_cm: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    pramana_weight_kg: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    pramana_bmi: Mapped[Optional[float]] = mapped_column(Numeric(4, 2), nullable=True)
    # 6. Satmya (Habituation / Suitability)
    satmya_suitability: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 7. Sattva (Mental strength / Temperament)
    sattva_mental_strength: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="Pravara (Superior), Madhyama (Medium), Avara (Inferior)"
    )
    sattva_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # 8. Ahara Shakti (Digestive capacity: Abhyavaharana & Jarana)
    ahara_shakti_appetite: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="Pravara, Madhyama, Avara"
    )
    # 9. Vyayama Shakti (Exercise and physical work capacity)
    vyayama_shakti_stamina: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="Pravara, Madhyama, Avara"
    )
    # 10. Vaya (Age category)
    vaya_age_stage: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="Bala (Child), Madhyama (Youth/Middle), Vriddha (Old)"
    )
    # Additional Ayurvedic clinical parameters
    agni_status: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="SAMAGNI, VISHAMAGNI, TIKSHNAGNI, MANDAGNI"
    )
    koshtha_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="KRURA, MADHYAMA, MRIDU"
    )
    ahara_vihara_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    nidana_causes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    samprapti_pathogenesis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    dashavidha_pariksha_table: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, comment="Complete structured Pariksha grid for AYUSH summary"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    session: Mapped[HistorySession] = relationship("HistorySession", back_populates="ayush_assessment")
    patient: Mapped[Patient] = relationship("Patient", back_populates="ayush_assessments")


# ==============================================================================
# 14. DOCUMENTS TABLE (DIGITIZATION & OCR)
# ==============================================================================

class Document(Base):
    """Uploaded physical paper records scanned at kiosk."""
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("history_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, name="document_type_enum"), nullable=False, default=DocumentType.PRESCRIPTION
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="SHA-256 integrity hash"
    )
    mime_type: Mapped[str] = mapped_column(String(100), default="application/pdf", nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    scan_resolution_dpi: Mapped[int] = mapped_column(Integer, default=300, nullable=False)
    ocr_raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ocr_language_detected: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ocr_confidence_score: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    detected_document_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    chronological_sequence: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    processing_status: Mapped[DocumentProcessingStatus] = mapped_column(
        Enum(DocumentProcessingStatus, name="document_processing_status_enum"),
        default=DocumentProcessingStatus.PENDING,
        nullable=False,
        index=True,
    )
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fhir_document_reference_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    retention_purge_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="24h temp purge compliance under DPDP"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_documents_session_chrono", "session_id", "chronological_sequence"),
    )

    # Relationships
    session: Mapped[HistorySession] = relationship("HistorySession", back_populates="documents")
    patient: Mapped[Patient] = relationship("Patient", back_populates="documents")
    extracted_entities: Mapped[List[ExtractedEntity]] = relationship(
        "ExtractedEntity", back_populates="document", cascade="all, delete-orphan"
    )
    medications: Mapped[List[Medication]] = relationship("Medication", back_populates="document")


# ==============================================================================
# 15. EXTRACTED ENTITIES TABLE
# ==============================================================================

class ExtractedEntity(Base):
    """Structured clinical entities parsed from scanned OCR documents."""
    __tablename__ = "extracted_entities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("history_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_type: Mapped[EntityType] = mapped_column(
        Enum(EntityType, name="entity_type_enum"), nullable=False, index=True
    )
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    standardized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    ontology_system: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="SNOMED_CT, LOINC, RXNORM, ICD10, NAMASTE_AYUSH"
    )
    ontology_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    value_numeric: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    value_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reference_range: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_abnormal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    drug_interaction_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    contraindication_warning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    page_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    bounding_box: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, comment="Coordinates {x, y, w, h} on scanned page"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_extracted_entities_document_type", "document_id", "entity_type"),
    )

    # Relationships
    document: Mapped[Document] = relationship("Document", back_populates="extracted_entities")
    session: Mapped[HistorySession] = relationship("HistorySession", back_populates="extracted_entities")
    patient: Mapped[Patient] = relationship("Patient", back_populates="extracted_entities")


# ==============================================================================
# 16. SUMMARIES TABLE
# ==============================================================================

class Summary(Base):
    """LLM-synthesized clinical history summary for physician review and HIS push."""
    __tablename__ = "summaries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("history_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    summary_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    summary_format: Mapped[SessionMode] = mapped_column(
        Enum(SessionMode, name="session_mode_enum", create_type=False),
        nullable=False,
        default=SessionMode.ALLOPATHIC,
    )
    allopathic_summary_json: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, comment="Sections 1-11 of Allopathic PRD format"
    )
    ayush_summary_json: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, comment="Prakriti, Vikriti, Agni, Dashavidha table"
    )
    summary_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    summary_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    overall_confidence_score: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    section_confidence_scores: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, comment="Per-section confidence for physician notice"
    )
    status: Mapped[SummaryStatus] = mapped_column(
        Enum(SummaryStatus, name="summary_status_enum"), default=SummaryStatus.DRAFT, nullable=False, index=True
    )
    confirmed_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    physician_edits_diff: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, comment="Audit diff between draft and clinician confirmation"
    )
    physician_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fhir_composition_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    abdm_push_status: Mapped[AbdmSyncStatus] = mapped_column(
        Enum(AbdmSyncStatus, name="abdm_sync_status_enum", create_type=False),
        default=AbdmSyncStatus.NOT_SYNCED,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_summaries_session_version", "session_id", "summary_version"),
    )

    # Relationships
    session: Mapped[HistorySession] = relationship("HistorySession", back_populates="summaries")
    patient: Mapped[Patient] = relationship("Patient", back_populates="summaries")
    confirmed_by_user: Mapped[Optional[User]] = relationship("User", back_populates="confirmed_summaries")


# ==============================================================================
# 17. RED FLAGS TABLE
# ==============================================================================

class RedFlag(Base):
    """Emergency detection alerts halting interview and notifying triage."""
    __tablename__ = "red_flags"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("history_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    flag_category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="CHEST_PAIN_DYSPNEA, ACUTE_STROKE, SEVERE_HEADACHE, ACUTE_ABDOMEN, etc.",
    )
    severity_level: Mapped[RedFlagSeverity] = mapped_column(
        Enum(RedFlagSeverity, name="red_flag_severity_enum"),
        nullable=False,
        default=RedFlagSeverity.CRITICAL,
        index=True,
    )
    triggered_rule: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_trigger_text: Mapped[str] = mapped_column(Text, nullable=False)
    action_taken: Mapped[str] = mapped_column(
        String(100), default="INTERVIEW_HALTED_TRIAGE_ALERTED", nullable=False
    )
    kiosk_display_alert_shown: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    triage_notified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    triage_acknowledged_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    triage_acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    session: Mapped[HistorySession] = relationship("HistorySession", back_populates="red_flags")
    patient: Mapped[Patient] = relationship("Patient", back_populates="red_flags")
    triage_acknowledged_by_user: Mapped[Optional[User]] = relationship(
        "User", back_populates="acknowledged_red_flags"
    )


# ==============================================================================
# 18. AUDIT LOGS TABLE
# ==============================================================================

class AuditLog(Base):
    """Immutable audit trail retained for 7 years for DPDP Act & ABDM compliance."""
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    patient_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="SET NULL"), nullable=True, index=True
    )
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("history_sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="CREATE, READ, UPDATE, DELETE, EXPORT, CONSENT_GRANT, CONSENT_REVOKE, RED_FLAG_TRIGGER, SUMMARY_CONFIRM",
    )
    entity_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    kiosk_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    correlation_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, index=True, comment="Request correlation id for tracing"
    )
    previous_state: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    new_state: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    __table_args__ = (
        Index("idx_audit_logs_timestamp_desc", timestamp.desc()),
        Index("idx_audit_logs_patient_action", "patient_id", "action"),
    )

    # Relationships
    user: Mapped[Optional[User]] = relationship("User", back_populates="audit_logs")
    patient: Mapped[Optional[Patient]] = relationship("Patient", back_populates="audit_logs")
    session: Mapped[Optional[HistorySession]] = relationship("HistorySession", back_populates="audit_logs")


# ==============================================================================
# 19. ABDM CONSENT ARTEFACTS
# ==============================================================================

class AbdmConsentArtefact(Base):
    """ABDM Consent Manager artefacts received via the gateway callback.

    Distinct from :class:`Consent` (the kiosk's DPDP capture): this row mirrors
    the *gateway-issued* artefact that authorises a specific data flow, with its
    hi-types, date range and expiry, per ABDM HIP specifications.
    """

    __tablename__ = "abdm_consent_artefacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    consent_artefact_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    consent_request_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    patient_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="SET NULL"), nullable=True, index=True
    )
    abha_address: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    status: Mapped[str] = mapped_column(
        String(30),
        default="GRANTED",
        nullable=False,
        index=True,
        comment="REQUESTED, GRANTED, DENIED, REVOKED, EXPIRED",
    )
    purpose_code: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    hi_types: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    permission: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, comment="Access mode, date range, frequency, data erase-at"
    )
    signature: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_artefact: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    granted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (Index("idx_abdm_artefact_status_expiry", "status", "expires_at"),)

    def is_active(self, at: Optional[datetime] = None) -> bool:
        moment = at or datetime.now(timezone.utc)
        if self.status != "GRANTED" or self.revoked_at is not None:
            return False
        return self.expires_at is None or self.expires_at > moment


# ==============================================================================
# 20. INTEGRATION OUTBOX (transactional outbox + retry queue)
# ==============================================================================

class IntegrationOutbox(Base):
    """Durable queue for outbound ABDM / HIS deliveries.

    PRD §6.5.2 requires that when ABDM or the HIS is unavailable the payload is
    queued locally and retried with exponential backoff. Storing the job in the
    same transaction as the clinical write makes delivery exactly-once from the
    hospital's point of view.
    """

    __tablename__ = "integration_outbox"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    destination: Mapped[str] = mapped_column(
        String(30), nullable=False, index=True, comment="ABDM_PHR, HIS, TRIAGE_NOTIFY"
    )
    operation: Mapped[str] = mapped_column(String(60), nullable=False)
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("history_sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    patient_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="SET NULL"), nullable=True, index=True
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        default="PENDING",
        nullable=False,
        index=True,
        comment="PENDING, IN_FLIGHT, DELIVERED, FAILED, DEAD_LETTER",
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    response_payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_outbox_dispatch", "status", "next_attempt_at"),
    )


# ==============================================================================
# 21. DOCUMENT REVIEW QUEUE (low-confidence OCR -> human review)
# ==============================================================================

class DocumentReviewTask(Base):
    """Human-in-the-loop queue for documents below the OCR confidence threshold.

    PRD §6.3.2: "For other languages, fallback to human review queue if
    confidence < threshold."
    """

    __tablename__ = "document_review_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("history_sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    patient_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="SET NULL"), nullable=True, index=True
    )
    reason: Mapped[str] = mapped_column(
        String(60),
        nullable=False,
        comment="LOW_OCR_CONFIDENCE, HANDWRITING_UNRESOLVED, UNSUPPORTED_LANGUAGE, ENGINE_FAILURE",
    )
    ocr_confidence: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    detected_language: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    machine_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    corrected_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        default="PENDING",
        nullable=False,
        index=True,
        comment="PENDING, IN_REVIEW, COMPLETED, REJECTED",
    )
    priority: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    assigned_to_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("idx_review_queue_status_priority", "status", "priority"),)

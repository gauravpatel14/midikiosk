-- =============================================================================
-- MediKiosk: AI-Powered Clinical History Software Platform
-- PostgreSQL Database Schema (DPDP Act 2023 & ABDM FHIR R4 Compliant)
-- Target: PostgreSQL 14+
-- =============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- -----------------------------------------------------------------------------
-- CUSTOM ENUM TYPES
-- -----------------------------------------------------------------------------

CREATE TYPE user_role_enum AS ENUM (
    'PHYSICIAN',
    'AYUSH_PRACTITIONER',
    'TRIAGE_NURSE',
    'KIOSK_ASSISTANT',
    'ADMINISTRATOR',
    'AUDITOR'
);

CREATE TYPE session_mode_enum AS ENUM (
    'ALLOPATHIC',
    'AYUSH',
    'HYBRID'
);

CREATE TYPE session_status_enum AS ENUM (
    'IN_PROGRESS',
    'COMPLETED',
    'ABANDONED',
    'RED_FLAG_HALTED',
    'EXPIRED'
);

CREATE TYPE summary_status_enum AS ENUM (
    'DRAFT',
    'PHYSICIAN_EDITED',
    'CONFIRMED',
    'REJECTED'
);

CREATE TYPE document_type_enum AS ENUM (
    'PRESCRIPTION',
    'LAB_REPORT',
    'DISCHARGE_SUMMARY',
    'AYUSH_PRESCRIPTION',
    'IMAGING_REPORT',
    'OTHER'
);

CREATE TYPE document_processing_status_enum AS ENUM (
    'PENDING',
    'PROCESSING',
    'PROCESSED',
    'FAILED',
    'FLAGGED_REVIEW'
);

CREATE TYPE entity_type_enum AS ENUM (
    'DIAGNOSIS',
    'MEDICATION',
    'INVESTIGATION',
    'PROCEDURE',
    'VITAL_SIGN',
    'ALLERGY'
);

CREATE TYPE red_flag_severity_enum AS ENUM (
    'CRITICAL',
    'HIGH',
    'URGENT'
);

CREATE TYPE abdm_sync_status_enum AS ENUM (
    'NOT_SYNCED',
    'QUEUED',
    'SYNCED',
    'FAILED',
    'RETRYING'
);

-- =============================================================================
-- 1. USERS TABLE
-- Clinicians, triage nurses, kiosk attendants, and administrative staff
-- =============================================================================
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    role user_role_enum NOT NULL DEFAULT 'PHYSICIAN',
    department VARCHAR(100),
    specialization VARCHAR(100),
    abdm_hpr_id VARCHAR(50),
    phone_number VARCHAR(20),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_department ON users(department);

COMMENT ON TABLE users IS 'Hospital staff, clinicians, and system administrators.';
COMMENT ON COLUMN users.abdm_hpr_id IS 'ABDM Healthcare Professional Registry Identifier for digital sign-off.';

-- =============================================================================
-- 2. PATIENTS TABLE
-- Core demographic profile linked with ABHA ID and hashed Aadhaar token
-- =============================================================================
CREATE TABLE patients (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    abha_id VARCHAR(32) UNIQUE,
    abha_address VARCHAR(100) UNIQUE,
    aadhaar_hash VARCHAR(64),
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100),
    date_of_birth DATE,
    age INT,
    gender VARCHAR(20) NOT NULL,
    phone_number VARCHAR(20),
    address_line TEXT,
    district VARCHAR(100),
    state VARCHAR(100),
    pincode VARCHAR(10),
    preferred_language VARCHAR(20) NOT NULL DEFAULT 'hi',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_patients_abha_id ON patients(abha_id);
CREATE INDEX idx_patients_abha_address ON patients(abha_address);
CREATE INDEX idx_patients_phone ON patients(phone_number);
CREATE INDEX idx_patients_name ON patients(first_name, last_name);

COMMENT ON TABLE patients IS 'Patient demographic registry adhering to ABDM specifications.';
COMMENT ON COLUMN patients.aadhaar_hash IS 'SHA-256 vault token; raw Aadhaar never stored in compliance with DPDP Act 2023.';

-- =============================================================================
-- 3. CONSENTS TABLE
-- Granular consent artifacts required by DPDP Act 2023 and ABDM Framework
-- =============================================================================
CREATE TABLE consents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    session_id UUID, -- References history_sessions(id) deferred via constraint
    consent_version VARCHAR(20) NOT NULL DEFAULT 'v1.0',
    audio_explanation_played BOOLEAN NOT NULL DEFAULT TRUE,
    consent_voice_and_touch BOOLEAN NOT NULL DEFAULT FALSE,
    consent_document_scan_ocr BOOLEAN NOT NULL DEFAULT FALSE,
    consent_share_with_hospital BOOLEAN NOT NULL DEFAULT FALSE,
    consent_upload_abha_phr BOOLEAN NOT NULL DEFAULT FALSE,
    consent_method VARCHAR(30) NOT NULL DEFAULT 'TOUCH',
    ip_or_kiosk_id VARCHAR(100) NOT NULL,
    is_revoked BOOLEAN NOT NULL DEFAULT FALSE,
    revoked_at TIMESTAMPTZ,
    revocation_reason TEXT,
    tamper_proof_hash VARCHAR(64) NOT NULL,
    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_consents_patient_id ON consents(patient_id);
CREATE INDEX idx_consents_is_revoked ON consents(is_revoked);
CREATE INDEX idx_consents_granted_at ON consents(granted_at);

COMMENT ON TABLE consents IS 'Granular consent tracking with revocability support and cryptographic hash.';

-- =============================================================================
-- 4. HISTORY SESSIONS TABLE
-- Encapsulates a single patient encounter at a kiosk station
-- =============================================================================
CREATE TABLE history_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    kiosk_id VARCHAR(100) NOT NULL,
    session_token VARCHAR(128) NOT NULL UNIQUE,
    mode session_mode_enum NOT NULL DEFAULT 'ALLOPATHIC',
    status session_status_enum NOT NULL DEFAULT 'IN_PROGRESS',
    interaction_language VARCHAR(20) NOT NULL DEFAULT 'hi',
    is_priority BOOLEAN NOT NULL DEFAULT FALSE,
    question_count INT NOT NULL DEFAULT 0,
    session_timeout_minutes INT NOT NULL DEFAULT 30,
    offline_captured BOOLEAN NOT NULL DEFAULT FALSE,
    his_push_status abdm_sync_status_enum NOT NULL DEFAULT 'NOT_SYNCED',
    abdm_sync_status abdm_sync_status_enum NOT NULL DEFAULT 'NOT_SYNCED',
    dialogue_metrics JSONB,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_active_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    synced_at TIMESTAMPTZ
);

CREATE INDEX idx_history_sessions_patient_id ON history_sessions(patient_id);
CREATE INDEX idx_history_sessions_kiosk_id ON history_sessions(kiosk_id);
CREATE INDEX idx_history_sessions_status ON history_sessions(status);
CREATE INDEX idx_history_sessions_is_priority ON history_sessions(is_priority);
CREATE INDEX idx_history_sessions_started_at ON history_sessions(started_at DESC);
CREATE INDEX idx_history_sessions_metrics ON history_sessions USING GIN (dialogue_metrics);

ALTER TABLE consents
    ADD CONSTRAINT fk_consents_session_id
    FOREIGN KEY (session_id) REFERENCES history_sessions(id) ON DELETE SET NULL;

COMMENT ON TABLE history_sessions IS 'Multimodal conversational kiosk sessions.';
COMMENT ON COLUMN history_sessions.dialogue_metrics IS 'ASR speech confidence, latency, turn duration, barge-in counts.';

-- =============================================================================
-- 5. CHIEF COMPLAINTS TABLE
-- Primary clinical complaints with standardized SNOMED/ICD mappings
-- =============================================================================
CREATE TABLE chief_complaints (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES history_sessions(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    complaint_text TEXT NOT NULL,
    duration_value NUMERIC(5, 1),
    duration_unit VARCHAR(20), -- HOURS, DAYS, WEEKS, MONTHS, YEARS
    severity_scale INT CHECK (severity_scale >= 1 AND severity_scale <= 10),
    priority_rank INT NOT NULL DEFAULT 1,
    icd10_code VARCHAR(20),
    snomed_ct_code VARCHAR(30),
    ayush_term VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_chief_complaints_session ON chief_complaints(session_id, priority_rank);
CREATE INDEX idx_chief_complaints_patient ON chief_complaints(patient_id);
CREATE INDEX idx_chief_complaints_icd10 ON chief_complaints(icd10_code);
CREATE INDEX idx_chief_complaints_snomed ON chief_complaints(snomed_ct_code);

-- =============================================================================
-- 6. HPI DETAILS TABLE
-- History of Present Illness structured with SOCRATES / OLDCARTS framework
-- =============================================================================
CREATE TABLE hpi_details (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chief_complaint_id UUID NOT NULL REFERENCES chief_complaints(id) ON DELETE CASCADE,
    session_id UUID NOT NULL REFERENCES history_sessions(id) ON DELETE CASCADE,
    site TEXT,
    onset_type VARCHAR(50),
    character TEXT,
    radiation TEXT,
    associated_symptoms TEXT,
    timing_pattern TEXT,
    exacerbating_factors TEXT,
    relieving_factors TEXT,
    severity_score INT CHECK (severity_score >= 1 AND severity_score <= 10),
    narrative_synthesis TEXT,
    structured_answers JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_hpi_complaint_id ON hpi_details(chief_complaint_id);
CREATE INDEX idx_hpi_session_id ON hpi_details(session_id);
CREATE INDEX idx_hpi_structured_answers ON hpi_details USING GIN (structured_answers);

-- =============================================================================
-- 7. PAST MEDICAL HISTORY TABLE
-- Chronic diseases, prior hospitalizations, surgical interventions
-- =============================================================================
CREATE TABLE past_medical_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES history_sessions(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    condition_name VARCHAR(255) NOT NULL,
    icd10_code VARCHAR(20),
    snomed_ct_code VARCHAR(30),
    onset_date DATE,
    onset_year INT,
    status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
    is_surgical BOOLEAN NOT NULL DEFAULT FALSE,
    surgery_date DATE,
    hospitalization_history TEXT,
    treatment_summary TEXT,
    source VARCHAR(30) NOT NULL DEFAULT 'SELF_REPORTED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_pmh_patient_id ON past_medical_history(patient_id);
CREATE INDEX idx_pmh_session_id ON past_medical_history(session_id);
CREATE INDEX idx_pmh_icd10 ON past_medical_history(icd10_code);

-- =============================================================================
-- 8. DOCUMENTS TABLE (DIGITIZATION & OCR)
-- Must be created before medications/extracted_entities for foreign key references
-- =============================================================================
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES history_sessions(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    document_type document_type_enum NOT NULL DEFAULT 'PRESCRIPTION',
    original_filename VARCHAR(255) NOT NULL,
    storage_path VARCHAR(500) NOT NULL,
    file_hash VARCHAR(64) NOT NULL,
    mime_type VARCHAR(100) NOT NULL DEFAULT 'application/pdf',
    file_size_bytes INT NOT NULL,
    page_count INT NOT NULL DEFAULT 1,
    scan_resolution_dpi INT NOT NULL DEFAULT 300,
    ocr_raw_text TEXT,
    ocr_language_detected VARCHAR(50),
    ocr_confidence_score NUMERIC(4, 3) CHECK (ocr_confidence_score >= 0.0 AND ocr_confidence_score <= 1.0),
    detected_document_date DATE,
    chronological_sequence INT NOT NULL DEFAULT 1,
    processing_status document_processing_status_enum NOT NULL DEFAULT 'PENDING',
    failure_reason TEXT,
    fhir_document_reference_id VARCHAR(100),
    retention_purge_date TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_documents_session_id ON documents(session_id);
CREATE INDEX idx_documents_patient_id ON documents(patient_id);
CREATE INDEX idx_documents_chrono ON documents(session_id, chronological_sequence);
CREATE INDEX idx_documents_status ON documents(processing_status);
CREATE INDEX idx_documents_date ON documents(detected_document_date);

COMMENT ON COLUMN documents.retention_purge_date IS 'Scheduled 24-hour purge date for raw scans complying with DPDP 2023 storage limitation.';

-- =============================================================================
-- 9. MEDICATIONS TABLE
-- Active/past prescription drugs, OTC, and AYUSH formulations
-- =============================================================================
CREATE TABLE medications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES history_sessions(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
    drug_name VARCHAR(255) NOT NULL,
    generic_name VARCHAR(255),
    rxnorm_code VARCHAR(30),
    dosage VARCHAR(100),
    frequency VARCHAR(100),
    route VARCHAR(50),
    duration VARCHAR(100),
    start_date DATE,
    is_currently_taking BOOLEAN NOT NULL DEFAULT TRUE,
    is_ayush_formulation BOOLEAN NOT NULL DEFAULT FALSE,
    ayush_formulation_type VARCHAR(100),
    source VARCHAR(30) NOT NULL DEFAULT 'SELF_REPORTED',
    drug_interaction_flag BOOLEAN NOT NULL DEFAULT FALSE,
    drug_interaction_details TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_medications_patient_id ON medications(patient_id);
CREATE INDEX idx_medications_session_id ON medications(session_id);
CREATE INDEX idx_medications_document_id ON medications(document_id);
CREATE INDEX idx_medications_rxnorm ON medications(rxnorm_code);
CREATE INDEX idx_medications_ayush ON medications(is_ayush_formulation);

-- =============================================================================
-- 10. ALLERGIES TABLE
-- Drug, food, and environmental hypersensitivities
-- =============================================================================
CREATE TABLE allergies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES history_sessions(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    allergen_type VARCHAR(50) NOT NULL,
    allergen_name VARCHAR(255) NOT NULL,
    reaction_description TEXT,
    severity VARCHAR(30) NOT NULL DEFAULT 'MODERATE',
    snomed_ct_code VARCHAR(30),
    source VARCHAR(30) NOT NULL DEFAULT 'SELF_REPORTED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_allergies_patient_id ON allergies(patient_id);
CREATE INDEX idx_allergies_session_id ON allergies(session_id);
CREATE INDEX idx_allergies_snomed ON allergies(snomed_ct_code);

-- =============================================================================
-- 11. FAMILY HISTORY TABLE
-- Hereditary diseases and genetic risks
-- =============================================================================
CREATE TABLE family_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES history_sessions(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    condition_name VARCHAR(255) NOT NULL,
    relationship_to_patient VARCHAR(50) NOT NULL,
    icd10_code VARCHAR(20),
    snomed_ct_code VARCHAR(30),
    age_at_onset INT,
    is_deceased BOOLEAN,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_family_history_patient ON family_history(patient_id);
CREATE INDEX idx_family_history_session ON family_history(session_id);

-- =============================================================================
-- 12. PERSONAL HISTORY TABLE
-- Diet, sleep, exercise, tobacco, alcohol, occupation, and obstetrics
-- =============================================================================
CREATE TABLE personal_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL UNIQUE REFERENCES history_sessions(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    diet_type VARCHAR(50),
    dietary_patterns TEXT,
    sleep_hours_per_day NUMERIC(3, 1),
    sleep_quality VARCHAR(50),
    exercise_frequency VARCHAR(50),
    tobacco_use VARCHAR(30) NOT NULL DEFAULT 'NEVER',
    tobacco_frequency VARCHAR(100),
    alcohol_use VARCHAR(30) NOT NULL DEFAULT 'NEVER',
    alcohol_frequency VARCHAR(100),
    substance_use_other TEXT,
    occupation VARCHAR(150),
    is_pregnant BOOLEAN,
    gravida INT,
    para INT,
    abortions INT,
    living_children INT,
    last_menstrual_period DATE,
    obstetric_history_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_personal_history_patient ON personal_history(patient_id);

-- =============================================================================
-- 13. REVIEW OF SYSTEMS (ROS) TABLE
-- Systematic review across major anatomical organ systems
-- =============================================================================
CREATE TABLE review_of_systems (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES history_sessions(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    system_name VARCHAR(50) NOT NULL,
    symptom_name VARCHAR(150) NOT NULL,
    is_present BOOLEAN NOT NULL,
    details TEXT,
    snomed_ct_code VARCHAR(30),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ros_session_system ON review_of_systems(session_id, system_name);
CREATE INDEX idx_ros_patient_id ON review_of_systems(patient_id);

-- =============================================================================
-- 14. AYUSH ASSESSMENTS TABLE (DASHAVIDHA PARIKSHA)
-- Complete 10-fold examination parameters for Ayurvedic history taking
-- =============================================================================
CREATE TABLE ayush_assessments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL UNIQUE REFERENCES history_sessions(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    -- 1. Prakriti (Constitutional type)
    prakriti_primary VARCHAR(50),
    prakriti_confidence_score NUMERIC(4, 3) CHECK (prakriti_confidence_score >= 0.0 AND prakriti_confidence_score <= 1.0),
    prakriti_breakdown JSONB,
    -- 2. Vikriti (Current morbidity / doshic imbalance)
    vikriti_summary TEXT,
    -- 3. Sara (Tissue excellence)
    sara_assessment VARCHAR(100),
    -- 4. Samhanana (Body compactness)
    samhanana_build VARCHAR(50),
    -- 5. Pramana (Anthropometrics)
    pramana_height_cm NUMERIC(5, 2),
    pramana_weight_kg NUMERIC(5, 2),
    pramana_bmi NUMERIC(4, 2),
    -- 6. Satmya (Habituation / adaptability)
    satmya_suitability TEXT,
    -- 7. Sattva (Mental strength / psychological profile)
    sattva_mental_strength VARCHAR(50),
    sattva_score INT,
    -- 8. Ahara Shakti (Digestive & assimilative power)
    ahara_shakti_appetite VARCHAR(50),
    -- 9. Vyayama Shakti (Physical endurance & workload capacity)
    vyayama_shakti_stamina VARCHAR(50),
    -- 10. Vaya (Age stage)
    vaya_age_stage VARCHAR(50),
    -- Additional Ayurveda parameters
    agni_status VARCHAR(50),
    koshtha_type VARCHAR(50),
    ahara_vihara_notes TEXT,
    nidana_causes TEXT,
    samprapti_pathogenesis TEXT,
    dashavidha_pariksha_table JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ayush_patient_id ON ayush_assessments(patient_id);
CREATE INDEX idx_ayush_prakriti ON ayush_assessments(prakriti_primary);
CREATE INDEX idx_ayush_pariksha_table ON ayush_assessments USING GIN (dashavidha_pariksha_table);

COMMENT ON TABLE ayush_assessments IS 'Captures classical Dashavidha Pariksha (10-fold examination) and Ahara-Vihara for Ayurveda.';

-- =============================================================================
-- 15. EXTRACTED ENTITIES TABLE
-- Granular clinical entities parsed from scanned OCR documents
-- =============================================================================
CREATE TABLE extracted_entities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    session_id UUID NOT NULL REFERENCES history_sessions(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    entity_type entity_type_enum NOT NULL,
    raw_text TEXT NOT NULL,
    standardized_name VARCHAR(255) NOT NULL,
    ontology_system VARCHAR(50),
    ontology_code VARCHAR(50),
    value_numeric NUMERIC(12, 4),
    value_text TEXT,
    unit VARCHAR(50),
    reference_range VARCHAR(100),
    is_abnormal BOOLEAN NOT NULL DEFAULT FALSE,
    drug_interaction_flag BOOLEAN NOT NULL DEFAULT FALSE,
    contraindication_warning TEXT,
    confidence_score NUMERIC(4, 3) CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
    page_number INT NOT NULL DEFAULT 1,
    bounding_box JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_entities_document_id ON extracted_entities(document_id);
CREATE INDEX idx_entities_session_id ON extracted_entities(session_id);
CREATE INDEX idx_entities_patient_id ON extracted_entities(patient_id);
CREATE INDEX idx_entities_type ON extracted_entities(entity_type);
CREATE INDEX idx_entities_ontology_code ON extracted_entities(ontology_code);
CREATE INDEX idx_entities_abnormal ON extracted_entities(is_abnormal) WHERE is_abnormal = TRUE;

-- =============================================================================
-- 16. SUMMARIES TABLE
-- Synthesized clinical summaries with clinician review & confirmation lifecycle
-- =============================================================================
CREATE TABLE summaries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES history_sessions(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    summary_version INT NOT NULL DEFAULT 1,
    summary_format session_mode_enum NOT NULL DEFAULT 'ALLOPATHIC',
    allopathic_summary_json JSONB,
    ayush_summary_json JSONB,
    summary_markdown TEXT NOT NULL,
    summary_html TEXT,
    overall_confidence_score NUMERIC(4, 3) CHECK (overall_confidence_score >= 0.0 AND overall_confidence_score <= 1.0),
    section_confidence_scores JSONB,
    status summary_status_enum NOT NULL DEFAULT 'DRAFT',
    confirmed_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    confirmed_at TIMESTAMPTZ,
    physician_edits_diff JSONB,
    physician_notes TEXT,
    fhir_composition_id VARCHAR(100),
    abdm_push_status abdm_sync_status_enum NOT NULL DEFAULT 'NOT_SYNCED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_summaries_session_version ON summaries(session_id, summary_version);
CREATE INDEX idx_summaries_patient_id ON summaries(patient_id);
CREATE INDEX idx_summaries_status ON summaries(status);
CREATE INDEX idx_summaries_confirmed_by ON summaries(confirmed_by_user_id);
CREATE INDEX idx_summaries_allopathic_json ON summaries USING GIN (allopathic_summary_json);
CREATE INDEX idx_summaries_ayush_json ON summaries USING GIN (ayush_summary_json);

-- =============================================================================
-- 17. RED FLAGS TABLE
-- Immediate clinical red flag detection and triage workflow alerts
-- =============================================================================
CREATE TABLE red_flags (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES history_sessions(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    flag_category VARCHAR(100) NOT NULL,
    severity_level red_flag_severity_enum NOT NULL DEFAULT 'CRITICAL',
    triggered_rule VARCHAR(255) NOT NULL,
    raw_trigger_text TEXT NOT NULL,
    action_taken VARCHAR(100) NOT NULL DEFAULT 'INTERVIEW_HALTED_TRIAGE_ALERTED',
    kiosk_display_alert_shown BOOLEAN NOT NULL DEFAULT TRUE,
    triage_notified_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    triage_acknowledged_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    triage_acknowledged_at TIMESTAMPTZ,
    resolution_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_red_flags_session_id ON red_flags(session_id);
CREATE INDEX idx_red_flags_patient_id ON red_flags(patient_id);
CREATE INDEX idx_red_flags_severity ON red_flags(severity_level);
CREATE INDEX idx_red_flags_category ON red_flags(flag_category);
CREATE INDEX idx_red_flags_unacknowledged ON red_flags(triage_acknowledged_at) WHERE triage_acknowledged_at IS NULL;

-- =============================================================================
-- 18. AUDIT LOGS TABLE
-- Immutable security and compliance log (DPDP Act 2023 7-year retention)
-- =============================================================================
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    patient_id UUID REFERENCES patients(id) ON DELETE SET NULL,
    session_id UUID REFERENCES history_sessions(id) ON DELETE SET NULL,
    action VARCHAR(50) NOT NULL,
    entity_name VARCHAR(50) NOT NULL,
    entity_id VARCHAR(100),
    kiosk_id VARCHAR(100),
    ip_address VARCHAR(45),
    user_agent VARCHAR(255),
    previous_state JSONB,
    new_state JSONB,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_timestamp ON audit_logs(timestamp DESC);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);
CREATE INDEX idx_audit_logs_entity ON audit_logs(entity_name, entity_id);
CREATE INDEX idx_audit_logs_patient ON audit_logs(patient_id, action);
CREATE INDEX idx_audit_logs_user ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_states ON audit_logs USING GIN (previous_state, new_state);

COMMENT ON TABLE audit_logs IS 'Immutable compliance audit trail retained for 7 years as mandated by DPDP Act 2023.';

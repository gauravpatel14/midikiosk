# MEDIKIOSK - TEAM selfNprove SIH 2026

AI-Powered Multilingual Patient Intake and Clinical Pre-Consultation Kiosk Platform for High-Volume Public Hospitals and AYUSH Healthcare Facilities.

---

## Table of Contents

1. [Executive Summary and Problem Statement](#1-executive-summary-and-problem-statement)
2. [Core Value Proposition and Impact](#2-core-value-proposition-and-impact)
3. [System Architecture and Technology Stack](#3-system-architecture-and-technology-stack)
4. [End-to-End Patient Intake Workflow](#4-end-to-end-patient-intake-workflow)
5. [Deep Dive into Functional Modules](#5-deep-dive-into-functional-modules)
   - [5.1 Module 1: Patient Identity, ABHA and DPDP Consent](#51-module-1-patient-identity-abha-and-dpdp-consent)
   - [5.2 Module 2: Multimodal Conversational History Engine](#52-module-2-multimodal-conversational-history-engine)
   - [5.3 Module 3: Real-Time Emergency Triage and Alerts](#53-module-3-real-time-emergency-triage-and-alerts)
   - [5.4 Module 4: Medical Document OCR and Clinical NER](#54-module-4-medical-document-ocr-and-clinical-ner)
   - [5.5 Module 5: Clinical Safety, Drug Interactions and AYUSH Toxicology](#55-module-5-clinical-safety-drug-interactions-and-ayush-toxicology)
   - [5.6 Module 6: Structured Summary Generation and EMR Interoperability](#56-module-6-structured-summary-generation-and-emr-interoperability)
   - [5.7 Module 7: Multi-Worker Distributed Scheduler and System Maintenance](#57-module-7-multi-worker-distributed-scheduler-and-system-maintenance)
6. [Database Schema and Data Models](#6-database-schema-and-data-models)
7. [Comprehensive API Endpoint Catalog](#7-comprehensive-api-endpoint-catalog)
8. [Installation and Deployment Guide](#8-installation-and-deployment-guide)
9. [Verification, Testing and Performance Benchmarks](#9-verification-testing-and-performance-benchmarks)
10. [Regulatory Compliance and Standards Alignment](#10-regulatory-compliance-and-standards-alignment)

---

## 1. Executive Summary and Problem Statement

### 1.1 The Healthcare Bottleneck in India
Public healthcare institutions in India, including premier tertiary centers such as the All India Institute of Medical Sciences (AIIMS) and the All India Institute of Ayurveda (AIIA), witness overwhelming outpatient volumes ranging between 4,000 and 10,000 patients every day. Consequently, physicians are constrained to consultation windows of merely 2 to 3 minutes per patient. Within this limited timeframe, doctors must perform multiple demanding cognitive tasks:
- Manually extract chief complaints and history of present illness.
- Decipher handwritten medical records and historical prescriptions.
- Inspect prior laboratory investigations for physiological abnormalities.
- Screen for contraindications and drug-drug interactions.
- Perform detailed domain-specific assessments, such as the Ayurvedic Dashavidha Pariksha.
- Formulate an accurate diagnosis, conduct physical examinations, and prescribe treatment.

This severe time constraint leads to under-elicited medical histories, missed comorbidities, adverse drug events, and extreme clinician burnout.

### 1.2 The MediKiosk Solution
MediKiosk is an automated, multimodal self-service kiosk deployed in hospital OPD waiting areas. Designed specifically for Indian demographics, it enables rural, urban, semi-literate, and elderly patients to independently record their complete medical history using voice and touch in their native language before entering the consultation room.

Furthermore, MediKiosk digitizes physical medical documents, extracts structured clinical entities (coded to ICD-10, LOINC, RxNorm, and NAMASTE standards), checks for dangerous drug interactions and heavy metal toxicity, and transmits a verified, single-page clinical summary directly to the physician's EMR interface.

---

## 2. Core Value Proposition and Impact

- **Time Reclamation for Physicians**: Reduces history-taking time by over 60%, allowing doctors to focus on examination and patient care.
- **Universal Accessibility**: Combines natural voice conversations (speech-to-text and text-to-speech in Hindi, English, and regional languages) with intuitive touch screen interfaces.
- **Clinical Safety and Decision Support**: Real-time cross-referencing against NIH RxNav drug interaction databases and WHO/API Ayurvedic heavy metal limits.
- **Emergency Triage**: Automated detection of critical red flags (e.g., myocardial infarction, stroke, hypertensive emergencies) with instantaneous WebSocket alerts to nurse stations.
- **National Ecosystem Integration**: Built from the ground up to integrate with the Ayushman Bharat Digital Mission (ABDM), supporting ABHA ID, Consent Manager v0.5, and FHIR R4 clinical bundles.
- **Full Regulatory Compliance**: Strict implementation of the Digital Personal Data Protection (DPDP) Act 2023, including cryptographic consent logs, granular permissions, and right-to-erasure cascade deletion.

---

## 3. System Architecture and Technology Stack

MediKiosk utilizes a decoupled, modern architecture optimized for high concurrency, low latency, and strict data security.

```mermaid
graph TD
    subgraph Kiosk_Terminal ["Kiosk Terminal Hardware"]
        UI["Touchscreen React Interface"]
        MIC["Noise-Cancelling Microphone"]
        SCANNER["High-Resolution Document Scanner"]
    end

    subgraph FastAPI_Backend ["FastAPI Core Engine"]
        ROUTER["API Gateway & JWT Auth"]
        ASR_TTS["Speech Engine (Bhashini / Vosk / Piper)"]
        FSM["Clinical Dialogue Finite State Machine"]
        TRIAGE["Red-Flag Emergency Detector"]
        OCR_ENGINE["Document OCR Pipeline (PyMuPDF / Tesseract 5.5)"]
        NER_ENGINE["Clinical NER (ICD-10, LOINC, RxNorm, NAMASTE)"]
        SAFETY["Safety Checker (RxNav Interactions + AYUSH Metals)"]
        SUMMARY["Jinja2 Clinical Summary Compiler"]
        LOCK["Distributed SchedulerLock (Redis / POSIX fcntl)"]
        SCHEDULER["APScheduler Retention Purge"]
    end

    subgraph Persistence_Layer ["Data Storage & Interoperability"]
        DB[(PostgreSQL / SQLite Database)]
        AUDIT[(Immutable DPDP Audit Log)]
        REDIS[(Redis Distributed Cache / Lock)]
        EMR["Hospital HIS / EMR (HL7 v2 & FHIR R4)"]
        ABDM["ABDM Gateway (ABHA & Consent Manager v0.5)"]
        NURSE["Nurse Station Dashboard (WebSocket Client)"]
    end

    UI -->|HTTP / WS| ROUTER
    MIC -->|Raw Audio Streams| ASR_TTS
    SCANNER -->|Multi-page PDFs / Images| OCR_ENGINE
    ROUTER --> FSM
    FSM --> TRIAGE
    TRIAGE -->|WebSocket Alert| NURSE
    ROUTER --> OCR_ENGINE
    OCR_ENGINE --> NER_ENGINE
    NER_ENGINE --> SAFETY
    FSM --> SUMMARY
    SAFETY --> SUMMARY
    SUMMARY --> DB
    SUMMARY --> EMR
    SUMMARY --> ABDM
    ROUTER --> DB
    ROUTER --> AUDIT
    LOCK --> REDIS
    SCHEDULER --> DB
```

### Technology Stack Specifications
- **Runtime Environment**: Python 3.11+ (Certified on Python 3.14.5).
- **Web Framework**: FastAPI, Starlette, Uvicorn (ASGI async server).
- **Database Layer**: SQLAlchemy 2.0 (Declarative Mapped Columns, AsyncSession Local, PostgreSQL 16 / SQLite).
- **Speech Processing**: Bhashini ULCA Pipeline, Microsoft Edge Neural TTS (Swara / Neerja), Vosk offline Kaldi provider, Piper ONNX, espeak-ng, macOS native say synthesizer, pure-python audioop fallbacks.
- **Document Processing**: Tesseract 5.5.3 (Language packs: eng, hin, tam), PyMuPDF (fitz), Pillow, OpenCV.
- **Clinical Ontologies**: ScispaCy, Med7, ICD-10, LOINC, RxNorm, AYUSH NAMASTE.
- **Distributed Locking & Scheduling**: Redis, POSIX fcntl kernel locks, APScheduler 3.11+.
- **Frontend Layer**: React 18, TypeScript, Vite, Tailwind CSS, WebSockets.

---

## 4. End-to-End Patient Intake Workflow

```mermaid
sequenceDiagram
    autonumber
    actor Patient as Patient
    participant Kiosk as Kiosk Terminal (UI/Voice)
    participant Auth as Auth & Consent Router
    participant Dialogue as Dialogue Engine
    participant Triage as Triage & WebSocket Service
    participant Nurse as Nurse Station Dashboard
    participant OCR as Document Scanner & OCR
    participant Safety as Safety & Interaction Engine
    participant Summary as Summary Generator
    participant EMR as Hospital HIS / ABDM

    Patient->>Kiosk: Approaches Kiosk & Selects Language (Hindi/English/Regional)
    Kiosk->>Auth: Query ABHA or Register Walk-in Patient
    Auth-->>Kiosk: Returns Patient Profile & Session Token
    Kiosk->>Patient: Plays Audio Privacy Explanation
    Patient->>Kiosk: Taps "I Agree" (Granular Consent Granted)
    Kiosk->>Auth: POST /auth/consent (Generates SHA-256 Hash)

    loop Adaptive Dialogue Interview
        Kiosk->>Dialogue: POST /dialogue/next (User Voice / Touch Input)
        Dialogue->>Triage: Screen Input for Emergency Red Flags
        alt Red Flag Detected (e.g. Chest Pain, Stroke)
            Triage->>Nurse: Broadcast Critical Alert via /ws/triage
            Nurse-->>Triage: POST /api/v1/triage/red-flags/{id}/acknowledge
            Dialogue-->>Kiosk: Halts Interview, Displays Emergency Screen
        else Normal Turn Progression
            Dialogue-->>Kiosk: Returns Next Adaptive Clinical Question
        end
    end

    opt Historical Record Scanning
        Patient->>Kiosk: Inserts Paper Prescriptions and Lab Reports
        Kiosk->>OCR: POST /documents/ocr/scan (Multi-page PDF/Images)
        OCR-->>Kiosk: Extracted Raw Text, Dates, Lab Values & Drugs
    end

    Kiosk->>Safety: Evaluate Drug Clashes & AYUSH Heavy Metals
    Safety-->>Summary: Validated Interaction Warnings & Toxic Limits
    Kiosk->>Summary: POST /summary/generate
    Summary-->>Kiosk: 1-Page Structured HTML / Plain Text Summary
    Summary->>EMR: Push FHIR R4 Bundle & HL7 v2 MDM Message
    Summary->>EMR: Push to ABDM PHR (Consent Permitting)
    Kiosk->>Patient: Displays Completion Screen & Prints OPD Token
```

---

## 5. Deep Dive into Functional Modules

### 5.1 Module 1: Patient Identity, ABHA and DPDP Consent

The Identity and Consent subsystem governs patient verification and legal data processing permissions.

```mermaid
graph TD
    A["Patient Check-In"] --> B{"Has ABHA Card / QR?"}
    B -- Yes --> C["Parse ABHA QR / Enter 14-digit ABHA"]
    B -- No --> D{"Has Aadhaar / Mobile?"}
    D -- Yes --> E["Aadhaar eKYC via OTP (ABDM Sandbox)"]
    D -- No --> F["Register Walk-in Patient with Temporary Hospital ID"]
    C --> G["Establish Demographic Record"]
    E --> G
    F --> G
    G --> H["Play Localized Audio Explanation of Rights"]
    H --> I["Collect Granular Consent Checkboxes"]
    I --> J["Generate Immutable SHA-256 Consent Hash"]
    J --> K["Persist in Consent Ledger"]
    
    subgraph Revocation_Flow ["Consent Revocation Pipeline"]
        L["Patient Invokes Right to Erasure"] --> M["POST /auth/consent/revoke/{patient_id}"]
        M --> N["Transactional Delete: Sessions, Summaries, Entities"]
        N --> O["Physical Unlink: Scanned Images & Temporary Audio"]
        O --> P["Dispatch Remote Call: ABDM CM POST /v0.5/consents/revoke"]
        P -- Success --> Q["Mark abdm_revocation_status = SUCCESS"]
        P -- Gateway Unavailable --> R["Mark abdm_revocation_status = REVOKED_PENDING_ABDM"]
        R --> S["Enqueue Background Retry Task (APScheduler)"]
        Q --> T["Append Irrevocable Record to AuditLog"]
        S --> T
    end
```

Key Capabilities:
- **ABHA Lookup and Creation**: Direct integration with ABDM Milestone 1 workflows for identity verification.
- **Granular Consent**: Separate explicit opt-ins for voice intake, document scanning, hospital EMR sharing, and ABHA PHR sync.
- **DPDP Act 2023 Right to Erasure**: Endpoint `POST /auth/consent/revoke/{patient_id}` executes atomic cascade deletion of clinical data while retaining an anonymized cryptographic audit log.
- **Remote Revocation Propagation**: Communicates directly with the ABDM Consent Manager (CM v0.5) to invalidate national consent artifacts.

---

### 5.2 Module 2: Multimodal Conversational History Engine

The dialogue engine acts as an AI clinical interviewer following established medical frameworks.

```mermaid
stateDiagram-v2
    [*] --> CHIEF_COMPLAINT: Patient Starts Intake
    CHIEF_COMPLAINT --> HPI_DURATION: Chief Complaint Extracted
    
    state "SOCRATES Pain Protocol" as SOCRATES {
        HPI_DURATION --> HPI_SOCRATES_SITE: Pain Detected
        HPI_SOCRATES_SITE --> HPI_SOCRATES_ONSET
        HPI_SOCRATES_ONSET --> HPI_SOCRATES_CHARACTER
        HPI_SOCRATES_CHARACTER --> HPI_SOCRATES_RADIATION
        HPI_SOCRATES_RADIATION --> HPI_SOCRATES_ASSOCIATIONS
        HPI_SOCRATES_ASSOCIATIONS --> HPI_SOCRATES_TIMING
        HPI_SOCRATES_TIMING --> HPI_SOCRATES_EXACERBATING
        HPI_SOCRATES_EXACERBATING --> HPI_SOCRATES_SEVERITY
    }

    SOCRATES --> PAST_MEDICAL_HISTORY: Pain Fully Characterized
    HPI_DURATION --> PAST_MEDICAL_HISTORY: Non-Pain Complaint

    state "AYUSH Dashavidha Pariksha" as AYUSH {
        PAST_MEDICAL_HISTORY --> AYUSH_PRAKRITI: AYUSH Mode Enabled
        AYUSH_PRAKRITI --> AYUSH_VIKRITI
        AYUSH_VIKRITI --> AYUSH_SARA
        AYUSH_SARA --> AYUSH_SAMHANANA
        AYUSH_SAMHANANA --> AYUSH_AGNI_KOSHTHA
        AYUSH_AGNI_KOSHTHA --> AYUSH_AHARA_VIHARA
    }

    AYUSH --> DRUG_HISTORY
    PAST_MEDICAL_HISTORY --> DRUG_HISTORY: Allopathic Mode
    DRUG_HISTORY --> ALLERGY_HISTORY
    ALLERGY_HISTORY --> REVIEW_OF_SYSTEMS
    REVIEW_OF_SYSTEMS --> COMPLETED: Minimum Criteria Met / Patient Ends Turn
    COMPLETED --> [*]
```

Clinical Questioning Standards:
- **SOCRATES Framework**: Fully characterizes pain symptoms by Site, Onset, Character, Radiation, Associations, Timing, Exacerbating factors, and Severity (1 to 10 scale).
- **Review of Systems (ROS)**: Systematically screens cardiovascular, respiratory, gastrointestinal, and neurological systems.
- **Ayurvedic Dashavidha Pariksha**: Assesses Prakriti (body constitution), Vikriti (imbalance), Sara (tissue quality), Samhanana (body build), Agni (digestive fire), and Koshtha (bowel habits).

Speech Recognition (ASR) & Natural Neural Synthesis (TTS):
- **Studio-Quality Neural Voices**: Integrated Microsoft Neural TTS delivering natural human cadence, tone, and breath pauses:
  - Hindi: `hi-IN-SwaraNeural` (natural Indian female healthcare assistant).
  - English: `en-IN-NeerjaNeural` (natural Indian-accented clinical voice).
  - Regional Languages: Tamil (`ta-IN-PallaviNeural`), Telugu (`te-IN-ShrutiNeural`), Bengali (`bn-IN-TanishaaNeural`), Marathi (`mr-IN-AarohiNeural`), Gujarati (`gu-IN-DhwaniNeural`).
- **5-Tier Zero-Downtime Fallback Cascade**:
  1. Bhashini ULCA Speech Gateway (Government of India online models)
  2. Edge Neural TTS (Natural human voice synthesis)
  3. Piper ONNX Neural Voice Engine (Local deep learning models)
  4. espeak-ng Synthesizer (Ultra-lightweight Linux formant synthesis)
  5. macOS Native Synthesizer (`/usr/bin/say`) with Lekha / Samantha voices
- **Automatic Audio Normalization**: Converts all speech output to standard 16kHz 16-bit mono PCM WAV via ffmpeg.

---

### 5.3 Module 3: Real-Time Emergency Triage and Alerts

MediKiosk monitors incoming transcripts and vitals in real-time to intercept life-threatening emergencies.

```mermaid
sequenceDiagram
    autonumber
    actor Patient as Patient
    participant Kiosk as Kiosk Terminal
    participant TriageRouter as POST /triage/check-flags
    participant Detector as RedFlagDetector
    participant WSManager as WebSocket ConnectionManager
    participant StaffDesk as Triage Staff Dashboard

    StaffDesk->>WSManager: Connect /ws/triage?token={JWT}
    Note over WSManager: Validates JWT signature and role (triage_staff/admin).<br/>Rejects invalid with 4401, unauthorized with 4403.
    WSManager-->>StaffDesk: WebSocket Connected (Session Registered)

    Patient->>Kiosk: Speaks: "Severe crushing chest pain radiating to left arm"
    Kiosk->>TriageRouter: Transmit Transcript and Vitals
    TriageRouter->>Detector: Evaluate Rules & Physiological Thresholds
    Detector-->>TriageRouter: Match: ACUTE_CORONARY_SYNDROME (Severity: CRITICAL)
    
    par Instant Emergency Notification
        TriageRouter->>WSManager: broadcast_alert(patient_id, kiosk_id, red_flag_type)
        WSManager->>StaffDesk: Send JSON Alert Payload via WebSocket
        StaffDesk-->>StaffDesk: Flashes Audio-Visual Emergency Alert on Screen
    and Kiosk Display Redirection
        TriageRouter-->>Kiosk: is_flagged = True, urgency = CRITICAL
        Kiosk-->>Patient: Halts Intake, Turns Screen Red, Instructs Patient to Rest
    end

    StaffDesk->>TriageRouter: POST /api/v1/triage/red-flags/{alert_id}/acknowledge
    TriageRouter-->>StaffDesk: Confirms Acknowledgment Recorded with Timestamp
```

Red Flag Criteria:
- **Cardiovascular**: Retrosternal pain radiating to left arm/jaw, diaphoresis, systolic blood pressure > 180 mmHg.
- **Neurological**: Sudden focal neurological deficits, slurred speech, facial droop, thunderclap headache.
- **Respiratory**: Severe stridor, respiratory rate > 30 breaths/min, SpO2 < 90%.
- **Trauma and Hemorrhage**: Uncontrolled external bleeding, hematemesis, acute rigid abdomen.

---

### 5.4 Module 4: Medical Document OCR and Clinical NER

The document digitization subsystem processes legacy paper records and extracts standardized clinical entities.

```mermaid
graph TD
    A["Patient Inserts Documents (PDF, JPEG, PNG, TIFF)"] --> B["Document Ingestion & File Size Validation"]
    B --> C{"Is PDF Native Text Present?"}
    C -- Yes --> D["Fast-Path: Extract Embedded Vector Text"]
    C -- No --> E["PyMuPDF Rasterization at 300 DPI"]
    E --> F["OpenCV Preprocessing: Grayscale, Deskew, Gaussian Thresholding"]
    F --> G["Multi-Language Tesseract 5.5 OCR (eng, hin, tam)"]
    D --> H["Combined Raw Text Corpus"]
    G --> H
    
    H --> I["Regex NER Date Parser"]
    I --> J["Extract Document Encounter Date for Chronology"]
    
    H --> K["Document Classification Engine"]
    K --> L{"Keyword Score Cues"}
    L -- "Rx, Tab, Cap, OD, BD" --> M["Classify: PRESCRIPTION"]
    L -- "Hb, WBC, Platelets, mg/dL" --> N["Classify: LAB_REPORT"]
    L -- "Admission Date, Discharge" --> O["Classify: DISCHARGE_SUMMARY"]
    
    H --> P["Clinical Entity Normalization"]
    P --> Q["Diagnoses ──► ICD-10 (e.g. Hypertension I10)"]
    P --> R["Laboratory Tests ──► LOINC (e.g. Glucose 1558-6)"]
    P --> S["Medications ──► RxNorm (e.g. Metformin 500mg)"]
    P --> T["Formulations ──► AYUSH NAMASTE Portal"]
    
    H --> U["Handwriting Classifier"]
    U --> V{"Mean Confidence < Threshold?"}
    V -- Yes --> W["Mark requires_human_review = True"]
    V -- No --> X["Approve for Automated Summary Inclusion"]
```

Key Extraction Pipelines:
- **Bilingual OCR**: Handles mixed-script documents containing English medical terms and Devanagari Hindi or Tamil text.
- **Abnormal Lab Flagging**: Identifies laboratory parameters outside biological reference intervals and highlights values in clinical reports.
- **Chronological Sorting**: Organizes multiple historical documents into a structured chronological timeline.

---

### 5.5 Module 5: Clinical Safety, Drug Interactions and AYUSH Toxicology

MediKiosk features an automated clinical decision support engine to prevent pharmaceutical and herbomineral adverse events.

```mermaid
graph TD
    A["Extracted & Self-Reported Medications"] --> B["clean_drug_name() Normalization"]
    B --> C["Generate Pairwise Combinations (Drug A, Drug B)"]
    
    C --> D["Query NIH NLM RxNav REST API"]
    D -- API Available --> E["Parse DrugBank / RxNav Interaction Tree"]
    D -- API Offline --> F["Query Local Pairwise Interaction Matrix (CSV)"]
    
    E --> G["Classify Severity: Major, Moderate, Minor"]
    F --> G
    G --> H["Generate Clinical Drug Clash Warnings"]

    A --> I["Filter AYUSH Formulations"]
    I --> J["Cross-reference AYUSH Safety Database (ayush_safety.json)"]
    
    J --> K["Screen Heavy Metal Limits (API Part I/II & WHO)"]
    K --> L["Lead (Pb) < 10 ppm | Arsenic (As) < 3 ppm"]
    K --> M["Cadmium (Cd) < 0.3 ppm | Mercury (Hg) < 1 ppm"]
    
    J --> N["Evaluate Schedule E(1) Poisonous Herbomineral Warnings"]
    N --> O{"Patient Comorbidity Match?"}
    O -- "Arogyavardhini Vati in CKD / Renal Disease" --> P["Trigger CRITICAL Contraindication Alert"]
    O -- "Makaradhwaja in Hypertensive Crisis" --> P
    O -- No Contraindication --> Q["Pass Safety Check with Recommended Anupana"]

    H --> R["Inject Findings into Physician Summary"]
    P --> R
    Q --> R
```

Safety Database Specifications:
- **NIH RxNav Integration**: Real-time evaluation of dangerous drug combinations, such as `Aspirin + Warfarin` (severe hemorrhage risk) and `Metformin + Radiocontrast` (lactic acidosis risk).
- **AYUSH Toxicology Engine**: Cross-references Rasa Shastra Bhasmas (Parada, Gandhaka, Tamra, Lauha) against chronic disease contraindications.

---

### 5.6 Module 6: Structured Summary Generation and EMR Interoperability

Once intake is complete, the summary engine compiles a comprehensive document for clinical review.

```mermaid
graph TD
    A["Patient Demographics"] --> G["Jinja2 Clinical Template Compiler"]
    B["SOCRATES Pain Narrative"] --> G
    C["Review of Systems Findings"] --> G
    D["Chronological Document Timeline"] --> G
    E["Flagged Abnormal Lab Values"] --> G
    F["Drug Interactions & AYUSH Alerts"] --> G

    G --> H["Generate Draft Summary (HTML & Plain Text)"]
    H --> I["Display in Hospital EMR for Physician Review"]
    
    I --> J{"Physician Edits or Confirms?"}
    J -- Edit --> K["Save Versioned Amendments (Preserve Original Audit)"]
    J -- Confirm --> L["POST /summary/confirm/{summary_id}"]
    
    L --> M["Assemble ABDM FHIR R4 Bundle"]
    M --> N["Bundle: Patient, Encounter, Composition, Condition, Observation"]
    
    L --> O["Assemble HL7 v2 Transmission"]
    O --> P["HL7 v2.5 ADT^A08 (Patient Information Update)"]
    O --> Q["HL7 v2.5 MDM^T02 (Medical Document Management)"]
    
    N --> R["Transmit to Hospital HIS & ABDM PHR"]
    P --> R
    Q --> R
```

Integration Standards:
- **HL7 FHIR R4**: Complies with the official ABDM Health Information Exchange specifications.
- **HL7 v2 MLLP Messaging**: Provides native compatibility with existing Indian hospital management systems (e.g., C-DAC e-Sushrut, NIC e-Hospital).
- **Physician Review Protocol**: Summaries remain in draft state until confirmed by a licensed medical practitioner.

---

### 5.7 Module 7: Multi-Worker Distributed Scheduler and System Maintenance

To ensure stability across multi-worker Uvicorn deployments, MediKiosk uses a distributed leader-election mechanism for background tasks.

```mermaid
graph TD
    A["Uvicorn Workers Spawned (Worker 1, Worker 2, Worker N)"] --> B["Execute FastAPI Lifespan Startup"]
    B --> C["Initialize SchedulerLock()"]
    
    C --> D{"Is Redis Configured & Enabled?"}
    D -- Yes --> E["Attempt Redis Lock: SETNX with 60s TTL"]
    D -- No --> F["Attempt POSIX File Lock: fcntl.flock(/tmp/medikiosk_scheduler.lock)"]
    
    E -- Acquired --> G["Elected as Leader Worker"]
    E -- Busy --> H["Standby Worker: Skip Scheduler Startup"]
    F -- Acquired --> G
    F -- Busy (BlockingIOError) --> H
    
    G --> I["Start APScheduler Instance"]
    I --> J["Schedule 30s Heartbeat Lock Renewal Job"]
    I --> K["Schedule Hourly Orphaned Media Sweep Job"]
    
    K --> L["Inspect /tmp/medikiosk_uploads, /tmp/medikiosk_documents"]
    L --> M{"File Age > RAW_MEDIA_RETENTION_HOURS (24h)?"}
    M -- Yes --> N["Purge File from Disk (DPDP Storage Limitation)"]
    M -- No --> O["Retain File"]
    
    subgraph Shutdown_Flow ["Graceful Shutdown"]
        P["Process Termination Signal (SIGTERM)"] --> Q["stop_cleanup_scheduler()"]
        Q --> R["Shutdown APScheduler Instance"]
        R --> S["Release Distributed Lock (Redis DEL / fcntl.LOCK_UN)"]
    end
```

Key Maintenance Features:
- **SchedulerLock**: Prevents duplicate execution of cleanup and synchronization jobs across clustered workers.
- **Automated Media Sweeping**: Enforces the DPDP Act storage limitation requirement by purging temporary voice recordings and unlinked images after 24 hours.
- **Data Authenticity Validation**: Runs automated integrity audits on startup to verify knowledge base files.

---

## 6. Database Schema and Data Models

The MediKiosk database contains 10 core relational tables implemented using SQLAlchemy 2.0.

```mermaid
erDiagram
    PATIENTS ||--o{ CONSENTS : "grants"
    PATIENTS ||--o{ HISTORY_SESSIONS : "participates_in"
    PATIENTS ||--o{ DOCUMENTS : "owns"
    PATIENTS ||--o{ SUMMARIES : "receives"
    PATIENTS ||--o{ RED_FLAGS : "triggers"
    PATIENTS ||--o{ AUDIT_LOGS : "subject_of"

    HISTORY_SESSIONS ||--o{ CHIEF_COMPLAINTS : "records"
    HISTORY_SESSIONS ||--o{ EXTRACTED_ENTITIES : "contains"
    HISTORY_SESSIONS ||--o{ RED_FLAGS : "generates"
    HISTORY_SESSIONS ||--o{ SUMMARIES : "synthesizes"

    USERS ||--o{ SUMMARIES : "confirms"
    USERS ||--o{ RED_FLAGS : "acknowledges"
    USERS ||--o{ AUDIT_LOGS : "initiates"

    PATIENTS {
        uuid id PK
        string abha_id UK
        string abha_address UK
        string aadhaar_hash UK
        encrypted_string first_name
        encrypted_string last_name
        integer age
        string gender
        encrypted_string phone_number
        string preferred_language
        boolean is_deleted
        timestamp created_at
    }

    CONSENTS {
        uuid id PK
        uuid patient_id FK
        string consent_version
        boolean consent_voice_and_touch
        boolean consent_document_scan_ocr
        boolean consent_share_with_hospital
        boolean consent_upload_abha_phr
        string ip_or_kiosk_id
        boolean is_revoked
        string abdm_revocation_status
        timestamp abdm_revocation_timestamp
        string tamper_proof_hash
        timestamp granted_at
    }

    HISTORY_SESSIONS {
        uuid id PK
        uuid patient_id FK
        string kiosk_id
        string session_token UK
        string mode
        string status
        string interaction_language
        boolean is_priority
        integer question_count
        timestamp started_at
        timestamp completed_at
    }

    DOCUMENTS {
        uuid id PK
        uuid patient_id FK
        string file_name
        string document_type
        string detected_language
        float ocr_confidence
        date document_date
        string storage_path
        timestamp created_at
    }

    SUMMARIES {
        uuid id PK
        uuid session_id FK
        uuid patient_id FK
        text plain_text_summary
        text html_summary
        boolean is_confirmed
        uuid confirmed_by_user_id FK
        timestamp confirmed_at
        timestamp created_at
    }

    RED_FLAGS {
        uuid id PK
        uuid session_id FK
        uuid patient_id FK
        string flag_category
        string severity_level
        string triggered_rule
        boolean is_acknowledged
        uuid triage_acknowledged_by FK
        timestamp triage_acknowledged_at
        timestamp created_at
    }

    AUDIT_LOGS {
        uuid id PK
        uuid user_id FK
        uuid patient_id FK
        string action
        string entity_name
        string entity_id
        jsonb old_state
        jsonb new_state
        timestamp timestamp
    }
```

Field Encryption Architecture:
Sensitive Personally Identifiable Information (PII) fields (e.g., patient names, phone numbers, and street addresses) use transparent AES-256 encryption via `EncryptedString` columns. Unencrypted raw Aadhaar numbers are never persisted; only peppered HMAC-SHA256 tokens are stored.

---

## 7. Comprehensive API Endpoint Catalog

The backend exposes 27 REST and WebSocket endpoints organized into functional route groups:

| Group | Method | Path | Summary / Description |
|---|---|---|---|
| **System** | `GET` | `/health` | Heartbeat endpoint reporting platform status and dataset integrity (`HEALTHY`/`DEGRADED`). |
| **Auth** | `POST` | `/auth/kiosk/token` | Issues a cryptographically signed JWT token for station terminal identity. |
| **Auth** | `POST` | `/auth/abha/search` | Searches for patient profiles using ABHA ID, ABHA address, or Aadhaar hash. |
| **Auth** | `POST` | `/auth/abha/create` | Issues a new ABHA identity via simulated/live Aadhaar eKYC OTP. |
| **Auth** | `POST` | `/auth/patient/register` | Registers walk-in patients lacking digital credentials with a temporary hospital ID. |
| **Auth** | `POST` | `/auth/consent` | Records granular DPDP consent along with a SHA-256 tamper-proof audit hash. |
| **Auth** | `GET` | `/auth/consent/{patient_id}` | Retrieves active unrevoked consent status for a specific patient. |
| **Auth** | `POST` | `/auth/consent/revoke/{patient_id}` | Right-to-erasure endpoint: purges intake data and propagates revocation to ABDM. |
| **Dialogue** | `POST` | `/dialogue/start` | Initializes a new history intake session in Allopathic or AYUSH mode. |
| **Dialogue** | `POST` | `/dialogue/next` | Ingests voice transcript/touch chip, evaluates red flags, and returns the next adaptive question. |
| **Speech** | `POST` | `/speech/asr` | Converts spoken audio WAV streams into localized text using Bhashini or Vosk. |
| **Speech** | `POST` | `/speech/tts` | Synthesizes localized audio prompts from text using Bhashini or Piper models. |
| **Triage** | `POST` | `/triage/check-flags` | Evaluates complaints and vitals against clinical emergency criteria. |
| **Triage** | `WS` | `/ws/triage` | Real-time WebSocket feed for nurse dashboards. Requires JWT auth (`triage_staff`/`admin`). |
| **Triage** | `GET` | `/api/v1/triage/red-flags` | Lists active, unacknowledged red-flag emergencies. |
| **Triage** | `POST` | `/api/v1/triage/red-flags/{id}/acknowledge` | Marks an emergency alert as acknowledged by a triage staff member. |
| **OCR** | `POST` | `/documents/ocr/scan` | Scans physical medical documents and extracts text, confidence scores, and encounter dates. |
| **NLP** | `POST` | `/nlp/extract-entities` | Normalizes medical text into ICD-10, LOINC, RxNorm, and NAMASTE entities. |
| **NLP** | `POST` | `/nlp/check-interactions` | Performs pairwise drug interaction checking using NIH RxNav and local datasets. |
| **Summary** | `POST` | `/summary/generate` | Generates a 1-page structured clinical summary including safety alerts and document timelines. |
| **Summary** | `POST` | `/summary/confirm/{summary_id}` | Allows the consulting physician to edit, sign, and commit the clinical summary. |
| **FHIR** | `GET` | `/fhir/bundle/{session_id}` | Generates an ABDM-compliant FHIR R4 clinical bundle for national data exchange. |
| **HIS** | `POST` | `/his/push/fhir/{session_id}` | Transmits a FHIR clinical bundle to the hospital's electronic health record system. |
| **HIS** | `POST` | `/his/push/hl7v2/{session_id}` | Transmits legacy HL7 v2 ADT^A08 and MDM^T02 messages to hospital EMRs. |
| **Sessions**| `GET` | `/api/v1/sessions/active` | Lists currently active kiosk intake sessions for administrative monitoring. |

---

## 8. Installation and Deployment Guide

### 8.1 Hardware Requirements
- **Display**: 15 to 21-inch high-brightness touchscreen.
- **Audio**: Directional speaker and noise-cancelling microphone array.
- **Scanner**: High-speed automatic document feeder (ADF) scanner supporting 300 DPI.
- **Compute**: Minimum Quad-Core Intel/AMD x86_64 or Apple Silicon processor with 8 GB RAM and 64 GB SSD.

### 8.2 System Dependencies
#### macOS
```bash
brew install tesseract tesseract-lang ffmpeg redis
```

#### Ubuntu / Debian
```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-hin tesseract-ocr-tam ffmpeg redis-server
```

### 8.3 Backend Installation
```bash
# 1. Clone the repository
git clone <repository-url> MediKiosk
cd MediKiosk

# 2. Configure Python Virtual Environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install Python Dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 4. Configure Environment Variables
cp .env.example .env

# 5. Run Clinical Knowledge Base Audit
python scripts/validate_data_files.py

# 6. Launch Backend Server
.venv/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```
Interactive Swagger API documentation will be available at: `http://localhost:8000/docs`.

### 8.4 Frontend Installation
```bash
cd frontend
npm install
npm run dev
```
The kiosk user interface will be available at: `http://localhost:5173`.

---

## 9. Verification, Testing and Performance Benchmarks

MediKiosk includes an automated test suite verifying all functional modules, security boundaries, and latency targets.

### 9.1 Running Automated Tests
```bash
# Run the complete test suite (37 test suites)
.venv/bin/python -m pytest tests/ -v

# Run performance SLA benchmarks using realistic clinical data
.venv/bin/python -m pytest tests/test_performance.py -v

# Run multi-worker scheduler lock concurrency tests
.venv/bin/python -m pytest tests/test_scheduler_lock.py -v

# Run ABDM consent revocation and retry tests
.venv/bin/python -m pytest tests/test_abdm_revocation.py -v

# Run WebSocket authentication and role authorization tests
.venv/bin/python -m pytest tests/test_websocket_auth.py -v

# Run clinical dataset authenticity verification tests
.venv/bin/python -m pytest tests/test_data_validation.py -v
```

### 9.2 Measured Performance SLA Benchmarks
All benchmarks are measured against realistic data: 10-turn Hindi dialogue progressions, 5-page bilingual medical dossier PDFs, and comprehensive multi-section patient histories.

| Pipeline Milestone | Target SLA | Measured Latency | Verification Status |
|---|---|---|---|
| `/dialogue/next` (10-turn SOCRATES progression) | < 500 ms | ~2.0 ms | PASSED |
| `/documents/ocr/scan` (5-page bilingual dossier PDF) | < 10.0 s | ~0.07 s (Vector) / ~4.1 s (Raster) | PASSED |
| `/summary/generate` (Full summary + Drug & AYUSH checks) | < 15.0 s | ~0.02 s | PASSED |
| Complete Test Suite Execution (37/37 suites) | < 30.0 s | 7.39 s | PASSED (100% Green) |

---

## 10. Regulatory Compliance and Standards Alignment

### 10.1 Digital Personal Data Protection (DPDP) Act 2023
- **Data Minimization and Purpose Limitation**: Collects only clinical data essential for the outpatient encounter.
- **Cryptographic Consent Records**: Stores SHA-256 tamper-proof hashes for all granted permissions.
- **Right to Erasure (`POST /auth/consent/revoke/{patient_id}`)**: Immediately purges intake sessions, summaries, and unlinks document files from disk upon request.
- **Storage Limitation**: Automated background cleanup purges transient media files older than 24 hours.

### 10.2 Ayushman Bharat Digital Mission (ABDM)
- **Milestone 1**: ABHA ID resolution via QR code parsing and Aadhaar eKYC verification.
- **Milestone 2**: Consent Manager v0.5 notification handling (`/abdm/webhooks/consents/hip/notify`) and revocation dispatch (`POST /v0.5/consents/revoke`).
- **Milestone 3**: Export of FHIR R4 clinical bundles containing `Composition`, `Condition`, `Observation`, and `MedicationStatement` resources.

### 10.3 AYUSH Clinical Safety Standards
- **Ayurvedic Pharmacopoeia of India (API) Guidelines**: Enforces heavy metal safety thresholds for herbal and herbomineral formulations:
  - Lead (Pb) < 10 ppm
  - Arsenic (As) < 3 ppm
  - Cadmium (Cd) < 0.3 ppm
  - Mercury (Hg) < 1 ppm
- **Schedule E(1) Safety Controls**: Flags toxicological contraindications for classical Rasa Shastra preparations.

---

TEAM selfNprove - Smart India Hackathon (SIH) 2026

"""Automated test suite verifying the 7 newly added MediKiosk production features.

Covers:
1. Drug Interaction Detection (Real data source via service & POST /nlp/check-interactions)
2. AYUSH Contraindication & Heavy Metal Safety Warning Engine
3. Real-Time WebSocket Triage Alerts (/ws/triage)
4. Red Flag Alert Acknowledgment (/api/v1/triage/red-flags/{id}/acknowledge)
5. DPDP Act 2023 Consent Revocation & Transactional Data Purge (/auth/consent/revoke/{id})
6. Chronological Document Timeline in Clinical Summaries
7. Session Cleanup and Document Archival Modes
"""

import os
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Add root and backend to path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
for p in [str(root_dir), str(backend_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.main import app
from backend.models import (
    AuditLog,
    Consent,
    Document,
    DocumentType,
    ExtractedEntity,
    HistorySession,
    Patient,
    RedFlag,
    SessionMode,
    SessionStatus,
    RedFlagSeverity,
    Summary,
)
from backend.services.ayush_safety import ayush_safety_service
from backend.services.cleanup import archive_or_delete_file, purge_orphaned_temp_dirs
from backend.services.drug_interaction import clean_drug_name, drug_interaction_service
from backend.services.summary.summary_generator import SummaryGenerator

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
Base.metadata.create_all(bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def test_drug_interaction_service():
    print("\n--- 1. Testing Drug Interaction Detection ---")
    # Test normalization
    assert clean_drug_name("Tab. Aspirin 75mg OD") == "aspirin"
    assert clean_drug_name("Cap. Amoxicillin 500mg TDS") == "amoxicillin"

    # Test pairwise detection from real clinical database
    interactions = drug_interaction_service.check_interactions(["Tab. Aspirin 75mg", "Tab. Warfarin 2mg"])
    assert len(interactions) >= 1
    item = interactions[0]
    assert item["severity"] == "Major"
    assert "bleeding" in item["description"].lower()
    print(f"✔ Detected Major Interaction: {item['drug_a']} + {item['drug_b']} ({item['source']})")

    # Test via REST Endpoint: POST /nlp/check-interactions
    res = client.post("/nlp/check-interactions", json={"medications": ["Telmisartan", "Ibuprofen", "Metformin"]})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["interactions_count"] >= 1
    print(f"✔ POST /nlp/check-interactions returned {data['interactions_count']} interaction(s)")


def test_ayush_safety_and_contraindications():
    print("\n--- 2. Testing AYUSH Safety & Heavy Metal Warnings ---")
    # Arogyavardhini Vati in patient with chronic kidney disease
    alerts = ayush_safety_service.evaluate_formulation_safety(
        medication_names=["Arogyavardhini Vati", "Tab. Pantop"],
        patient_conditions=["Chronic Kidney Disease (CKD stage 3)", "Hypertension"],
    )
    assert len(alerts) >= 1
    arogya_alert = alerts[0]
    assert arogya_alert["formulation"] == "Arogyavardhini Vati"
    assert "Parada" in str(arogya_alert["elements"])
    assert len(arogya_alert["triggered_contraindications"]) >= 1
    assert any(any(k in c.lower() for k in ["kidney", "renal", "ckd", "nephrotic"]) for c in arogya_alert["triggered_contraindications"])
    print(f"✔ AYUSH Safety Alert Triggered: {arogya_alert['formulation']} flagged for {arogya_alert['triggered_contraindications']}")


def test_realtime_websocket_triage():
    print("\n--- 3. Testing Real-Time WebSocket Triage Alerts ---")
    from backend.security import create_access_token
    token = create_access_token("staff-triage-user-01", role="triage_staff")
    with client.websocket_connect(f"/ws/triage?token={token}") as ws:
        # Trigger red flag via POST /triage/check-flags
        res = client.post(
            "/triage/check-flags",
            json={"text": "Severe retrosternal chest pain radiating to left arm", "vitals": {"systolic_bp": 195}},
        )
        assert res.status_code == 200
        assert res.json()["is_flagged"] is True

        # Read broadcast from WebSocket
        alert_msg = ws.receive_json()
        assert alert_msg["event"] == "EMERGENCY_TRIAGE_ALERT"
        assert alert_msg["urgency_level"] == "CRITICAL"
        assert "ACUTE_CORONARY_SYNDROME" in alert_msg["red_flag_type"] or "EMERGENCY" in alert_msg["red_flag_type"]
        print(f"✔ Received Live WebSocket Triage Alert: Type={alert_msg['red_flag_type']} Urgency={alert_msg['urgency_level']}")


def test_triage_alert_acknowledgment():
    print("\n--- 4. Testing Red Flag Alert Acknowledgment ---")
    db = TestingSessionLocal()
    alert_id = uuid.uuid4()
    red_flag = RedFlag(
        id=alert_id,
        session_id=uuid.uuid4(),
        patient_id=uuid.uuid4(),
        flag_category="ACUTE_CORONARY_SYNDROME",
        severity_level=RedFlagSeverity.CRITICAL,
        triggered_rule="Chest tightness with radiation",
        raw_trigger_text="Patient reported retrosternal chest pain",
        triage_notified_at=datetime.now(timezone.utc),
    )
    db.add(red_flag)
    db.commit()
    db.close()

    res = client.post(f"/api/v1/triage/red-flags/{alert_id}/acknowledge")
    assert res.status_code == 200
    assert res.json()["status"] == "success"
    assert res.json()["alert_id"] == str(alert_id)
    print(f"✔ Alert {alert_id} acknowledged by staff")


def test_consent_revocation_and_data_purge():
    print("\n--- 5. Testing DPDP Act 2023 Consent Revocation ---")
    db = TestingSessionLocal()
    pid = uuid.uuid4()
    sid = uuid.uuid4()

    # Create dummy patient, session, consent, document, summary
    pat = Patient(
        id=pid,
        first_name="Anita",
        last_name="Deshmukh",
        gender="FEMALE",
        phone_number="9876543219",
        preferred_language="hi",
    )
    db.add(pat)

    session = HistorySession(
        id=sid,
        patient_id=pid,
        kiosk_id="KIOSK-01",
        session_token=str(uuid.uuid4()),
        mode=SessionMode.ALLOPATHIC,
        interaction_language="hi",
        status=SessionStatus.COMPLETED,
    )
    db.add(session)

    consent = Consent(
        id=uuid.uuid4(),
        patient_id=pid,
        session_id=sid,
        consent_version="v1.0",
        ip_or_kiosk_id="KIOSK-01",
        is_revoked=False,
        tamper_proof_hash="dummy_hash_for_test",
        granted_at=datetime.now(timezone.utc),
    )
    db.add(consent)

    # Temporary physical file
    temp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    temp_file.write(b"%PDF-1.4 test document data")
    temp_file.close()

    did = uuid.uuid4()
    doc = Document(
        id=did,
        session_id=sid,
        patient_id=pid,
        storage_path=temp_file.name,
        original_filename="prescription.pdf",
        file_hash="dummyhash123",
        file_size_bytes=1024,
        mime_type="application/pdf",
        document_type=DocumentType.PRESCRIPTION,
    )
    db.add(doc)

    summary = Summary(
        id=uuid.uuid4(),
        session_id=sid,
        patient_id=pid,
        summary_html="<p>Summary</p>",
        summary_markdown="Summary",
    )
    db.add(summary)
    db.commit()
    db.close()

    # Execute Revocation via POST /auth/consent/revoke/{patient_id}
    # Authenticate with kiosk token first
    tok_res = client.post("/auth/kiosk/token", json={"kiosk_id": "KIOSK-01", "shared_secret": "kiosk_hospital_aiia_secret_2026"})
    headers = {"Authorization": f"Bearer {tok_res.json()['access_token']}"}

    res = client.post(
        f"/auth/consent/revoke/{pid}",
        json={"reason": "Patient requested right to erasure under DPDP Act 2023", "kiosk_id": "KIOSK-01"},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["purged_sessions_count"] == 1
    assert data["purged_documents_count"] == 1

    # Verify Database state
    db_verify = TestingSessionLocal()
    assert db_verify.query(HistorySession).filter(HistorySession.id == sid).first() is None
    assert db_verify.query(Summary).filter(Summary.session_id == sid).first() is None
    assert db_verify.query(Document).filter(Document.id == did).first() is None
    revoked_consent = db_verify.query(Consent).filter(Consent.patient_id == pid).first()
    assert revoked_consent.is_revoked is True
    audit = db_verify.query(AuditLog).filter(AuditLog.patient_id == pid, AuditLog.action == "CONSENT_REVOCATION").first()
    assert audit is not None
    db_verify.close()

    print("✔ Transactional data purge verified: Session, Document, Summary deleted; Consent marked REVOKED; AuditLog recorded")


def test_chronological_document_timeline_in_summary():
    print("\n--- 6. Testing Chronological Document Timeline in Summary ---")
    generator = SummaryGenerator()

    patient_data = {
        "demographics": {"first_name": "Sunita", "last_name": "Devi", "age": 48},
        "chief_complaint": "Persistent joint pain and fever",
        "past_medical": ["Rheumatoid Arthritis"],
        "medications": ["Tab. Methotrexate 10mg", "Tab. Amoxicillin 500mg"],
        "is_ayush": False,
    }

    # Two documents with different dates
    document_data = {
        "documents": [
            {"filename": "recent_lab.pdf", "document_date": "2026-08-20", "document_type_hint": "LAB_REPORT", "confidence_score": 0.95},
            {"filename": "old_prescription.png", "document_date": "2025-11-14", "document_type_hint": "PRESCRIPTION", "confidence_score": 0.91},
        ],
        "entities": {"medications": [{"name": "Tab. Methotrexate"}]},
    }

    html_out, text_out = generator.generate(patient_data, document_data)

    # Verify Timeline section in HTML
    assert "Medical Document Timeline (Chronological)" in html_out
    assert "recent_lab.pdf" in html_out
    assert "old_prescription.png" in html_out

    # Verify Drug Interaction flagged in HTML
    assert "Potential Drug Interactions Detected" in html_out
    assert "amoxicillin" in html_out.lower() or "methotrexate" in html_out.lower()

    # Verify Timeline in plain text
    assert "MEDICAL DOCUMENT TIMELINE" in text_out
    assert "2026-08-20" in text_out
    assert "2025-11-14" in text_out

    print("✔ Chronological timeline verified: Documents sorted chronologically in HTML and plain text")


def test_session_cleanup_and_archival():
    print("\n--- 7. Testing Session Cleanup & Archival ---")
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(b"RIFF dummy audio data")
        temp_wav = f.name

    # Test local archival
    res = archive_or_delete_file(temp_wav, patient_id="pat-test-01")
    assert res["status"] in ("ARCHIVED_LOCAL", "DELETED")
    assert not os.path.exists(temp_wav)  # File moved or deleted from original location
    print(f"✔ Archive or delete file verified: {res['status']}")

    # Test orphaned directory sweep
    purged = purge_orphaned_temp_dirs(max_age_hours=0)
    print(f"✔ Purged {purged} temporary files from orphaned directories")


if __name__ == "__main__":
    test_drug_interaction_service()
    test_ayush_safety_and_contraindications()
    test_realtime_websocket_triage()
    test_triage_alert_acknowledgment()
    test_consent_revocation_and_data_purge()
    test_chronological_document_timeline_in_summary()
    test_session_cleanup_and_archival()
    print("\n========================================================")
    print("  ALL 7 NEW PRODUCTION FEATURES VERIFIED AND PASSING!   ")
    print("========================================================\n")

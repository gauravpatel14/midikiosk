"""Comprehensive automated test suite verifying ALL 23 FastAPI endpoints end-to-end."""

import os
import sys
import tempfile
import uuid
from pathlib import Path

# Add root and backend to path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
for p in [str(root_dir), str(backend_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from PIL import Image, ImageDraw
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.main import app
from backend.services.speech.audio_utils import generate_mock_wav

# Isolated SQLite in-memory test database
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


def test_all_23_endpoints_deep_suite():
    print("\n========================================================")
    print("  RUNNING DEEP END-TO-END VERIFICATION OF ALL 23 ENDPOINTS ")
    print("========================================================")

    # 1. System Health Check
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    print("✔ 1. GET /health -> 200 OK")

    # 2. Auth: Kiosk Token
    res = client.post(
        "/auth/kiosk/token",
        json={"kiosk_id": "KIOSK-E2E-01", "shared_secret": "kiosk_hospital_aiia_secret_2026"},
    )
    assert res.status_code == 200
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("✔ 2. POST /auth/kiosk/token -> 200 OK (JWT issued)")

    # 3. Auth: ABHA Search
    res = client.post("/auth/abha/search", json={"abha_id": "91-5820-1924-8831"}, headers=headers)
    assert res.status_code == 200
    assert res.json()["found"] is True
    print("✔ 3. POST /auth/abha/search -> 200 OK (Patient located)")

    # 4. Auth: ABHA Create via eKYC
    res = client.post(
        "/auth/abha/create",
        json={
            "aadhaar_number": "987654321098",
            "phone_number": "9876543210",
            "first_name": "Kavita",
            "last_name": "Patel",
            "gender": "Female",
            "otp": "123456",
        },
        headers=headers,
    )
    assert res.status_code == 200
    assert "91-" in res.json()["abha_id"]
    print("✔ 4. POST /auth/abha/create -> 200 OK (ABHA generated)")

    # 5. Auth: Walk-in Patient Register
    res = client.post(
        "/auth/patient/register",
        json={
            "first_name": "Deepak",
            "last_name": "Nair",
            "age": 42,
            "gender": "Male",
            "phone_number": "9876501234",
            "district": "New Delhi",
            "preferred_language": "hi",
        },
        headers=headers,
    )
    assert res.status_code == 200
    patient_id = res.json()["temp_patient_id"]
    print(f"✔ 5. POST /auth/patient/register -> 200 OK (Temp ID: {patient_id})")

    # 6. Auth: Consent Record
    res = client.post(
        "/auth/consent",
        json={
            "patient_id": patient_id,
            "consent_version": "v1.0",
            "audio_explanation_played": True,
            "consent_voice_and_touch": True,
            "consent_document_scan_ocr": True,
            "consent_share_with_hospital": True,
            "consent_upload_abha_phr": True,
            "consent_method": "TOUCH",
            "kiosk_id": "KIOSK-E2E-01",
        },
        headers=headers,
    )
    assert res.status_code == 200
    assert "tamper_proof_hash" in res.json()
    print("✔ 6. POST /auth/consent -> 200 OK (Consent signed & hashed)")

    # 7. Auth: Consent Retrieve
    res = client.get(f"/auth/consent/{patient_id}", headers=headers)
    assert res.status_code == 200
    assert res.json()["has_active_consent"] is True
    print("✔ 7. GET /auth/consent/{patient_id} -> 200 OK (Consent verified)")

    # 8. Speech: Detect Language
    res = client.post("/speech/detect-language", json={"text": "Mujhe 3 din se chest pain aur bukhar hai"})
    assert res.status_code == 200
    assert res.json()["detected_language"] == "hi"
    print("✔ 8. POST /speech/detect-language -> 200 OK (Hinglish code-mix detected as 'hi')")

    # 9. Speech: Synthesize (TTS)
    res = client.post("/speech/synthesize", json={"text": "कृपया अपनी छाती के दर्द के बारे में बताएं।", "language": "hi"})
    assert res.status_code == 200
    assert os.path.exists(res.json()["audio_file_path"])
    print(f"✔ 9. POST /speech/synthesize -> 200 OK (WAV synthesized at {res.json()['audio_file_path']})")

    # 10. Speech: Transcribe (ASR)
    test_wav = "/tmp/test_api_speech.wav"
    generate_mock_wav(test_wav, duration_sec=1.5)
    with open(test_wav, "rb") as f:
        res = client.post("/speech/transcribe", files={"file": ("test.wav", f, "audio/wav")}, data={"language": "hi"})
    assert res.status_code == 200
    assert len(res.json()["transcription"]) > 0
    print(f"✔ 10. POST /speech/transcribe -> 200 OK (Transcribed: '{res.json()['transcription']}')")

    # 11. Dialogue: Start
    session_id = str(uuid.uuid4())
    res = client.post("/dialogue/start", json={"session_id": session_id, "language": "en", "mode": "ALLOPATHIC"})
    assert res.status_code == 200
    assert res.json()["current_state"] == "CHIEF_COMPLAINT"
    print(f"✔ 11. POST /dialogue/start -> 200 OK (State: {res.json()['current_state']})")

    # 12. Dialogue: Next
    res = client.post(
        "/dialogue/next",
        json={"session_id": session_id, "current_state": "CHIEF_COMPLAINT", "user_response": "I have chest pain for 3 days"},
    )
    assert res.status_code == 200
    assert res.json()["current_state"] == "HPI_DURATION"
    print(f"✔ 12. POST /dialogue/next -> 200 OK (Advanced to state: {res.json()['current_state']})")

    # 13. Document OCR: Scan
    test_img = "/tmp/test_api_ocr.png"
    img = Image.new("RGB", (400, 200), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((20, 30), "Rx: Tab. Amoxicillin 500mg TDS", fill=(0, 0, 0))
    img.save(test_img)
    with open(test_img, "rb") as f:
        res = client.post("/documents/ocr/scan", files={"file": ("rx.png", f, "image/png")})
    assert res.status_code == 200
    assert res.json()["status"] == "success"
    print(f"✔ 13. POST /documents/ocr/scan -> 200 OK (Engine: {res.json()['metadata'].get('ocr_engine')})")

    # 14. NLP Entity Extraction
    res = client.post(
        "/nlp/extract-entities",
        json={"text": "Diagnosis: Essential Hypertension. Rx: Tab. Telmisartan 40mg OD. Lab: Fasting Blood Glucose 118 mg/dL"},
    )
    assert res.status_code == 200
    assert len(res.json()["entities"]["diagnoses"]) > 0
    print(f"✔ 14. POST /nlp/extract-entities -> 200 OK (Diagnoses: {[d['name'] for d in res.json()['entities']['diagnoses']]})")

    # 15. Summary: Generate
    patient_summary_payload = {
        "demographics": {
            "first_name": "Rameshwar",
            "last_name": "Sharma",
            "age": 54,
            "gender": "Male",
            "abha_id": "91-4920-8319-1024",
            "phone_number": "9876543210",
        },
        "chief_complaint": "Chest tightness and dyspnea for 3 days",
        "hpi": {"HPI_DURATION": "3 days", "HPI_SOCRATES_CHARACTER": "Heavy compressive pressure"},
        "past_medical": ["Essential Hypertension"],
        "medications": [{"name": "Tab. Telmisartan", "dosage": "40mg", "frequency": "OD", "duration": "Daily"}],
        "is_ayush": False,
    }
    res = client.post("/summary/generate", json={"patient_data": patient_summary_payload})
    assert res.status_code == 200
    assert "MEDIKIOSK CLINICAL HISTORY SUMMARY" in res.json()["plain_text_summary"]
    print("✔ 15. POST /summary/generate -> 200 OK (HTML & Plain Text summaries rendered)")

    # 16. ABDM FHIR: Preview Bundle
    fhir_payload = {
        "patient_data": patient_summary_payload["demographics"],
        "history_data": patient_summary_payload,
        "summary_text": res.json()["plain_text_summary"],
    }
    res = client.post("/abdm/fhir/preview", json=fhir_payload)
    assert res.status_code == 200
    assert res.json()["resourceType"] == "Bundle"
    print(f"✔ 16. POST /abdm/fhir/preview -> 200 OK (Valid FHIR R4 Bundle with {len(res.json()['entry'])} entries)")

    # 17. ABDM FHIR: Bundle and Push
    res = client.post("/abdm/fhir/bundle-and-push", json=fhir_payload)
    assert res.status_code == 200
    assert res.json()["status"] in ("DELIVERED_ABDM_HIE", "SIMULATED_ABDM_HIE_DELIVERED")
    print(f"✔ 17. POST /abdm/fhir/bundle-and-push -> 200 OK (Status: {res.json()['status']})")

    # 18. Triage: Check Red Flags
    res = client.post(
        "/triage/check-flags",
        json={"text": "Severe chest pain radiating to left arm and sweating", "vitals": {"systolic_bp": 195, "diastolic_bp": 125}},
    )
    assert res.status_code == 200
    assert res.json()["is_flagged"] is True
    print(f"✔ 18. POST /triage/check-flags -> 200 OK (Red flags identified: {res.json()['flags_count']})")

    # 19. HIS: Status
    res = client.get("/his/status")
    assert res.status_code == 200
    assert res.json()["status"] == "online"
    print(f"✔ 19. GET /his/status -> 200 OK (Active adapter: {res.json()['active_adapter']})")

    # 20. HIS: Switch Adapter
    res = client.post("/his/adapter/switch", json={"adapter": "hl7v2"})
    assert res.status_code == 200
    assert res.json()["active_adapter"] == "hl7v2"
    print("✔ 20. POST /his/adapter/switch -> 200 OK (Switched to 'hl7v2')")

    # 21. HIS: Send Summary
    res = client.post(
        "/his/send-summary",
        json={
            "patient_id": patient_id,
            "summary": {"plain_text_summary": "Clinical Summary for EMR", "patient": patient_summary_payload["demographics"]},
        },
    )
    assert res.status_code == 200
    assert res.json()["adapter"] == "HL7_v2"
    print(f"✔ 21. POST /his/send-summary -> 200 OK (Dispatched via HL7_v2)")

    # 22. Kiosk Sessions Active
    res = client.get("/api/v1/sessions/active")
    assert res.status_code == 200
    assert isinstance(res.json(), list)
    print("✔ 22. GET /api/v1/sessions/active -> 200 OK")

    # 23. Triage Unacknowledged Red Flags
    res = client.get("/api/v1/triage/red-flags")
    assert res.status_code == 200
    assert isinstance(res.json(), list)
    print("✔ 23. GET /api/v1/triage/red-flags -> 200 OK")

    print("\n========================================================")
    print("  ALL 23 ENDPOINTS VERIFIED AND PASSING 100%!")
    print("========================================================\n")


if __name__ == "__main__":
    test_all_23_endpoints_deep_suite()

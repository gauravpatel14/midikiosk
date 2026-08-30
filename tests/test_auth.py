"""Automated test suite verifying all 6 Auth, ABHA, and Consent endpoints."""

import sys
from pathlib import Path

# Add root and backend directory to path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
for p in [str(root_dir), str(backend_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

try:
    from backend.main import app
    from backend.database import get_db, Base
except ImportError:
    from main import app
    from database import get_db, Base

# Setup in-memory SQLite isolated test database
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


def test_auth_and_consent_suite():
    print("\n--- Running MediKiosk Auth & Consent Test Suite ---")

    # 1. Kiosk Internal JWT Token
    res = client.post(
        "/auth/kiosk/token",
        json={"kiosk_id": "KIOSK-01", "shared_secret": "kiosk_hospital_aiia_secret_2026"},
    )
    assert res.status_code == 200, res.text
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("✔ 1. POST /auth/kiosk/token: Internal JWT issued successfully")

    # 2. ABHA Search
    res = client.post(
        "/auth/abha/search",
        json={"abha_id": "91-5820-1924-8831"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    search_data = res.json()
    assert search_data["found"] is True
    patient_id = search_data["patient_id"]
    print(f"✔ 2. POST /auth/abha/search: Patient located (ID: {patient_id})")

    # 3. ABHA Create via eKYC
    res = client.post(
        "/auth/abha/create",
        json={
            "aadhaar_number": "987654321098",
            "phone_number": "9876543210",
            "first_name": "Aarav",
            "last_name": "Verma",
            "gender": "Male",
            "otp": "123456",
        },
        headers=headers,
    )
    assert res.status_code == 200, res.text
    create_data = res.json()
    assert "91-" in create_data["abha_id"]
    print(f"✔ 3. POST /auth/abha/create: ABHA created via eKYC (ABHA: {create_data['abha_id']})")

    # 4. Patient Register (Walk-in without ABHA)
    res = client.post(
        "/auth/patient/register",
        json={
            "first_name": "Meera",
            "last_name": "Kumari",
            "age": 32,
            "gender": "Female",
            "phone_number": "9123456780",
            "district": "New Delhi",
            "preferred_language": "hi",
        },
        headers=headers,
    )
    assert res.status_code == 200, res.text
    reg_patient_id = res.json()["temp_patient_id"]
    print(f"✔ 4. POST /auth/patient/register: Walk-in registered (Temp ID: {reg_patient_id})")

    # 5. Consent Record
    res = client.post(
        "/auth/consent",
        json={
            "patient_id": reg_patient_id,
            "consent_version": "v1.0",
            "audio_explanation_played": True,
            "consent_voice_and_touch": True,
            "consent_document_scan_ocr": True,
            "consent_share_with_hospital": True,
            "consent_upload_abha_phr": True,
            "consent_method": "TOUCH",
            "kiosk_id": "KIOSK-01",
        },
        headers=headers,
    )
    assert res.status_code == 200, res.text
    consent_id = res.json()["consent_id"]
    tamper_hash = res.json()["tamper_proof_hash"]
    print(f"✔ 5. POST /auth/consent: Consent recorded (Tamper Hash: {tamper_hash[:16]}...)")

    # 6. Consent Retrieve
    res = client.get(f"/auth/consent/{reg_patient_id}", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["has_active_consent"] is True
    assert len(res.json()["active_consents"]) == 1
    print(f"✔ 6. GET /auth/consent/{{patient_id}}: Active consent retrieved successfully")

    print("\n--- ALL 6 ENDPOINTS VERIFIED AND PASSING 100% ---")


if __name__ == "__main__":
    test_auth_and_consent_suite()

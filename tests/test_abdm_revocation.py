"""Test ABDM Consent Revocation Propagation & Retry Logic."""

import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.core.config import settings
from backend.database import Base, get_db
from backend.main import app
from backend.models import (
    AuditLog,
    Consent,
    HistorySession,
    Patient,
    SessionMode,
    SessionStatus,
)
from backend.services.abdm.consent import AbdmConsentService

TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    previous = app.dependency_overrides.get(get_db)

    def _override():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override
    yield
    if previous is not None:
        app.dependency_overrides[get_db] = previous
    else:
        app.dependency_overrides.pop(get_db, None)


def test_abdm_revocation_success_propagation(monkeypatch):
    client = TestClient(app)
    db = TestingSessionLocal()

    pid = uuid.uuid4()
    patient = Patient(
        id=pid,
        first_name="Ramesh",
        last_name="Gupta",
        gender="Male",
        phone_number="9876543210",
        preferred_language="hi",
    )
    db.add(patient)

    cid = uuid.uuid4()
    consent = Consent(
        id=cid,
        patient_id=pid,
        consent_version="v1.0",
        consent_voice_and_touch=True,
        consent_share_with_hospital=True,
        ip_or_kiosk_id="KIOSK-01",
        tamper_proof_hash="hash123",
        is_revoked=False,
    )
    db.add(consent)
    db.commit()
    db.close()

    # Mock ABDM Consent Revocation Success
    revoked_calls = []

    async def mock_revoke(self, consent_id: str, reason: str = ""):
        revoked_calls.append({"consent_id": consent_id, "reason": reason})
        return {"status": "SUCCESS", "consentId": consent_id}

    monkeypatch.setattr(AbdmConsentService, "revoke_consent", mock_revoke)

    tok_res = client.post("/auth/kiosk/token", json={"kiosk_id": "KIOSK-01", "shared_secret": "kiosk_hospital_aiia_secret_2026"})
    headers = {"Authorization": f"Bearer {tok_res.json()['access_token']}"}

    res = client.post(
        f"/auth/consent/revoke/{pid}",
        json={"reason": "Revocation requested by patient", "kiosk_id": "KIOSK-01"},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["abdm_revocation_status"] == "SUCCESS"
    assert len(revoked_calls) == 1
    assert revoked_calls[0]["consent_id"] == str(cid)

    # Verify DB state
    db_verify = TestingSessionLocal()
    rev_consent = db_verify.query(Consent).filter(Consent.id == cid).first()
    assert rev_consent.is_revoked is True
    assert rev_consent.abdm_revocation_status == "SUCCESS"
    assert rev_consent.abdm_revocation_timestamp is not None
    db_verify.close()


def test_abdm_revocation_failure_and_retry_path(monkeypatch):
    client = TestClient(app)
    db = TestingSessionLocal()

    pid = uuid.uuid4()
    patient = Patient(
        id=pid,
        first_name="Sunita",
        last_name="Devi",
        gender="Female",
        phone_number="9876543211",
        preferred_language="hi",
    )
    db.add(patient)

    cid = uuid.uuid4()
    consent = Consent(
        id=cid,
        patient_id=pid,
        consent_version="v1.0",
        consent_voice_and_touch=True,
        ip_or_kiosk_id="KIOSK-01",
        tamper_proof_hash="hash456",
        is_revoked=False,
    )
    db.add(consent)
    db.commit()
    db.close()

    # Mock ABDM Gateway failure
    async def mock_revoke_fail(self, consent_id: str, reason: str = ""):
        raise ConnectionError("ABDM Gateway 503 Service Unavailable")

    monkeypatch.setattr(AbdmConsentService, "revoke_consent", mock_revoke_fail)

    tok_res = client.post("/auth/kiosk/token", json={"kiosk_id": "KIOSK-01", "shared_secret": "kiosk_hospital_aiia_secret_2026"})
    headers = {"Authorization": f"Bearer {tok_res.json()['access_token']}"}

    # Endpoint must not fail; should mark REVOKED_PENDING_ABDM locally
    res = client.post(
        f"/auth/consent/revoke/{pid}",
        json={"reason": "Patient requested data deletion", "kiosk_id": "KIOSK-01"},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["abdm_revocation_status"] == "REVOKED_PENDING_ABDM"

    # Verify DB state
    db_verify = TestingSessionLocal()
    rev_consent = db_verify.query(Consent).filter(Consent.id == cid).first()
    assert rev_consent.is_revoked is True
    assert rev_consent.abdm_revocation_status == "REVOKED_PENDING_ABDM"
    db_verify.close()

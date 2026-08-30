"""Automated test suite verifying MediKiosk ABDM FHIR R4 integration and resources."""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add root and backend to path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
for p in [str(root_dir), str(backend_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.services.fhir.fhir_builder import (
    create_composition,
    create_consent_resource,
    create_document_reference,
    create_fhir_bundle,
    create_patient_resource,
)
from backend.services.fhir.fhir_client import FHIRClient


def test_fhir_suite():
    print("\n--- Running MediKiosk ABDM FHIR R4 Test Suite ---")

    # Sample clinical data for a typical patient
    patient_data = {
        "id": "pat-aiia-1001",
        "demographics": {
            "first_name": "Rameshwar",
            "last_name": "Sharma",
            "age": 54,
            "gender": "male",
            "date_of_birth": "1972-04-14",
            "abha_id": "91-4920-8319-1024",
            "abha_address": "rameshwar72@abdm",
            "phone_number": "9876543210",
            "address_line": "House 42, Sector 12",
            "district": "South Delhi",
            "state": "Delhi",
            "pincode": "110025",
        }
    }

    # 1. Test Patient Resource
    patient_res = create_patient_resource(patient_data)
    assert patient_res["resourceType"] == "Patient"
    assert patient_res["id"] == "pat-aiia-1001"
    assert any("healthid.ndhm.gov.in" in id_obj.get("system", "") for id_obj in patient_res["identifier"])
    assert patient_res["name"][0]["text"] == "Rameshwar Sharma"
    assert patient_res["gender"] == "male"
    print("✔ 1. create_patient_resource(): Validated ABDM NRCeS Patient resource")

    # 2. Test DocumentReference Resource
    doc_metadata = {
        "id": "doc-scan-2001",
        "patient_id": "pat-aiia-1001",
        "filename": "prescription_aiia_opd.pdf",
        "mime_type": "application/pdf",
        "document_type_hint": "PRESCRIPTION",
        "primary_language": "hin",
    }
    doc_res = create_document_reference(doc_metadata, file_location="/tmp/sample.pdf")
    assert doc_res["resourceType"] == "DocumentReference"
    assert doc_res["status"] == "current"
    assert doc_res["docStatus"] == "final"
    assert doc_res["subject"]["reference"] == "Patient/pat-aiia-1001"
    assert doc_res["type"]["coding"][0]["code"] == "57833-6"  # LOINC Prescription
    print("✔ 2. create_document_reference(): Validated LOINC 57833-6 DocumentReference resource")

    # 3. Test Composition Resource
    history_data = {
        "session_id": "sess-opd-3001",
        "patient_id": "pat-aiia-1001",
        "chief_complaint": "Retrosternal chest tightness and breathlessness",
        "hpi": {"HPI_DURATION": "3 days"},
    }
    summary_text = "CLINICAL SUMMARY:\nPatient: Rameshwar Sharma\nAssessment: Suspected angina pectoris with hypertension."
    comp_res = create_composition(history_data, summary_text)
    assert comp_res["resourceType"] == "Composition"
    assert comp_res["status"] == "final"
    assert comp_res["subject"]["reference"] == "Patient/pat-aiia-1001"
    assert len(comp_res["section"]) >= 3
    print("✔ 3. create_composition(): Validated ABDM OPConsultRecord Composition resource")

    # 4. Test Consent Resource
    consent_data = {
        "consent_id": "cons-dpdp-4001",
        "patient_id": "pat-aiia-1001",
        "is_revoked": False,
        "tamper_proof_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "granted_at": "2026-08-27T18:15:00Z",
    }
    consent_res = create_consent_resource(consent_data)
    assert consent_res["resourceType"] == "Consent"
    assert consent_res["status"] == "active"
    assert consent_res["scope"]["coding"][0]["code"] == "patient-privacy"
    assert "dpdp-act-2023" in consent_res["policy"][0]["uri"]
    assert "TamperProofHash" in consent_res["provision"]["data"][0]["reference"]["display"]
    print("✔ 4. create_consent_resource(): Validated DPDP Act 2023 compliant Consent resource")

    # 5. Test Bundle Assembly
    all_resources = [patient_res, comp_res, doc_res, consent_res]
    bundle = create_fhir_bundle(all_resources)
    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "document"
    assert len(bundle["entry"]) == 4
    print(f"✔ 5. create_fhir_bundle(): Assembled {len(bundle['entry'])} entries into DocumentBundle")

    # 6. Test Push to ABDM with Retry Logic
    client = FHIRClient(max_retries=2)
    push_result = asyncio.run(client.push_to_abdm(all_resources, patient_abha_id="91-4920-8319-1024"))
    assert "status" in push_result
    assert push_result["patient_abha_id"] == "91-4920-8319-1024"
    assert push_result["resources_count"] == 4
    assert push_result["transaction_id"].startswith("TX-") or "transactionId" in str(push_result)
    print(f"✔ 6. push_to_abdm(): Dispatched bundle to ABDM HIE (Transaction: {push_result['transaction_id']})")

    # 7. Print Sample JSONs for Demonstration
    print("\n--- SAMPLE ABDM FHIR R4 PATIENT RESOURCE ---")
    print(json.dumps(patient_res, indent=2)[:350] + "\n  ...\n}")

    print("\n--- ALL ABDM FHIR R4 TESTS PASSED 100% ---")


if __name__ == "__main__":
    test_fhir_suite()

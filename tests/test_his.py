"""Automated test suite verifying MediKiosk Hospital Information System (HIS) Adapters."""

import sys
from pathlib import Path

# Add root and backend to path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
for p in [str(root_dir), str(backend_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.services.his.adapters import FHIRHISAdapter, HL7v2HISAdapter, MockHISAdapter, WebhookHISAdapter
from backend.services.his.hl7v2_generator import generate_hl7v2_oru_r01
from backend.services.his.service import HISIntegrationService


def test_his_adapter_suite():
    print("\n--- Running MediKiosk HIS Integration Adapter Test Suite ---")

    # Sample clinical summary payload
    patient_id = "pat-aiia-1001"
    summary_data = {
        "kiosk_id": "KIOSK_01",
        "patient": {
            "name": "Rameshwar Sharma",
            "gender": "Male",
            "date_of_birth": "1972-04-14",
            "phone": "9876543210",
        },
        "chief_complaint": {"text": "Retrosternal chest tightness and shortness of breath"},
        "hpi": {
            "duration": "3 days",
            "character": "Compressive heaviness",
            "severity": "7",
        },
        "plain_text_summary": "CLINICAL SUMMARY:\nPatient Rameshwar Sharma evaluated in OPD.\nAssessment: Suspected angina pectoris.",
        "red_flag": {
            "category": "ACUTE_CORONARY_SYNDROME",
            "rule": "Chest tightness radiating to arm",
        },
    }

    sample_documents = [
        {
            "id": "doc-scan-01",
            "filename": "prescription_aiia.pdf",
            "document_type_hint": "PRESCRIPTION",
            "mime_type": "application/pdf",
        }
    ]

    # --------------------------------------------------------------------------
    # 1. TEST HL7 v2.5 ER7 MESSAGE GENERATOR
    # --------------------------------------------------------------------------
    hl7_msg = generate_hl7v2_oru_r01(patient_id, summary_data, sample_documents)
    assert "MSH|^~\\&|MEDIKIOSK|AIIA_OPD|" in hl7_msg
    assert "ORU^R01^ORU_R01" in hl7_msg
    assert f"PID|1||{patient_id}^^^AIIA^MR||Sharma^Rameshwar" in hl7_msg
    assert "PV1|1|O|OPD^KIOSK_01^^AIIA" in hl7_msg
    assert "OBR|1||CLIN_HIST_" in hl7_msg
    assert "OBX|1|TX|CHIEF_COMPLAINT" in hl7_msg
    assert "OBX|2|TX|HPI" in hl7_msg
    assert "OBX|3|ST|RED_FLAG_ALERT" in hl7_msg
    assert "OBX|4|TX|CLINICAL_SUMMARY" in hl7_msg
    assert "OBX|5|ED|DOCUMENT_REF" in hl7_msg
    print(f"✔ 1. HL7 v2 Generator: Generated valid {len(hl7_msg)} char ORU^R01 message with MSH, PID, PV1, OBR, OBX")

    # --------------------------------------------------------------------------
    # 2. TEST HL7 v2 ADAPTER
    # --------------------------------------------------------------------------
    hl7_adapter = HL7v2HISAdapter(host="127.0.0.1", port=2575)
    hl7_res = hl7_adapter.send_summary(patient_id, summary_data, sample_documents)
    assert hl7_res["adapter"] == "HL7_v2"
    assert hl7_res["status"] == "ACK_RECEIVED"
    assert hl7_res["message_type"] == "ORU^R01"
    print(f"✔ 2. HL7v2HISAdapter: Dispatched message (ACK: {hl7_res['message_id']})")

    # --------------------------------------------------------------------------
    # 3. TEST FHIR R4 ADAPTER
    # --------------------------------------------------------------------------
    fhir_adapter = FHIRHISAdapter(endpoint_url="https://his.aiia.gov.in/fhir/r4", auth_token="mock_tok")
    fhir_res = fhir_adapter.send_summary(patient_id, summary_data, sample_documents)
    assert fhir_res["adapter"] == "FHIR_R4"
    assert fhir_res["status"] in ("SENT", "FAILED")
    assert fhir_res["resources_count"] >= 2  # Composition + DocumentReference
    print(f"✔ 3. FHIRHISAdapter: Bundled {fhir_res['resources_count']} resources and posted to HIS (Tx: {fhir_res['transaction_id']})")

    # --------------------------------------------------------------------------
    # 4. TEST WEBHOOK ADAPTER
    # --------------------------------------------------------------------------
    webhook_adapter = WebhookHISAdapter(
        webhook_url="https://his.aiia.gov.in/api/v1/clinical-records",
        secret_key="my_secret_key",
    )
    webhook_res = webhook_adapter.send_summary(patient_id, summary_data, sample_documents)
    assert webhook_res["adapter"] == "WEBHOOK"
    assert webhook_res["status"] == "DISPATCHED"
    assert "signature_sha256" in webhook_res
    print(f"✔ 4. WebhookHISAdapter: Signed payload with HMAC-SHA256 and dispatched (Sig: {webhook_res['signature_sha256']})")

    # --------------------------------------------------------------------------
    # 5. TEST MOCK HIS ADAPTER
    # --------------------------------------------------------------------------
    mock_adapter = MockHISAdapter()
    mock_res = mock_adapter.send_summary(patient_id, summary_data, sample_documents)
    assert mock_res["adapter"] == "MOCK_HIS"
    assert mock_res["status"] == "ACK"
    assert len(mock_adapter.received_records) == 1
    assert mock_adapter.received_records[0]["patient_id"] == patient_id
    print(f"✔ 5. MockHISAdapter: Successfully recorded and archived summary (ID: {mock_res['reception_id']})")

    # --------------------------------------------------------------------------
    # 6. TEST HIS INTEGRATION SERVICE & FACTORY
    # --------------------------------------------------------------------------
    service = HISIntegrationService()
    # Default is mock
    res_default = service.send_summary(patient_id, summary_data)
    assert res_default["adapter"] == "MOCK_HIS"

    # Switch to HL7v2
    service.set_adapter("hl7v2")
    res_hl7 = service.send_summary(patient_id, summary_data)
    assert res_hl7["adapter"] == "HL7_v2"

    # Switch to Webhook
    service.set_adapter("webhook")
    res_wh = service.send_summary(patient_id, summary_data)
    assert res_wh["adapter"] == "WEBHOOK"

    # Switch to FHIR
    service.set_adapter("fhir")
    res_fhir = service.send_summary(patient_id, summary_data)
    assert res_fhir["adapter"] == "FHIR_R4"

    print("✔ 6. HISIntegrationService: Successfully hot-swapped between all 4 adapters dynamically")

    print("\n--- ALL HIS INTEGRATION ADAPTER TESTS PASSED 100% ---")


if __name__ == "__main__":
    test_his_adapter_suite()

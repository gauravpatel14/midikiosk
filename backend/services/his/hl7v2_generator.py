"""HL7 v2 Message Generator for MediKiosk.

Generates standards-compliant HL7 v2.5 ER7 pipe-delimited messages
(ORU^R01 Observational Report) for integration with legacy hospital systems
(e.g., NIC e-Hospital, CDAC, MedSys, Allscripts).
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid


def generate_hl7v2_oru_r01(
    patient_id: str,
    summary: Dict[str, Any],
    documents: Optional[List[Dict[str, Any]]] = None,
    sending_app: str = "MEDIKIOSK",
    sending_facility: str = "AIIA_OPD",
    receiving_app: str = "HOSPITAL_HIS",
    receiving_facility: str = "CENTRAL_HOSPITAL",
) -> str:
    """Construct a complete HL7 v2.5 ORU^R01 message string.
    
    Segments included:
    - MSH: Message Header
    - PID: Patient Identification
    - PV1: Patient Visit
    - OBR: Observation Request (Clinical History Battery)
    - OBX: Multiple Observation segments for Chief Complaint, HPI, Summary, and Documents.
    """
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%d%H%M%S")
    msg_control_id = f"MSG{ts}{uuid.uuid4().hex[:6].upper()}"

    raw_demo = summary.get("patient") or summary.get("demographics")
    demo: Dict[str, Any] = raw_demo if isinstance(raw_demo, dict) else {}
    raw_name = str(demo.get("name") or "")
    parts = raw_name.split() if raw_name else []
    first_name = str(demo.get("first_name") or (parts[0] if parts else "Unknown"))
    last_name = str(demo.get("last_name") or (parts[-1] if len(parts) > 1 else ""))

    gender_val = str(demo.get("gender") or "").lower()
    gender_hl7 = "M" if gender_val.startswith("m") else ("F" if gender_val.startswith("f") else "U")
    dob = str(demo.get("date_of_birth") or "")
    dob_hl7 = dob.replace("-", "") if dob else ""
    phone = str(demo.get("phone") or demo.get("phone_number") or "")
    address = str(demo.get("address") or "Sector 12^^New Delhi^DL^110025^IND")

    segments = []

    # 1. MSH: Message Header
    msh = f"MSH|^~\\&|{sending_app}|{sending_facility}|{receiving_app}|{receiving_facility}|{ts}||ORU^R01^ORU_R01|{msg_control_id}|P|2.5"
    segments.append(msh)

    # 2. PID: Patient Identification
    pid = f"PID|1||{patient_id}^^^AIIA^MR||{last_name}^{first_name}^^^^^L||{dob_hl7}|{gender_hl7}|||{address}||{phone}"
    segments.append(pid)

    # 3. PV1: Patient Visit (Outpatient OPD)
    kiosk_id = str(summary.get("kiosk_id") or "KIOSK_01")
    pv1 = f"PV1|1|O|OPD^{kiosk_id}^^AIIA||||||||||||||||{msg_control_id[:10]}"
    segments.append(pv1)

    # 4. OBR: Observation Report
    obr_id = f"CLIN_HIST_{ts}"
    obr = f"OBR|1||{obr_id}|371530004^Clinical consultation report^SCT|||{ts}"
    segments.append(obr)

    # 5. OBX Segments: Observations
    obx_idx = 1

    # 5a. Chief Complaint
    cc = summary.get("chief_complaint")
    if isinstance(cc, dict):
        cc_text = cc.get("text", "None")
    else:
        cc_text = cc or "None"
    segments.append(f"OBX|{obx_idx}|TX|CHIEF_COMPLAINT^Chief Complaint||{_sanitize_hl7(str(cc_text))}||||||F")
    obx_idx += 1

    # 5b. HPI Details
    raw_hpi = summary.get("hpi")
    hpi: Dict[str, Any] = raw_hpi if isinstance(raw_hpi, dict) else {}
    hpi_summary = f"Duration: {hpi.get('duration', 'N/A')}, Character: {hpi.get('character', 'N/A')}, Severity: {hpi.get('severity', 'N/A')}"
    segments.append(f"OBX|{obx_idx}|TX|HPI^History of Present Illness||{_sanitize_hl7(hpi_summary)}||||||F")
    obx_idx += 1

    # 5c. Red Flag Status
    raw_rf = summary.get("red_flag")
    rf: Optional[Dict[str, Any]] = raw_rf if isinstance(raw_rf, dict) else None
    rf_text = f"RED_FLAG: {rf.get('category')} - {rf.get('rule')}" if rf else "NO_RED_FLAGS"
    segments.append(f"OBX|{obx_idx}|ST|RED_FLAG_ALERT^Triage Alert||{_sanitize_hl7(rf_text)}||||||F")
    obx_idx += 1

    # 5d. Clinical Summary Note (Plain text)
    summary_text = str(summary.get("plain_text_summary") or summary.get("text_summary") or "Summary not generated.")
    clean_summary = _sanitize_hl7(summary_text[:1500])
    segments.append(f"OBX|{obx_idx}|TX|CLINICAL_SUMMARY^Physician EMR Note||{clean_summary}||||||F")
    obx_idx += 1

    # 5e. Scanned Documents
    if documents:
        for doc in documents:
            if isinstance(doc, dict):
                doc_name = str(doc.get("filename") or "Scanned_Prescription.pdf")
                doc_type = str(doc.get("document_type_hint") or "PRESCRIPTION")
                segments.append(f"OBX|{obx_idx}|ED|DOCUMENT_REF^{doc_type}||PDF^{doc_name}||||||F")
                obx_idx += 1

    # HL7 segments joined with standard carriage return (\r)
    return "\r".join(segments) + "\r"


def _sanitize_hl7(text: str) -> str:
    """Escape HL7 delimiter characters (|, ^, ~, \\, &) to prevent format corruption."""
    return (
        text.replace("\\", "\\E\\")
        .replace("|", "\\F\\")
        .replace("^", "\\S\\")
        .replace("~", "\\R\\")
        .replace("&", "\\T\\")
        .replace("\r", " ")
        .replace("\n", " \\.br\\ ")
    )

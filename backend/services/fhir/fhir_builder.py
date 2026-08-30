"""HL7 FHIR R4 Resource Builder for ABDM (Ayushman Bharat Digital Mission).

Generates standard ABDM NRCeS-compliant FHIR R4 resources:
- Patient: https://nrces.in/ndhm/fhir/r4/StructureDefinition/Patient
- DocumentReference: https://nrces.in/ndhm/fhir/r4/StructureDefinition/DocumentReference
- Composition (OPConsult): https://nrces.in/ndhm/fhir/r4/StructureDefinition/OPConsultRecord
- Consent: https://nrces.in/ndhm/fhir/r4/StructureDefinition/Consent
"""

import base64
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def create_patient_resource(patient_data: Dict[str, Any]) -> Dict[str, Any]:
    """Build ABDM-compliant FHIR R4 Patient resource.
    
    Args:
        patient_data: Dictionary containing demographics, ABHA ID, name, gender, phone.
        
    Returns:
        FHIR R4 Patient resource dictionary.
    """
    patient_id = str(patient_data.get("id") or patient_data.get("patient_id") or uuid.uuid4())
    demo = patient_data.get("demographics", patient_data)
    first_name = demo.get("first_name", "Unknown")
    last_name = demo.get("last_name", "")
    full_name = f"{first_name} {last_name}".strip()
    
    gender_map = {"male": "male", "female": "female", "other": "other"}
    raw_gender = str(demo.get("gender", "male")).lower()
    gender = gender_map.get(raw_gender, "unknown")

    identifiers = []
    # 1. ABHA Number
    if demo.get("abha_id"):
        identifiers.append({
            "type": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                    "code": "MR",
                    "display": "Medical Record Number",
                }]
            },
            "system": "https://healthid.ndhm.gov.in",
            "value": demo.get("abha_id"),
        })
    # 2. ABHA Address / PHR
    if demo.get("abha_address"):
        identifiers.append({
            "system": "https://ndhm.in/phr",
            "value": demo.get("abha_address"),
        })

    resource = {
        "resourceType": "Patient",
        "id": patient_id,
        "meta": {
            "versionId": "1",
            "lastUpdated": datetime.now(timezone.utc).isoformat(),
            "profile": ["https://nrces.in/ndhm/fhir/r4/StructureDefinition/Patient"],
        },
        "text": {
            "status": "generated",
            "div": f'<div xmlns="http://www.w3.org/1999/xhtml">{full_name}, {gender}, Age: {demo.get("age", "--")}</div>',
        },
        "identifier": identifiers,
        "name": [{
            "use": "official",
            "text": full_name,
            "family": last_name,
            "given": [first_name],
        }],
        "gender": gender,
    }

    if demo.get("date_of_birth"):
        resource["birthDate"] = str(demo.get("date_of_birth"))

    if demo.get("phone_number") or demo.get("phone"):
        resource["telecom"] = [{
            "system": "phone",
            "value": demo.get("phone_number") or demo.get("phone"),
            "use": "mobile",
        }]

    if demo.get("address_line") or demo.get("district") or demo.get("state"):
        resource["address"] = [{
            "use": "home",
            "line": [demo.get("address_line")] if demo.get("address_line") else [],
            "city": demo.get("district", ""),
            "state": demo.get("state", ""),
            "postalCode": demo.get("pincode", ""),
            "country": "IND",
        }]

    return resource


def create_document_reference(
    document_metadata: Dict[str, Any], file_location: Optional[str] = None
) -> Dict[str, Any]:
    """Build ABDM-compliant FHIR R4 DocumentReference resource for scanned prescriptions/reports.
    
    Args:
        document_metadata: Metadata dict (document_type, filename, language, mime_type, etc.)
        file_location: Local filesystem path to attachment (encoded as base64 or URL).
        
    Returns:
        FHIR R4 DocumentReference resource dictionary.
    """
    doc_id = str(document_metadata.get("id", uuid.uuid4()))
    doc_type = document_metadata.get("document_type_hint", "PRESCRIPTION").upper()

    # LOINC Codes for document classification
    type_coding = {
        "PRESCRIPTION": {"code": "57833-6", "display": "Prescription for medication"},
        "LAB_REPORT": {"code": "11502-2", "display": "Laboratory report"},
        "DISCHARGE_SUMMARY": {"code": "18842-5", "display": "Discharge summary"},
    }.get(doc_type, {"code": "34108-1", "display": "Outpatient Note"})

    # Read binary content if file exists
    attachment = {
        "contentType": document_metadata.get("mime_type", "application/pdf"),
        "language": document_metadata.get("primary_language", "en"),
        "title": document_metadata.get("filename", "Clinical Document Scan"),
        "creation": datetime.now(timezone.utc).isoformat(),
    }

    if file_location and os.path.exists(file_location):
        try:
            with open(file_location, "rb") as f:
                b64_content = base64.b64encode(f.read()).decode("utf-8")
                attachment["data"] = b64_content
                attachment["size"] = os.path.getsize(file_location)
        except Exception:
            attachment["url"] = f"file://{file_location}"
    else:
        attachment["url"] = file_location or f"urn:uuid:{doc_id}"

    patient_ref = f"Patient/{document_metadata.get('patient_id', 'unknown')}"

    return {
        "resourceType": "DocumentReference",
        "id": doc_id,
        "meta": {
            "versionId": "1",
            "lastUpdated": datetime.now(timezone.utc).isoformat(),
            "profile": ["https://nrces.in/ndhm/fhir/r4/StructureDefinition/DocumentReference"],
        },
        "status": "current",
        "docStatus": "final",
        "type": {
            "coding": [{
                "system": "http://loinc.org",
                "code": type_coding["code"],
                "display": type_coding["display"],
            }]
        },
        "subject": {"reference": patient_ref},
        "date": datetime.now(timezone.utc).isoformat(),
        "content": [{"attachment": attachment}],
    }


def create_composition(
    history_data: Dict[str, Any], summary_text: str
) -> Dict[str, Any]:
    """Build ABDM-compliant FHIR R4 Composition resource for OPD Clinical History.
    
    Args:
        history_data: Extracted clinical history (Chief complaint, HPI, PMH, ROS, etc.).
        summary_text: Rendered plain text or HTML summary.
        
    Returns:
        FHIR R4 Composition resource dictionary.
    """
    comp_id = str(history_data.get("session_id", uuid.uuid4()))
    patient_ref = f"Patient/{history_data.get('patient_id', 'unknown')}"
    timestamp = datetime.now(timezone.utc).isoformat()

    sections = [
        {
            "title": "Chief Complaint",
            "code": {"coding": [{"system": "http://snomed.info/sct", "code": "422843007", "display": "Chief complaint"}]},
            "text": {"status": "generated", "div": f'<div xmlns="http://www.w3.org/1999/xhtml">{history_data.get("chief_complaint", "Not recorded")}</div>'},
        },
        {
            "title": "History of Present Illness",
            "code": {"coding": [{"system": "http://snomed.info/sct", "code": "102835002", "display": "History of present illness"}]},
            "text": {"status": "generated", "div": f'<div xmlns="http://www.w3.org/1999/xhtml">{history_data.get("hpi", {}).get("HPI_DURATION", "Recent onset")}</div>'},
        },
        {
            "title": "MediKiosk Clinical Summary",
            "code": {"coding": [{"system": "http://snomed.info/sct", "code": "371530004", "display": "Clinical consultation report"}]},
            "text": {"status": "generated", "div": f'<div xmlns="http://www.w3.org/1999/xhtml"><pre>{summary_text[:1200]}</pre></div>'},
        },
    ]

    return {
        "resourceType": "Composition",
        "id": comp_id,
        "meta": {
            "versionId": "1",
            "lastUpdated": timestamp,
            "profile": ["https://nrces.in/ndhm/fhir/r4/StructureDefinition/OPConsultRecord"],
        },
        "status": "final",
        "type": {
            "coding": [{
                "system": "http://snomed.info/sct",
                "code": "371530004",
                "display": "Clinical consultation report",
            }]
        },
        "subject": {"reference": patient_ref},
        "date": timestamp,
        "author": [{
            "display": "MediKiosk Multimodal Intake Terminal - All India Institute of Ayurveda",
        }],
        "title": "OPD Clinical Consultation & Auto-History Summary",
        "section": sections,
    }


def create_consent_resource(consent_data: Dict[str, Any]) -> Dict[str, Any]:
    """Build ABDM-compliant FHIR R4 Consent resource adhering to DPDP Act 2023.
    
    Args:
        consent_data: Consent record dictionary containing patient_id, tamper_proof_hash, grants.
        
    Returns:
        FHIR R4 Consent resource dictionary.
    """
    consent_id = str(consent_data.get("consent_id") or consent_data.get("id") or uuid.uuid4())
    patient_ref = f"Patient/{consent_data.get('patient_id', 'unknown')}"
    timestamp = consent_data.get("granted_at", datetime.now(timezone.utc).isoformat())

    return {
        "resourceType": "Consent",
        "id": consent_id,
        "meta": {
            "versionId": "1",
            "lastUpdated": str(timestamp),
            "profile": ["https://nrces.in/ndhm/fhir/r4/StructureDefinition/Consent"],
        },
        "status": "active" if not consent_data.get("is_revoked", False) else "rejected",
        "scope": {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/consentscope",
                "code": "patient-privacy",
                "display": "Privacy Consent",
            }]
        },
        "category": [{
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                "code": "59284-0",
                "display": "Consent Document",
            }]
        }],
        "patient": {"reference": patient_ref},
        "dateTime": str(timestamp),
        "policy": [{
            "authority": "https://abdm.gov.in/policies",
            "uri": "https://abdm.gov.in/consent-policy-dpdp-act-2023",
        }],
        "policyRule": {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/consentpolicycodes",
                "code": "cric",
                "display": "Common Rule Informed Consent",
            }]
        },
        "provision": {
            "type": "permit",
            "period": {
                "start": str(timestamp),
            },
            "data": [{
                "meaning": "dependents",
                "reference": {"display": f"TamperProofHash:{consent_data.get('tamper_proof_hash', 'unhashed')}"},
            }],
        },
    }


def create_fhir_bundle(
    resources: List[Dict[str, Any]], bundle_type: str = "document"
) -> Dict[str, Any]:
    """Assemble individual FHIR resources into a valid FHIR R4 Bundle."""
    bundle_id = str(uuid.uuid4())
    entries = []

    for res in resources:
        res_type = res.get("resourceType")
        res_id = res.get("id")
        entries.append({
            "fullUrl": f"urn:uuid:{res_id}",
            "resource": res,
        })

    return {
        "resourceType": "Bundle",
        "id": bundle_id,
        "meta": {
            "versionId": "1",
            "lastUpdated": datetime.now(timezone.utc).isoformat(),
            "profile": ["https://nrces.in/ndhm/fhir/r4/StructureDefinition/DocumentBundle"],
        },
        "identifier": {
            "system": "https://aiia.gov.in/bundles",
            "value": bundle_id,
        },
        "type": bundle_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "entry": entries,
    }

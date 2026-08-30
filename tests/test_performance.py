"""Performance and Latency Benchmark Test Suite for MediKiosk Production Endpoints.

Note: Realistic test data used (10-turn dialogue state progression, 5-page bilingual
PDF with real prescription & lab report text, and comprehensive multi-section patient history).

Evaluates production SLA thresholds:
1. /dialogue/next < 500 ms (Real 10-turn dialogue history state machine progression)
2. /documents/ocr/scan < 10.0 seconds (Realistic 5-page English/Hindi multi-page medical PDF)
3. /summary/generate < 15.0 seconds (Full clinical compilation with drug interactions & AYUSH safety)

Run benchmarks:
    .venv/bin/python -m pytest tests/test_performance.py -v
Skip benchmarks:
    SKIP_PERFORMANCE_TESTS=1 .venv/bin/python -m pytest tests/test_performance.py
"""

import os
import sys
import tempfile
import time
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

# Add root and backend to path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
for p in [str(root_dir), str(backend_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.main import app

client = TestClient(app)


def _check_skip():
    if os.getenv("SKIP_PERFORMANCE_TESTS") == "1":
        pytest.skip("Skipping performance benchmarks because SKIP_PERFORMANCE_TESTS=1")


@pytest.mark.performance
def test_benchmark_dialogue_next_latency():
    """Benchmark /dialogue/next: Must respond in under 500ms across 10 realistic dialogue turns."""
    _check_skip()

    session_id = str(uuid.uuid4())
    init_res = client.post("/dialogue/start", json={"session_id": session_id, "language": "hi", "mode": "ALLOPATHIC"})
    assert init_res.status_code == 200

    # 10 realistic turns with speech transcripts and state progression
    realistic_turns = [
        {"state": "CHIEF_COMPLAINT", "response": "मुझे पिछले तीन दिनों से सीने में दर्द और भारीपन महसूस हो रहा है"},
        {"state": "HPI_DURATION", "response": "3 days"},
        {"state": "HPI_SOCRATES_SITE", "response": "Retrosternal chest, middle of the chest"},
        {"state": "HPI_SOCRATES_ONSET", "response": "Sudden onset while walking upstairs"},
        {"state": "HPI_SOCRATES_CHARACTER", "response": "Heavy compressive tightness and squeezing"},
        {"state": "HPI_SOCRATES_RADIATION", "response": "Radiating to left shoulder and jaw"},
        {"state": "HPI_SOCRATES_ASSOCIATIONS", "response": "Associated with mild breathlessness and cold sweat"},
        {"state": "HPI_SOCRATES_TIMING", "response": "Constant dull ache with acute spikes"},
        {"state": "HPI_SOCRATES_EXACERBATING", "response": "Worse on exertion, slightly relieved by sitting still"},
        {"state": "HPI_SOCRATES_SEVERITY", "response": "7 out of 10 on pain scale"},
    ]

    latencies = []
    current_state = "CHIEF_COMPLAINT"

    for turn in realistic_turns:
        payload = {
            "session_id": session_id,
            "current_state": turn["state"],
            "user_response": turn["response"],
        }
        start = time.perf_counter()
        res = client.post("/dialogue/next", json=payload)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        assert res.status_code == 200
        latencies.append(elapsed_ms)
        current_state = res.json().get("next_state", current_state)

    avg_latency = sum(latencies) / len(latencies)
    max_latency = max(latencies)
    print(f"\n[PERF] /dialogue/next across 10 turns - Avg: {avg_latency:.2f} ms, Max: {max_latency:.2f} ms (Target < 500 ms)")
    assert avg_latency < 500.0, f"/dialogue/next average exceeded 500ms SLA (Measured: {avg_latency:.2f} ms)"


@pytest.mark.performance
def test_benchmark_ocr_scan_latency():
    """Benchmark /documents/ocr/scan: Realistic 5-page bilingual clinical PDF processed in under 10.0 seconds."""
    _check_skip()

    # Generate a realistic 5-page clinical record PDF (Prescriptions, Lab Reports, Discharge Summary)
    pages = []
    page_contents = [
        # Page 1: OPD Prescription (English & Hindi)
        [
            "ALL INDIA INSTITUTE OF AYURVEDA (AIIA) - OPD CARD",
            "OPD Reg: AIIA-2026-98124 | Date: 18-08-2026",
            "Patient: Rameshwar Prasad Sharma | Age: 56 | Gender: M",
            "Chief Complaint: छाती में भारीपन और सांस फूलना (Chest heaviness)",
            "Diagnosis: Essential Hypertension (ICD-10: I10), Type 2 Diabetes",
            "Rx:",
            "1. Tab. Telmisartan 40 mg - 1 Tab OD morning after breakfast",
            "2. Tab. Metformin 500 mg - 1 Tab BD after meals",
            "3. Tab. Pantoprazole 40 mg - 1 Tab OD empty stomach",
        ],
        # Page 2: Complete Blood Count (CBC) Laboratory Report
        [
            "CENTRAL CLINICAL PATHOLOGY LABORATORY - REPORT",
            "Specimen: Whole Blood EDTA | Collected: 18-08-2026 08:30",
            "INVESTIGATION                     RESULT       REFERENCE RANGE",
            "Hemoglobin (Hb)                  14.2 g/dL     13.0 - 17.0 g/dL",
            "Total Leukocyte Count (WBC)      7,800 /cumm   4,000 - 11,000",
            "Platelet Count                   240,000 /cumm 150,000 - 450,000",
            "RBC Count                        4.8 mill/cumm 4.5 - 5.5",
            "Packed Cell Volume (PCV)         42.5 %        40.0 - 50.0",
        ],
        # Page 3: Biochemistry & Renal Function Test (KFT)
        [
            "BIOCHEMISTRY & RENAL FUNCTION PANEL",
            "Patient: Rameshwar Sharma | Verified by: Dr. Ananya Sen, MD",
            "Fasting Blood Glucose            142 mg/dL     70 - 100 [HIGH]",
            "Post-Prandial Glucose            198 mg/dL     < 140 [HIGH]",
            "HbA1c (Glycated Hemoglobin)      7.4 %         < 5.7 [POOR CONTROL]",
            "Serum Creatinine                 1.1 mg/dL     0.7 - 1.3",
            "Blood Urea Nitrogen (BUN)        18 mg/dL      7 - 20",
            "Serum Uric Acid                  5.6 mg/dL     3.5 - 7.2",
        ],
        # Page 4: Ayurvedic Clinical Assessment & Formulations
        [
            "DEPARTMENT OF KAYACHIKITSA - AYUSH INTEGRATED OPD",
            "Dashavidha Pariksha Summary: Vata-Pitta Prakriti, Madhyama Sara",
            "Agni: Vishamagni | Koshtha: Krura Koshtha | Vaya: Madhyama",
            "Rasa Shastra & Herbo-mineral Formulations Prescribed:",
            "1. Arogyavardhini Vati - 250 mg BD with Lukewarm Water",
            "2. Prabhakar Vati - 125 mg BD with Arjunarishta 20ml",
            "3. Punarnavadi Kashayam - 15 ml BD before meals",
            "Note: Monitor BP and serum creatinine weekly.",
        ],
        # Page 5: Clinical Instructions & Follow-Up Advice
        [
            "PATIENT DISCHARGE & LIFESTYLE ADVICE (पथ्यापथ्य निर्देश)",
            "1. Avoid excessive salt, oily, and pungent (katu) foods.",
            "2. Daily brisk walking 30 minutes in morning.",
            "3. नियमित रूप से रक्तचाप की जांच कराएं (Check BP regularly).",
            "4. यदि सीने में दर्द बढ़े तो तुरंत आपातकालीन कक्ष (ER) जाएं।",
            "Next Follow-Up Visit: 01-September-2026",
            "Consultant: Dr. V. K. Joshi, MD, PhD (Kayachikitsa)",
        ],
    ]

    import pymupdf

    doc = pymupdf.open()
    for p_lines in page_contents:
        page = doc.new_page(width=595, height=842)
        y = 72
        for line in p_lines:
            page.insert_text((50, y), line, fontsize=12)
            y += 24

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        doc.save(f.name)
        pdf_path = f.name

    try:
        start = time.perf_counter()
        with open(pdf_path, "rb") as f:
            res = client.post("/documents/ocr/scan", files={"file": ("clinical_dossier.pdf", f, "application/pdf")})
        elapsed_sec = time.perf_counter() - start

        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["page_count"] == 5

        print(f"\n[PERF] /documents/ocr/scan 5-page PDF total elapsed time: {elapsed_sec:.2f} s (Target < 10.0 s)")
        assert elapsed_sec < 10.0, f"5-page OCR scan exceeded 10.0s SLA (Measured: {elapsed_sec:.2f} s)"
    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)


@pytest.mark.performance
def test_benchmark_summary_generate_latency():
    """Benchmark /summary/generate: Multi-section Jinja2 + interaction + AYUSH safety check in under 15 seconds."""
    _check_skip()

    # Complete realistic patient history dossier
    payload = {
        "patient_data": {
            "demographics": {
                "first_name": "Rameshwar",
                "last_name": "Sharma",
                "age": 56,
                "gender": "Male",
                "abha_id": "91-4920-8319-1024",
                "phone_number": "9876543210",
                "preferred_language": "Hindi",
            },
            "chief_complaint": "Retrosternal chest tightness and exertional dyspnea for 3 days",
            "hpi": {
                "HPI_DURATION": "3 days",
                "HPI_SOCRATES_CHARACTER": "Heavy compressive pressure",
                "HPI_SOCRATES_RADIATION": "Spreading to left shoulder and jaw",
                "HPI_SOCRATES_ASSOCIATIONS": "Mild diaphoresis and nausea",
                "HPI_SOCRATES_SEVERITY": "7",
            },
            "past_medical": ["Essential Hypertension", "Type 2 Diabetes Mellitus", "Dyslipidemia"],
            "medications": [
                {"name": "Tab. Telmisartan", "dosage": "40mg", "frequency": "OD", "duration": "Daily"},
                {"name": "Tab. Metformin", "dosage": "500mg", "frequency": "BD", "duration": "Daily"},
                {"name": "Tab. Aspirin", "dosage": "75mg", "frequency": "OD", "duration": "Daily"},
                {"name": "Tab. Warfarin", "dosage": "2mg", "frequency": "OD", "duration": "Daily"},
            ],
            "allergies": ["Penicillin", "Sulfa drugs"],
            "family_history": ["Father: Coronary artery disease at 60", "Mother: Type 2 Diabetes"],
            "personal_history": ["Vegetarian diet, non-smoker, sedentary lifestyle"],
            "review_of_systems": ["Cardiovascular: Chest tightness", "Respiratory: Exertional dyspnea"],
            "is_ayush": True,
            "ayush_assessments": {
                "AYUSH_PRAKRITI": "Vata-Pitta Prakriti",
                "AYUSH_VIKRITI": "Vata Vriddhi with Pitta Anubandha",
                "AYUSH_SARA": "Madhyama Sara",
                "AYUSH_SAMHANANA": "Madhyama Samhanana",
                "AYUSH_AGNI_KOSHTHA": "Vishamagni with Krura Koshtha",
                "AYUSH_SATTVA": "Pravara Sattva",
            },
        },
        "document_data": {
            "entities": {
                "laboratory_results": [
                    {"test_name": "Fasting Blood Sugar", "value": "142", "unit": "mg/dL", "reference_range": "70-100", "interpretation": "High"},
                    {"test_name": "HbA1c", "value": "7.4", "unit": "%", "reference_range": "< 5.7", "interpretation": "High"},
                    {"test_name": "Hemoglobin", "value": "14.2", "unit": "g/dL", "reference_range": "13.0-17.0", "interpretation": "Normal"},
                    {"test_name": "Serum Creatinine", "value": "1.1", "unit": "mg/dL", "reference_range": "0.7-1.3", "interpretation": "Normal"},
                ],
                "medications": [
                    {"name": "Arogyavardhini Vati", "dosage": "250mg", "frequency": "BD", "duration": "15 days"},
                    {"name": "Prabhakar Vati", "dosage": "125mg", "frequency": "BD", "duration": "30 days"},
                ],
            },
            "documents": [
                {"filename": "prescription_2026_08_18.pdf", "detected_document_date": "2026-08-18", "document_type": "PRESCRIPTION"},
                {"filename": "cbc_report_2026_08_19.pdf", "detected_document_date": "2026-08-19", "document_type": "LAB_REPORT"},
            ]
        },
    }

    start = time.perf_counter()
    res = client.post("/summary/generate", json=payload)
    elapsed_sec = time.perf_counter() - start

    assert res.status_code == 200
    data = res.json()
    assert "MEDIKIOSK CLINICAL HISTORY SUMMARY" in data["plain_text_summary"]
    assert "Potential Drug Interactions" in data["html_summary"]
    assert "AYUSH Safety Alerts" in data["html_summary"] or "AYUSH Formulation" in data["html_summary"]
    assert "Medical Document Timeline" in data["html_summary"]

    print(f"\n[PERF] /summary/generate comprehensive compilation: {elapsed_sec:.2f} s (Target < 15.0 s)")
    assert elapsed_sec < 15.0, f"Summary compilation exceeded 15.0s SLA (Measured: {elapsed_sec:.2f} s)"


if __name__ == "__main__":
    test_benchmark_dialogue_next_latency()
    test_benchmark_ocr_scan_latency()
    test_benchmark_summary_generate_latency()

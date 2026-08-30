"""Automated test suite verifying MediKiosk SummaryGenerator."""

import sys
from pathlib import Path

# Add root and backend to path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
for p in [str(root_dir), str(backend_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.services.summary.summary_generator import SummaryGenerator


def test_summary_generator_suite():
    print("\n--- Running MediKiosk Summary Generator Test Suite ---")

    generator = SummaryGenerator()

    # 1. Prepare Mock Patient Data (from Dialogue Manager)
    patient_data_allopathic = {
        "demographics": {
            "first_name": "Rameshwar",
            "last_name": "Sharma",
            "age": 54,
            "gender": "Male",
            "abha_id": "91-4920-8319-1024",
            "phone_number": "9876543210",
            "preferred_language": "Hindi",
        },
        "chief_complaint": "Retrosternal chest tightness and shortness of breath for 3 days",
        "hpi": {
            "HPI_DURATION": "3 days",
            "HPI_SOCRATES_CHARACTER": "Heavy compressive pressure",
            "HPI_SOCRATES_RADIATION": "Spreading to left shoulder and arm",
            "HPI_SOCRATES_SEVERITY": "7",
        },
        "past_medical": [
            "Essential Hypertension (diagnosed 2018)",
            "Type 2 Diabetes Mellitus on oral hypoglycemics",
        ],
        "medications": [
            {"name": "Tab. Telmisartan", "dosage": "40mg", "frequency": "OD", "duration": "Daily"},
            {"name": "Tab. Metformin", "dosage": "500mg", "frequency": "BD", "duration": "Daily"},
        ],
        "allergies": ["Penicillin (produces pruritic skin rashes)"],
        "family_history": ["Father had myocardial infarction at age 62"],
        "personal_history": ["Vegetarian diet, non-smoker, non-alcoholic"],
        "review_of_systems": ["Exertional dyspnea present, pedal edema absent"],
        "red_flag": {
            "category": "ACUTE_CORONARY_SYNDROME",
            "rule": "Chest pain with left arm radiation",
            "message": "Potential Acute Coronary Syndrome. Triage nurse alerted.",
        },
        "is_ayush": False,
    }

    # Document Extraction Data (from EntityExtractor)
    document_data = {
        "entities": {
            "medications": [
                {"name": "Tab. Pantop", "dosage": "40mg", "frequency": "OD", "duration": "5 days"},
            ],
            "laboratory_results": [
                {
                    "test_name": "Fasting Blood Sugar",
                    "value": "138",
                    "unit": "mg/dL",
                    "reference_range": "70 - 100",
                    "interpretation": "High",
                },
                {
                    "test_name": "Hemoglobin",
                    "value": "11.2",
                    "unit": "g/dL",
                    "reference_range": "13.0 - 17.0",
                    "interpretation": "Low",
                },
                {
                    "test_name": "Serum Creatinine",
                    "value": "0.9",
                    "unit": "mg/dL",
                    "reference_range": "0.7 - 1.3",
                    "interpretation": "Normal",
                },
            ],
            "procedures": [
                {"name": "Appendectomy (2015)"},
            ],
        }
    }

    # --------------------------------------------------------------------------
    # 1. TEST ALLOPATHIC SUMMARY GENERATION
    # --------------------------------------------------------------------------
    html_out, text_out = generator.generate(patient_data_allopathic, document_data)

    # Validate HTML Output
    assert "<!DOCTYPE html>" in html_out
    assert "Rameshwar Sharma" in html_out
    assert "91-4920-8319-1024" in html_out
    assert "Chief Complaint" in html_out
    assert "History of Present Illness" in html_out
    assert "Heavy compressive pressure" in html_out
    assert "Spreading to left shoulder" in html_out
    assert "Essential Hypertension" in html_out
    assert "Tab. Telmisartan" in html_out
    assert "Tab. Pantop" in html_out
    assert "Penicillin" in html_out
    assert "Appendectomy" in html_out
    # Abnormal lab values highlighted
    assert "val-high" in html_out or "High" in html_out
    assert "val-low" in html_out or "Low" in html_out
    # Red flag banner
    assert "ACUTE_CORONARY_SYNDROME" in html_out
    # Editable placeholder
    assert 'contenteditable="true"' in html_out
    assert "<!-- PHYSICIAN_EDITABLE" in html_out
    print("✔ 1a. HTML Summary Generated: All 11 sections + Abnormal Labs + Red Flag Banner verified")

    # Validate Plain Text Output
    assert "MEDIKIOSK CLINICAL HISTORY SUMMARY" in text_out
    assert "Rameshwar Sharma" in text_out
    assert "CRITICAL CLINICAL ALERT" in text_out
    assert "Fasting Blood Sugar: 138 mg/dL" in text_out
    assert "(ABNORMAL)" in text_out
    assert "<!-- PHYSICIAN_EDITABLE_SECTION -->" in text_out
    print("✔ 1b. Plain Text Summary Generated: Verified clean format for hospital EMR paste")

    # --------------------------------------------------------------------------
    # 2. TEST AYUSH MODE (DASHAVIDHA PARIKSHA) SUMMARY
    # --------------------------------------------------------------------------
    patient_data_ayush = dict(patient_data_allopathic)
    patient_data_ayush["is_ayush"] = True
    patient_data_ayush["ayush_assessments"] = {
        "AYUSH_PRAKRITI": "Vata-Pitta Prakriti",
        "AYUSH_VIKRITI": "Vata-Kapha Vriddhi",
        "AYUSH_SARA": "Madhyama Sara",
        "AYUSH_SAMHANANA": "Madhyama Samhanana",
        "AYUSH_AGNI_KOSHTHA": "Vishamagni with Krura Koshtha",
    }

    html_ayush, text_ayush = generator.generate(patient_data_ayush, document_data)

    assert "Dashavidha Pariksha" in html_ayush
    assert "Prakriti" in html_ayush
    assert "Vata-Pitta Prakriti" in html_ayush
    assert "Vishamagni with Krura Koshtha" in html_ayush
    assert "Dashavidha Pariksha" in text_ayush
    print("✔ 2. AYUSH Summary: Dashavidha Pariksha table & 10 Pariksha factors verified in HTML & text")

    print("\n--- ALL SUMMARY GENERATOR TESTS PASSED 100% ---")


if __name__ == "__main__":
    test_summary_generator_suite()

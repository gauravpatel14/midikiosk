"""Automated test suite verifying MediKiosk Clinical Entity Extraction."""

import sys
from pathlib import Path

# Add root and backend to path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
for p in [str(root_dir), str(backend_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.services.extraction.entity_extractor import EntityExtractor


def test_clinical_entity_extraction_suite():
    print("\n--- Running MediKiosk Clinical Entity Extraction Test Suite ---")

    # Sample realistic hospital OPD discharge / prescription text
    clinical_doc_text = """
    ALL INDIA INSTITUTE OF AYURVEDA - HOSPITAL OPD
    Date of Consultation: 14-08-2026
    Patient: Rameshwar Sharma, 54/M
    
    CLINICAL DIAGNOSIS:
    Patient evaluated for Essential Hypertension and Type 2 Diabetes Mellitus with mild Bronchial Asthma.
    
    MEDICATIONS PRESCRIBED:
    1. Tab. Pantop 40mg OD x 5 days
    2. Tab. Telmisartan 40mg OD
    3. Cap. Amoxicillin 500mg TDS x 7 days
    4. Syp. Bresol 10ml BD
    
    LABORATORY INVESTIGATIONS:
    Hemoglobin: 13.8 g/dL (Normal 12.0 - 16.0)
    Fasting Blood Glucose: 118 mg/dL (Normal 70 - 100)
    Platelets: 2.4 Lakh (Normal 1.5 - 4.5)
    
    PAST SURGICAL HISTORY:
    Underwent Appendectomy in 2018 without complications.
    
    KNOWN ALLERGIES:
    Allergies: Penicillin allergy noted (manifests as urticarial rash).
    """

    # 1. Test Pure Regex Rule-Based Extraction (Offline Fallback)
    regex_extractor = EntityExtractor(use_llm_if_available=False)
    res_regex = regex_extractor.extract(clinical_doc_text)

    assert res_regex["status"] == "success"
    assert res_regex["extraction_method"] == "regex_rule_engine"
    entities = res_regex["entities"]

    # 1a. Diagnoses with ICD-10
    diags = entities["diagnoses"]
    assert len(diags) >= 2, f"Expected >=2 diagnoses, got {len(diags)}"
    diag_codes = {d.get("icd10_code") for d in diags}
    assert "I10" in diag_codes or "E11.9" in diag_codes
    print(f"✔ 1a. Diagnoses Extracted ({len(diags)}): {[d['name'] + ' (' + str(d.get('icd10_code')) + ')' for d in diags]}")

    # 1b. Medications
    meds = entities["medications"]
    assert len(meds) >= 2, f"Expected >=2 medications, got {len(meds)}"
    med_names = [m["name"] for m in meds]
    print(f"✔ 1b. Medications Extracted ({len(meds)}): {[m['name'] + ' ' + m['dosage'] + ' ' + m['frequency'] for m in meds]}")

    # 1c. Laboratory Results
    labs = entities["laboratory_results"]
    assert len(labs) >= 1, f"Expected >=1 lab results, got {len(labs)}"
    hb_lab = next((l for l in labs if "Hemoglobin" in l["test_name"]), None)
    assert hb_lab is not None
    assert hb_lab["value"] == "13.8"
    assert hb_lab["unit"] == "g/dL"
    print(f"✔ 1c. Lab Results Extracted ({len(labs)}): {[l['test_name'] + ': ' + l['value'] + ' ' + str(l.get('unit')) for l in labs]}")

    # 1d. Procedures / Surgeries
    procs = entities["procedures"]
    assert len(procs) >= 1, f"Expected >=1 procedures, got {len(procs)}"
    assert any("Appendectomy" in p["name"] for p in procs)
    print(f"✔ 1d. Procedures Extracted ({len(procs)}): {[p['name'] for p in procs]}")

    # 1e. Allergies
    allergies = entities["allergies"]
    assert len(allergies) >= 1, f"Expected >=1 allergies, got {len(allergies)}"
    assert any("Penicillin" in a["allergen"] for a in allergies)
    print(f"✔ 1e. Allergies Extracted ({len(allergies)}): {[a['allergen'] for a in allergies]}")

    # 1f. Dates
    dates = entities["dates"]
    assert len(dates) >= 1, f"Expected >=1 dates, got {len(dates)}"
    assert any("14-08-2026" in d["date_string"] for d in dates)
    print(f"✔ 1f. Dates Extracted ({len(dates)}): {[d['date_string'] for d in dates]}")

    # 1g. Confidence Scores
    assert res_regex["overall_confidence"] > 0.70
    print(f"✔ 1g. Overall Confidence Score: {res_regex['overall_confidence']}")

    # 2. Test LLM-Augmented Extraction (using gpt-4o-mini if client initialized)
    llm_extractor = EntityExtractor(use_llm_if_available=True)
    res_llm = llm_extractor.extract(clinical_doc_text)
    assert res_llm["status"] == "success"
    print(f"✔ 2. LLM Engine Mode: {res_llm['extraction_method']} (Overall Confidence: {res_llm['overall_confidence']})")

    # 3. Empty input handling
    res_empty = regex_extractor.extract("")
    assert res_empty["status"] == "empty"
    assert len(res_empty["entities"]["diagnoses"]) == 0
    print("✔ 3. Empty input gracefully handled.")

    print("\n--- ALL CLINICAL ENTITY EXTRACTION TESTS PASSED 100% ---")


if __name__ == "__main__":
    test_clinical_entity_extraction_suite()

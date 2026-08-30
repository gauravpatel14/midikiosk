"""Rule-Based and Regular Expression Clinical Entity Extractor for MediKiosk.

Extracts diagnoses, medications, laboratory results, procedures, allergies,
and dates from unstructured medical OCR transcripts with ICD-10 mapping.
"""

import re
from typing import Any, Dict, List, Optional

try:
    from services.extraction.icd10_map import ICD10_DATABASE, lookup_icd10
except ImportError:
    from .icd10_map import ICD10_DATABASE, lookup_icd10


class RegexClinicalExtractor:
    """Zero-dependency, high-precision regex clinical entity extractor."""

    # --------------------------------------------------------------------------
    # 1. DIAGNOSES EXTRACTION
    # --------------------------------------------------------------------------
    def extract_diagnoses(self, text: str) -> List[Dict[str, Any]]:
        results = []
        lower = text.lower()

        for term in ICD10_DATABASE:
            # Word boundary regex to prevent partial word collisions
            pattern = rf"\b{re.escape(term)}\b"
            if re.search(pattern, lower):
                icd = lookup_icd10(term)
                results.append({
                    "name": term.title(),
                    "icd10_code": icd["code"] if icd else "R69",
                    "icd10_title": icd["title"] if icd else "Illness, unspecified",
                    "confidence": 0.88,
                })
        return results

    # --------------------------------------------------------------------------
    # 2. MEDICATIONS EXTRACTION
    # --------------------------------------------------------------------------
    def extract_medications(self, text: str) -> List[Dict[str, Any]]:
        results = []
        # Match prescription patterns: (Form) (Name) (Dose) (Frequency) (Duration)
        # e.g. "Tab. Pantop 40mg OD x 5 days", "Cap Amoxicillin 500 mg TDS", "Paracetamol 650mg BD"
        med_pattern = re.compile(
            r"(?:(?P<form>Tab\.?|Cap\.?|Syp\.?|Inj\.?|Oint\.?)\s+)?"
            r"(?P<name>[A-Z][a-zA-Z]{2,20}(?:\s+[A-Z][a-zA-Z]{2,15})?)\s+"
            r"(?P<dose>\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|IU|units))\s*"
            r"(?:(?P<freq>OD|BD|TDS|TID|QID|HS|SOS|PRN|once daily|twice daily|thrice daily)\b)?"
            r"(?:\s*(?:x|for)\s*(?P<duration>\d+\s*(?:days?|weeks?|months?)))?",
            re.IGNORECASE,
        )

        for match in med_pattern.finditer(text):
            groups = match.groupdict()
            form = groups.get("form") or ""
            name = groups.get("name", "").strip()
            # Filter out non-medication capitalized words
            if name.lower() in ("hospital", "department", "patient", "clinical", "laboratory", "report", "discharge"):
                continue

            full_name = f"{form} {name}".strip()
            results.append({
                "name": full_name,
                "dosage": (groups.get("dose") or "").strip(),
                "frequency": (groups.get("freq") or "OD").strip().upper(),
                "duration": (groups.get("duration") or "").strip() or None,
                "confidence": 0.89,
            })

        return results

    # --------------------------------------------------------------------------
    # 3. LABORATORY RESULTS EXTRACTION
    # --------------------------------------------------------------------------
    def extract_laboratory_results(self, text: str) -> List[Dict[str, Any]]:
        results = []
        # Pattern matching: Test Name : Value Unit (Reference Range)
        # e.g. "Hemoglobin: 13.8 g/dL (Normal 12.0 - 16.0)"
        lab_pattern = re.compile(
            r"(?P<test>Hemoglobin|Hb|Platelets?|WBC|TLC|Total Count|Fasting Blood Glucose|Glucose|Blood Sugar|Creatinine|Bilirubin|Urea|SGOT|SGPT|ESR|HbA1c|TSH)\s*"
            r"[:=-]?\s*"
            r"(?P<val>\d+(?:\.\d+)?)\s*"
            r"(?P<unit>g/dL|mg/dL|g/L|mmol/L|µmol/L|IU/L|U/L|cells/cumm|/cumm|%|mIU/L)?"
            r"(?:\s*(?:\(|\[)?(?:Normal|Ref|Range)?\s*[:=-]?\s*(?P<ref>\d+(?:\.\d+)?\s*[-–]\s*\d+(?:\.\d+)?)(?:\)|\])?)?",
            re.IGNORECASE,
        )

        for match in lab_pattern.finditer(text):
            groups = match.groupdict()
            test_name = (groups.get("test") or "").strip().title()
            val = (groups.get("val") or "").strip()
            unit = (groups.get("unit") or "").strip() or None
            ref = (groups.get("ref") or "").strip() or None

            # Clinical interpretation
            interpretation = "Unknown"
            if ref and "-" in ref:
                try:
                    low, high = [float(x.strip()) for x in ref.split("-")]
                    v = float(val)
                    if v < low:
                        interpretation = "Low"
                    elif v > high:
                        interpretation = "High"
                    else:
                        interpretation = "Normal"
                except ValueError:
                    interpretation = "Normal"

            results.append({
                "test_name": test_name,
                "value": val,
                "unit": unit,
                "reference_range": ref,
                "interpretation": interpretation,
                "confidence": 0.93,
            })

        return results

    # --------------------------------------------------------------------------
    # 4. PROCEDURES & SURGERIES EXTRACTION
    # --------------------------------------------------------------------------
    def extract_procedures(self, text: str) -> List[Dict[str, Any]]:
        results = []
        proc_pattern = re.compile(
            r"\b(Appendectomy|Cholecystectomy|CABG|Coronary Artery Bypass|Angioplasty|Stenting|Cesarean Section|C-Section|"
            r"Hysterectomy|Endoscopy|Colonoscopy|Biopsy|Dialysis|Hernioplasty|Knee Replacement|Arthroplasty)\b",
            re.IGNORECASE,
        )

        for match in proc_pattern.finditer(text):
            proc_name = match.group(0).strip().title()
            results.append({
                "name": proc_name,
                "confidence": 0.90,
            })

        return results

    # --------------------------------------------------------------------------
    # 5. ALLERGIES EXTRACTION
    # --------------------------------------------------------------------------
    def extract_allergies(self, text: str) -> List[Dict[str, Any]]:
        results = []
        # Pattern: Allergy / Allergic to : Allergen (Reaction)
        allergy_pattern = re.compile(
            r"(?:allergy|allergies|allergic to)\s*[:=-]?\s*(?P<allergen>[A-Za-z0-9\s]+?)(?=(?:\n|\.|\,|$|\;))",
            re.IGNORECASE,
        )
        for match in allergy_pattern.finditer(text):
            val = match.group("allergen").strip()
            if val.lower() not in ("none", "nil", "no known drug allergies", "nkda", "no", "denied"):
                results.append({
                    "allergen": val.title(),
                    "confidence": 0.87,
                })

        # Check for specific drug allergy mentions directly
        direct_allergens = ["penicillin", "sulfa", "aspirin", "ibuprofen", "peanuts", "latex"]
        for alg in direct_allergens:
            if re.search(rf"\b{alg}\s+allergy\b", text, re.IGNORECASE):
                results.append({
                    "allergen": alg.title(),
                    "confidence": 0.91,
                })

        return results

    # --------------------------------------------------------------------------
    # 6. DATES EXTRACTION
    # --------------------------------------------------------------------------
    def extract_dates(self, text: str) -> List[Dict[str, Any]]:
        results = []
        date_pattern = re.compile(
            r"\b(?P<date>(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4})|(?:\d{4}-\d{2}-\d{2})|(?:\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4}))\b",
            re.IGNORECASE,
        )

        for match in date_pattern.finditer(text):
            dt_str = match.group("date").strip()
            results.append({
                "date_string": dt_str,
                "confidence": 0.95,
            })

        return results

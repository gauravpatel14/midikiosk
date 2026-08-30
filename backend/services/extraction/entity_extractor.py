"""Unified Clinical Entity Extractor for MediKiosk.

Merges LLM (OpenAI gpt-4o-mini / local medical models) with high-precision
regular expression fallbacks and ICD-10 clinical coding normalization.
"""

from typing import Any, Dict, List, Optional

try:
    from services.extraction.icd10_map import lookup_icd10
    from services.extraction.llm_extractor import LLMEntityExtractor
    from services.extraction.regex_extractor import RegexClinicalExtractor
except ImportError:
    from .icd10_map import lookup_icd10
    from .llm_extractor import LLMEntityExtractor
    from .regex_extractor import RegexClinicalExtractor


class EntityExtractor:
    """Extracts diagnoses (with ICD-10), medications, lab results, procedures, allergies, and dates."""

    def __init__(self, use_llm_if_available: bool = True) -> None:
        self.use_llm = use_llm_if_available
        self.regex_engine = RegexClinicalExtractor()
        self.llm_engine = LLMEntityExtractor()

    def extract(self, text: str) -> Dict[str, Any]:
        """Extract structured medical entities and confidence scores from unstructured OCR text.
        
        Args:
            text: Raw OCR or transcription text from clinical records.
            
        Returns:
            Dict conforming to MediKiosk clinical entity schema.
        """
        if not text or not text.strip():
            return {
                "status": "empty",
                "extraction_method": "none",
                "overall_confidence": 0.0,
                "entities": {
                    "diagnoses": [],
                    "medications": [],
                    "laboratory_results": [],
                    "procedures": [],
                    "allergies": [],
                    "dates": [],
                },
                "raw_text_length": 0,
            }

        extracted_data: Optional[Dict[str, Any]] = None
        method_used = "regex_rule_engine"

        # 1. Attempt LLM Extraction if enabled
        if self.use_llm and self.llm_engine.client:
            extracted_data = self.llm_engine.extract_with_llm(text)
            if extracted_data:
                method_used = "llm_openai_gpt4o_mini"

        # 2. Fallback to Regex Rule Engine if LLM returned None or disabled
        if not extracted_data:
            extracted_data = {
                "diagnoses": self.regex_engine.extract_diagnoses(text),
                "medications": self.regex_engine.extract_medications(text),
                "laboratory_results": self.regex_engine.extract_laboratory_results(text),
                "procedures": self.regex_engine.extract_procedures(text),
                "allergies": self.regex_engine.extract_allergies(text),
                "dates": self.regex_engine.extract_dates(text),
            }
            method_used = "regex_rule_engine"
        else:
            # Augment / normalize any missing regex matches
            regex_diag = self.regex_engine.extract_diagnoses(text)
            existing_diag_names = {d["name"].lower() for d in extracted_data.get("diagnoses", [])}
            for d in regex_diag:
                if d["name"].lower() not in existing_diag_names:
                    extracted_data.setdefault("diagnoses", []).append(d)

        # 3. Post-process & Normalize ICD-10 for Diagnoses
        for diag in extracted_data.get("diagnoses", []):
            if not diag.get("icd10_code") or diag.get("icd10_code") == "R69":
                icd_match = lookup_icd10(diag.get("name", ""))
                if icd_match:
                    diag["icd10_code"] = icd_match["code"]
                    diag["icd10_title"] = icd_match["title"]

        # 4. Compute Overall Confidence
        all_confidences = []
        for cat in ("diagnoses", "medications", "laboratory_results", "procedures", "allergies", "dates"):
            items = extracted_data.get(cat, [])
            for item in items:
                if isinstance(item, dict) and "confidence" in item:
                    all_confidences.append(float(item["confidence"]))

        overall_conf = (
            round(sum(all_confidences) / len(all_confidences), 2)
            if all_confidences
            else 0.85
        )

        return {
            "status": "success",
            "extraction_method": method_used,
            "overall_confidence": overall_conf,
            "entities": {
                "diagnoses": extracted_data.get("diagnoses", []),
                "medications": extracted_data.get("medications", []),
                "laboratory_results": extracted_data.get("laboratory_results", []),
                "procedures": extracted_data.get("procedures", []),
                "allergies": extracted_data.get("allergies", []),
                "dates": extracted_data.get("dates", []),
            },
            "raw_text_length": len(text),
        }

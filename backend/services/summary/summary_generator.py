"""Summary Generator for MediKiosk.

Takes structured patient history (from DialogueManager) and OCR document
extraction data (from EntityExtractor) and compiles a physician-ready
editable summary in HTML and plain text.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import jinja2

try:
    from services.summary.templates import HTML_SUMMARY_TEMPLATE, PLAIN_TEXT_SUMMARY_TEMPLATE
except ImportError:
    from .templates import HTML_SUMMARY_TEMPLATE, PLAIN_TEXT_SUMMARY_TEMPLATE

from backend.services.ayush_safety import ayush_safety_service
from backend.services.drug_interaction import drug_interaction_service


class SummaryGenerator:
    """Enterprise clinical summary generator utilizing Jinja2 templates."""

    def __init__(self) -> None:
        self.jinja_env = jinja2.Environment(autoescape=False)
        self.html_template = self.jinja_env.from_string(HTML_SUMMARY_TEMPLATE)
        self.text_template = self.jinja_env.from_string(PLAIN_TEXT_SUMMARY_TEMPLATE)

    def generate(
        self,
        patient_data: Dict[str, Any],
        document_data: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, str]:
        """Generate physician-ready clinical summary in both HTML and plain text.
        
        Args:
            patient_data: Dict containing patient demographics and dialogue manager session data.
            document_data: Optional dict from OCR document entity extractor.
            
        Returns:
            Tuple of (html_summary, plain_text_summary)
        """
        document_data = document_data or {}
        context = self._build_template_context(patient_data, document_data)

        html_out = self.html_template.render(**context)
        text_out = self.text_template.render(**context)

        return html_out, text_out

    def _build_template_context(
        self, patient_data: Dict[str, Any], document_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Normalize and merge dialogue history and document extraction into a unified context."""
        now_str = datetime.now(timezone.utc).strftime("%d-%b-%Y %H:%M UTC")

        # 1. Demographics
        demo_raw = patient_data.get("demographics") or patient_data.get("patient")
        demo: Dict[str, Any] = demo_raw if isinstance(demo_raw, dict) else {}
        name = f"{demo.get('first_name', '')} {demo.get('last_name', '')}".strip() or demo.get("name", "Unknown Patient")
        
        patient_info = {
            "name": name,
            "age": demo.get("age", "--"),
            "gender": demo.get("gender", "--"),
            "abha_id": demo.get("abha_id"),
            "temp_id": str(patient_data.get("temp_patient_id") or demo.get("id") or "") or None,
            "phone": demo.get("phone_number", demo.get("phone", "--")),
            "language": demo.get("preferred_language", "Hindi"),
        }

        # 2. Chief Complaint
        cc_raw = patient_data.get("chief_complaint")
        if isinstance(cc_raw, dict):
            cc_text = cc_raw.get("complaint") or cc_raw.get("text") or "Not recorded"
        elif isinstance(cc_raw, str):
            cc_text = cc_raw
        else:
            cc_text = "Not recorded"

        # 3. HPI (SOCRATES)
        raw_hpi = patient_data.get("hpi")
        hpi_raw: Dict[str, Any] = raw_hpi if isinstance(raw_hpi, dict) else {}
        hpi_info = {
            "duration": hpi_raw.get("HPI_DURATION", hpi_raw.get("duration", "Recent onset")),
            "character": hpi_raw.get("HPI_SOCRATES_CHARACTER", hpi_raw.get("character")),
            "radiation": hpi_raw.get("HPI_SOCRATES_RADIATION", hpi_raw.get("radiation")),
            "severity": hpi_raw.get("HPI_SOCRATES_SEVERITY", hpi_raw.get("severity")),
        }

        # 4. Past Medical History (merge dialogue PMH and OCR procedures/surgeries)
        past_med = list(patient_data.get("past_medical", []))
        ocr_procs = document_data.get("entities", {}).get("procedures", [])
        for p in ocr_procs:
            p_name = f"Prior Procedure: {p.get('name')}"
            if p_name not in past_med:
                past_med.append(p_name)

        # 5. Drug History (merge dialogue meds and OCR extracted meds)
        meds_raw = patient_data.get("medications", [])
        medications: List[Dict[str, Any]] = []
        for m in meds_raw:
            if isinstance(m, str):
                medications.append({"name": m, "dosage": "--", "frequency": "--", "duration": "--"})
            elif isinstance(m, dict):
                medications.append(m)

        ocr_meds = document_data.get("entities", {}).get("medications", [])
        for om in ocr_meds:
            medications.append({
                "name": om.get("name", "Unknown Medicine"),
                "dosage": om.get("dosage", "--"),
                "frequency": om.get("frequency", "--"),
                "duration": om.get("duration", "--"),
            })

        # 6. Allergies (merge dialogue allergies and OCR allergies)
        allergies = list(patient_data.get("allergies", []))
        ocr_allergies = document_data.get("entities", {}).get("allergies", [])
        for oa in ocr_allergies:
            alg_name = oa.get("allergen", "")
            if alg_name and alg_name not in allergies:
                allergies.append(alg_name)

        # 7. Family History
        family = list(patient_data.get("family_history", []))

        # 8. Personal History
        personal = list(patient_data.get("personal_history", []))

        # 9. Review of Systems
        ros = list(patient_data.get("review_of_systems", []))

        # 10. Prior Investigations (OCR Lab results with abnormal flag)
        labs_raw = document_data.get("entities", {}).get("laboratory_results", [])
        lab_results: List[Dict[str, Any]] = []
        for lab in labs_raw:
            val_str = str(lab.get("value", "")).strip()
            ref_str = str(lab.get("reference_range", "") or "").strip()
            interp = lab.get("interpretation", "Normal")

            # Determine High/Low if not already set
            if interp == "Unknown" and "-" in ref_str:
                try:
                    low, high = [float(x.strip()) for x in ref_str.split("-")]
                    v = float(val_str)
                    if v < low:
                        interp = "Low"
                    elif v > high:
                        interp = "High"
                    else:
                        interp = "Normal"
                except (ValueError, TypeError):
                    interp = "Normal"

            lab_results.append({
                "test_name": lab.get("test_name", "Lab Investigation"),
                "value": val_str,
                "unit": lab.get("unit", ""),
                "reference_range": ref_str,
                "interpretation": interp,
            })

        # 11. AYUSH Dashavidha Pariksha
        is_ayush = patient_data.get("is_ayush", False) or (patient_data.get("mode", "").upper() == "AYUSH")
        ayush_raw = patient_data.get("ayush_assessments", {})
        ayush_info = {
            "prakriti": ayush_raw.get("AYUSH_PRAKRITI", "Vata-Pitta Prakriti"),
            "vikriti": ayush_raw.get("AYUSH_VIKRITI", "Vata Vriddhi / Dosha Dushti"),
            "sara": ayush_raw.get("AYUSH_SARA", "Madhyama Sara"),
            "samhanana": ayush_raw.get("AYUSH_SAMHANANA", "Madhyama Samhanana"),
            "pramana": ayush_raw.get("AYUSH_PRAMANA", "Yatha-pramana"),
            "satmya": ayush_raw.get("AYUSH_SATMYA", "Oka-satmya"),
            "sattva": ayush_raw.get("AYUSH_SATTVA", "Madhyama Sattva"),
            "agni": ayush_raw.get("AYUSH_AGNI_KOSHTHA", "Samagni (Balanced digestion)"),
            "vyayama": ayush_raw.get("AYUSH_VYAYAMA", "Madhyama"),
            "vaya": ayush_raw.get("AYUSH_VAYA", "Madhyama Vaya"),
        }

        # 12. Drug-Drug Interactions Detection (Real Source)
        med_names = [m.get("name", "") for m in medications if m.get("name")]
        drug_interactions = drug_interaction_service.check_interactions(med_names)

        # 13. AYUSH Contraindication & Heavy Metal Safety
        patient_conditions = past_med + [cc_text]
        ayush_alerts = ayush_safety_service.evaluate_formulation_safety(
            med_names, patient_conditions=patient_conditions
        )

        # 14. Chronological Document Sorting & Timeline
        raw_docs = document_data.get("documents")
        if not raw_docs:
            if document_data.get("filename"):
                raw_docs = [document_data]
            else:
                raw_docs = []

        def _doc_sort_key(d: Dict[str, Any]) -> str:
            return str(d.get("document_date") or d.get("date") or d.get("timestamp") or "1970-01-01")

        sorted_docs = sorted(raw_docs, key=_doc_sort_key, reverse=True)
        document_timeline = [
            {
                "date": d.get("document_date") or d.get("date") or "Unknown Date",
                "type": d.get("document_type_hint") or d.get("type") or "Clinical Record",
                "filename": d.get("filename") or "document.pdf",
                "confidence": float(d.get("confidence_score") or d.get("confidence") or 0.9),
            }
            for d in sorted_docs
        ]

        # 15. Red Flags
        rf = patient_data.get("red_flag") or patient_data.get("red_flag_details")

        return {
            "hospital_name": "All India Institute of Ayurveda - Clinical OPD",
            "generated_date": now_str,
            "patient": patient_info,
            "chief_complaint": {"text": cc_text},
            "hpi": hpi_info,
            "past_medical": past_med,
            "medications": medications,
            "allergies": allergies,
            "family_history": family,
            "personal_history": personal,
            "review_of_systems": ros,
            "laboratory_results": lab_results,
            "drug_interactions": drug_interactions,
            "ayush_alerts": ayush_alerts,
            "document_timeline": document_timeline,
            "is_ayush": is_ayush,
            "ayush": ayush_info,
            "red_flag": rf,
            "physician_notes": patient_data.get("physician_notes"),
        }

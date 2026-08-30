"""AYUSH Herbomineral Safety & Heavy Metal Contraindication Service.

Integrates:
- Ayurvedic Pharmacopoeia of India (API) Part I & II heavy metal permissible standards
- WHO Guidelines for Quality Control of Herbal Medicines
- Schedule E(1) of the Drugs and Cosmetics Rules 1945 (Ayurvedic poisonous substances)
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger(__name__)


class AyushSafetyService:
    """Evaluates AYUSH herbo-mineral formulations, heavy metal limits, and contraindications."""

    def __init__(self) -> None:
        self.data_path = settings.AYUSH_SAFETY_DATA_PATH
        self.pharmacopoeia = ""
        self.permissible_limits: Dict[str, Any] = {}
        self.formulations: List[Dict[str, Any]] = []
        self._load_safety_db()

    def _load_safety_db(self) -> None:
        resolved_path = os.path.abspath(self.data_path)
        if not os.path.exists(resolved_path):
            logger.warning("ayush_safety_db_missing", path=resolved_path)
            return

        try:
            with open(resolved_path, mode="r", encoding="utf-8") as f:
                data = json.load(f)
                self.pharmacopoeia = data.get("pharmacopoeia", "API / WHO")
                self.permissible_limits = data.get("permissible_limits_ppm", {})
                self.formulations = data.get("rasa_shastra_formulations", [])
            logger.info("ayush_safety_db_loaded", formulations=len(self.formulations), path=resolved_path)
        except Exception as exc:
            logger.error("ayush_safety_db_load_failed", error=str(exc))

    def evaluate_formulation_safety(
        self, medication_names: List[str], patient_conditions: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Check extracted medications against known herbo-mineral preparations and patient contraindications."""
        alerts: List[Dict[str, Any]] = []
        if not medication_names:
            return alerts

        conditions_lower = [c.lower() for c in (patient_conditions or [])]

        for med in medication_names:
            med_clean = med.lower().strip()
            # Match against known Rasa Shastra formulations
            for form in self.formulations:
                matched = False
                if form["name"].lower() in med_clean:
                    matched = True
                else:
                    for alias in form.get("aliases", []):
                        if alias.lower() in med_clean:
                            matched = True
                            break

                if matched:
                    # Check if patient conditions trigger specific contraindications
                    triggered_contraindications: List[str] = []
                    for contra in form.get("contraindications", []):
                        contra_lower = contra.lower()
                        for cond in conditions_lower:
                            if any(k in cond for k in ["kidney", "renal", "ckd", "creatinine"]) and any(k in contra_lower for k in ["kidney", "renal", "ckd", "nephrotic"]):
                                triggered_contraindications.append(contra)
                            elif any(k in cond for k in ["pregnant", "pregnancy"]) and any(k in contra_lower for k in ["pregnan", "lactat"]):
                                triggered_contraindications.append(contra)
                            elif any(k in cond for k in ["hypertension", "bp high", "high bp"]) and any(k in contra_lower for k in ["hyperten", "bp"]):
                                triggered_contraindications.append(contra)
                            elif any(k in cond for k in ["liver", "hepatic", "cirrhosis"]) and any(k in contra_lower for k in ["liver", "hepatic"]):
                                triggered_contraindications.append(contra)

                    severity = "High" if triggered_contraindications else "Moderate"

                    alerts.append({
                        "formulation": form["name"],
                        "matched_input": med,
                        "severity": severity,
                        "elements": form.get("herbo_mineral_elements", []),
                        "toxicity_alert": form.get("toxicity_alert", ""),
                        "contraindications": form.get("contraindications", []),
                        "triggered_contraindications": list(set(triggered_contraindications)),
                        "max_duration_days": form.get("max_duration_days"),
                        "regulatory_status": form.get("regulatory_status", ""),
                        "standard_limits": self.permissible_limits,
                    })

        return alerts


ayush_safety_service = AyushSafetyService()

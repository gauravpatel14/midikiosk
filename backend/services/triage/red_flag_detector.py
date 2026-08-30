"""RedFlagDetector service for MediKiosk Emergency Triage.

Evaluates unstructured patient speech/touch responses and structured vitals data
to detect life-threatening clinical emergencies and generate immediate triage alerts.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

try:
    from services.triage.emergency_patterns import EMERGENCY_PATTERNS
    from services.triage.vitals_checker import check_physiological_vitals
except ImportError:
    from .emergency_patterns import EMERGENCY_PATTERNS
    from .vitals_checker import check_physiological_vitals


class RedFlagDetector:
    """Enterprise emergency triage and red-flag detection service for MediKiosk."""

    def __init__(self, custom_patterns: Optional[List[Dict[str, Any]]] = None) -> None:
        self.patterns = custom_patterns or EMERGENCY_PATTERNS

    def check(
        self, text: Optional[str] = None, vitals: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Evaluate patient text and structured vitals for emergency red flags.
        
        Args:
            text: Patient voice transcript or selected touch response.
            vitals: Optional dict of measured vitals (systolic_bp, spo2, heart_rate, etc.)
            
        Returns:
            List of detected red flag dictionaries.
        """
        flags: List[Dict[str, Any]] = []

        # 1. EVALUATE TEXT PATTERNS (Multilingual NLP Regex)
        if text and text.strip():
            lower_text = text.lower()
            for pattern in self.patterns:
                # Check if any primary trigger matches
                primary_match = any(
                    re.search(trig, lower_text, re.IGNORECASE)
                    for trig in pattern["primary_triggers"]
                )

                if primary_match:
                    # If pattern requires co-symptoms, verify co-symptom match
                    co_symptoms = pattern.get("co_symptoms", [])
                    if co_symptoms:
                        co_match = any(
                            re.search(co, lower_text, re.IGNORECASE)
                            for co in co_symptoms
                        )
                        if co_match:
                            flags.append({
                                "trigger_source": "PATIENT_RESPONSE_TEXT",
                                "category": pattern["category"],
                                "severity": pattern["severity"],
                                "description": pattern["description"],
                                "rule": f"Matched primary symptom + secondary co-symptom in '{text.strip()[:60]}'",
                                "recommended_action": pattern["action"],
                            })
                    else:
                        # Direct trigger without co-symptoms (e.g. suicidal ideation, poison ingestion, stridor)
                        flags.append({
                            "trigger_source": "PATIENT_RESPONSE_TEXT",
                            "category": pattern["category"],
                            "severity": pattern["severity"],
                            "description": pattern["description"],
                            "rule": f"Matched standalone emergency trigger in '{text.strip()[:60]}'",
                            "recommended_action": pattern["action"],
                        })

        # 2. EVALUATE STRUCTURED PHYSIOLOGICAL VITALS
        if vitals:
            vitals_flags = check_physiological_vitals(vitals)
            for vf in vitals_flags:
                flags.append({
                    "trigger_source": "PHYSIOLOGICAL_VITALS",
                    "category": vf["category"],
                    "severity": vf["severity"],
                    "description": vf["description"],
                    "rule": f"{vf['parameter']} = {vf['observed_value']} (Threshold: {vf['threshold']})",
                    "recommended_action": vf["action"],
                })

        return flags

    def has_red_flags(
        self, text: Optional[str] = None, vitals: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, List[Dict[str, Any]]]:
        """Convenience method returning (is_flagged_boolean, list_of_flags)."""
        flags = self.check(text, vitals)
        return len(flags) > 0, flags


red_flag_detector = RedFlagDetector()

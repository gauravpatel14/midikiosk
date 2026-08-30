"""Red-flag detection engine for MediKiosk.

Monitors patient speech and touch responses for clinical emergency criteria.
Immediately halts the conversational interview and notifies triage nurses.
"""

import re
from typing import Any, Dict, Optional, Tuple

# Robust clinical emergency patterns supporting natural phrase variations across languages
RED_FLAG_PATTERNS = [
    {
        "category": "ACUTE_CORONARY_SYNDROME",
        "primary": [
            r"\b(chest|angina).{0,20}(pain|pressure|tightness|heavy|heaviness)\b",
            r"(सीने|छाती|दिल).{0,25}(दर्द|भारीपन|दबाव)",
            r"நெஞ்சு.{0,20}வலி",
        ],
        "co_symptoms": [
            r"\b(breath|breathless|shortness of breath|dyspnea)\b",
            r"(सांस|दम|दम फूलना)",
            r"மூச்சு",
            r"\b(sweat|sweating|perspiration)\b",
            r"(पसीना|घबराहट)",
            r"\b(left arm|arm|jaw|neck)\b",
            r"(बायें हाथ|बाएं हाथ|हाथ|कंधे|जबड़े)",
            r"\b(dizzy|dizziness|faint|fainting|syncope)\b",
            r"(चक्कर|बेहोशी)",
        ],
        "message": "Potential Acute Coronary Syndrome detected. Immediate triage nursing required.",
    },
    {
        "category": "ACUTE_STROKE",
        "primary": [
            r"\b(weakness|slurred speech|facial droop|paralysis|numbness)\b",
            r"(कमजोरी|आवाज लड़खड़ाना|लकवा|सुन्न)",
        ],
        "co_symptoms": [
            r"\b(one side|face|arm|leg|sudden|vision)\b",
            r"(एक तरफ|चेहरा|अचानक|दिखाई नहीं दे रहा)",
        ],
        "message": "Potential acute cerebrovascular event (stroke) symptoms detected.",
    },
    {
        "category": "SEVERE_HEADACHE_THUNDERCLAP",
        "primary": [
            r"\b(worst headache|thunderclap|severe headache)\b",
            r"(भयानक सिरदर्द|असहनीय सिरदर्द|तेज सिरदर्द)",
        ],
        "co_symptoms": [
            r"\b(neck stiffness|stiff neck|vomiting|confusion)\b",
            r"(गर्दन अकड़ना|उल्टी|बेहोशी)",
        ],
        "message": "Severe acute headache with meningeal/intracranial warning signs.",
    },
    {
        "category": "ACUTE_ABDOMEN_GI_BLEED",
        "primary": [
            r"\b(vomiting blood|hematemesis|black stool|melena)\b",
            r"(खून की उल्टी|काला शौच|पेट में भयंकर दर्द)",
        ],
        "co_symptoms": [
            r"\b(faint|fainting|chills|rigid|cold)\b",
            r"(बेहोश|कड़ा)",
        ],
        "message": "Potential acute abdomen or internal gastrointestinal hemorrhage.",
    },
    {
        "category": "PSYCHIATRIC_CRISIS",
        "primary": [
            r"\b(suicide|suicidal|kill myself|want to die|end my life)\b",
            r"(आत्महत्या|खुद को नुकसान|मरना चाहता)",
        ],
        "co_symptoms": [],
        "message": "High-risk psychiatric distress or suicidal ideation detected.",
    },
]


def check_clinical_red_flags(text: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """Inspect patient response for emergency clinical trigger conditions using regex."""
    if not text or not text.strip():
        return False, None

    lower_text = text.lower()

    for rule in RED_FLAG_PATTERNS:
        # Check primary symptom match
        primary_match = any(re.search(p, lower_text, re.IGNORECASE) for p in rule["primary"])
        if primary_match:
            # If no co-symptoms required
            if not rule["co_symptoms"]:
                return True, {
                    "category": rule["category"],
                    "rule": "Primary clinical alert trigger",
                    "raw_text": text,
                    "severity": "CRITICAL",
                    "action": "INTERVIEW_HALTED_TRIAGE_ALERTED",
                    "triage_message": rule["message"],
                }

            # Check co-symptom match
            co_match = any(re.search(co, lower_text, re.IGNORECASE) for co in rule["co_symptoms"])
            if co_match:
                return True, {
                    "category": rule["category"],
                    "rule": "Combined primary symptom + co-symptom alert trigger",
                    "raw_text": text,
                    "severity": "CRITICAL",
                    "action": "INTERVIEW_HALTED_TRIAGE_ALERTED",
                    "triage_message": rule["message"],
                }

    return False, None

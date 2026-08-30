"""ICD-10 Clinical Coding Dictionary and Normalization for MediKiosk.

Maps common clinical diagnoses, symptoms, and OPD presentations
to standard WHO ICD-10 diagnostic codes.
"""

from typing import Dict, Optional, Tuple

ICD10_DATABASE: Dict[str, Tuple[str, str]] = {
    # Cardiovascular
    "hypertension": ("I10", "Essential (primary) hypertension"),
    "high blood pressure": ("I10", "Essential (primary) hypertension"),
    "htn": ("I10", "Essential (primary) hypertension"),
    "angina": ("I20.9", "Angina pectoris, unspecified"),
    "angina pectoris": ("I20.9", "Angina pectoris, unspecified"),
    "myocardial infarction": ("I21.9", "Acute myocardial infarction, unspecified"),
    "heart attack": ("I21.9", "Acute myocardial infarction, unspecified"),
    "coronary artery disease": ("I25.10", "Atherosclerotic heart disease of native coronary artery"),
    "cad": ("I25.10", "Atherosclerotic heart disease of native coronary artery"),
    "heart failure": ("I50.9", "Heart failure, unspecified"),

    # Endocrine & Metabolic
    "type 2 diabetes": ("E11.9", "Type 2 diabetes mellitus without complications"),
    "type 2 diabetes mellitus": ("E11.9", "Type 2 diabetes mellitus without complications"),
    "t2dm": ("E11.9", "Type 2 diabetes mellitus without complications"),
    "diabetes": ("E11.9", "Type 2 diabetes mellitus without complications"),
    "diabetes mellitus": ("E11.9", "Type 2 diabetes mellitus without complications"),
    "hypothyroidism": ("E03.9", "Hypothyroidism, unspecified"),
    "hyperthyroidism": ("E05.90", "Thyrotoxicosis, unspecified"),
    "dyslipidemia": ("E78.5", "Hyperlipidemia, unspecified"),
    "high cholesterol": ("E78.00", "Pure hypercholesterolemia, unspecified"),

    # Respiratory
    "asthma": ("J45.909", "Unspecified asthma, uncomplicated"),
    "bronchial asthma": ("J45.909", "Unspecified asthma, uncomplicated"),
    "copd": ("J44.9", "Chronic obstructive pulmonary disease, unspecified"),
    "acute bronchitis": ("J20.9", "Acute bronchitis, unspecified"),
    "bronchitis": ("J20.9", "Acute bronchitis, unspecified"),
    "pneumonia": ("J18.9", "Pneumonia, unspecified organism"),
    "upper respiratory tract infection": ("J06.9", "Acute upper respiratory infection, unspecified"),
    "urti": ("J06.9", "Acute upper respiratory infection, unspecified"),
    "allergic rhinitis": ("J30.9", "Allergic rhinitis, unspecified"),

    # Gastrointestinal
    "gerd": ("K21.9", "Gastro-esophageal reflux disease without esophagitis"),
    "acid reflux": ("K21.9", "Gastro-esophageal reflux disease without esophagitis"),
    "gastritis": ("K29.70", "Gastritis, unspecified, without bleeding"),
    "peptic ulcer": ("K27.9", "Peptic ulcer, site unspecified"),
    "gastroenteritis": ("A09", "Infectious gastroenteritis and colitis, unspecified"),
    "irritable bowel syndrome": ("K58.9", "Irritable bowel syndrome without diarrhea"),
    "ibs": ("K58.9", "Irritable bowel syndrome without diarrhea"),
    "fatty liver": ("K76.0", "Fatty (change of) liver, not elsewhere classified"),

    # Musculoskeletal & Rheumatology
    "osteoarthritis": ("M19.90", "Unspecified osteoarthritis, unspecified site"),
    "rheumatoid arthritis": ("M06.9", "Rheumatoid arthritis, unspecified"),
    "lumbar spondylosis": ("M47.817", "Spondylosis without myelopathy or radiculopathy, lumbosacral region"),
    "back pain": ("M54.50", "Low back pain, unspecified"),
    "cervical spondylosis": ("M47.812", "Spondylosis without myelopathy or radiculopathy, cervical region"),

    # Infections & General
    "fever": ("R50.9", "Fever, unspecified"),
    "pyrexia": ("R50.9", "Fever, unspecified"),
    "urinary tract infection": ("N39.0", "Urinary tract infection, site not specified"),
    "uti": ("N39.0", "Urinary tract infection, site not specified"),
    "migraine": ("G43.909", "Migraine, unspecified, not intractable"),
    "anemia": ("D64.9", "Anemia, unspecified"),
}


def lookup_icd10(diagnosis_name: str) -> Optional[Dict[str, str]]:
    """Lookup ICD-10 code and descriptive title for a clinical condition name."""
    if not diagnosis_name:
        return None

    clean = diagnosis_name.strip().lower()
    # Direct match
    if clean in ICD10_DATABASE:
        code, title = ICD10_DATABASE[clean]
        return {"code": code, "title": title}

    # Substring / partial match
    for key, (code, title) in ICD10_DATABASE.items():
        if key in clean or clean in key:
            return {"code": code, "title": title}

    return None

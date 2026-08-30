"""Automated test suite verifying MediKiosk RedFlagDetector service."""

import sys
from pathlib import Path

# Add root and backend to path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
for p in [str(root_dir), str(backend_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.services.triage.red_flag_detector import RedFlagDetector


def test_red_flag_suite():
    print("\n--- Running MediKiosk Red Flag Detector Test Suite ---")

    detector = RedFlagDetector()

    # --------------------------------------------------------------------------
    # 1. ACUTE CORONARY SYNDROME (ACS / MI)
    # --------------------------------------------------------------------------
    text_acs = "I am having crushing chest tightness and pain radiating down my left arm with cold sweats."
    is_flagged, flags = detector.has_red_flags(text_acs)
    assert is_flagged is True
    assert any(f["category"] == "ACUTE_CORONARY_SYNDROME" for f in flags)
    print(f"✔ 1. ACS Detection: Triggered {flags[0]['category']} ({flags[0]['severity']})")

    # --------------------------------------------------------------------------
    # 2. ACUTE STROKE (FAST CRITERIA)
    # --------------------------------------------------------------------------
    text_stroke = "My mother suddenly developed slurred speech and facial droop with one side weakness."
    is_flagged, flags = detector.has_red_flags(text_stroke)
    assert is_flagged is True
    assert any(f["category"] == "ACUTE_STROKE" for f in flags)
    print(f"✔ 2. Stroke Detection: Triggered {flags[0]['category']} ({flags[0]['severity']})")

    # --------------------------------------------------------------------------
    # 3. RESPIRATORY FAILURE / STRIDOR
    # --------------------------------------------------------------------------
    text_resp = "Patient is gasping for air and suffocating, cannot breathe at all."
    is_flagged, flags = detector.has_red_flags(text_resp)
    assert is_flagged is True
    assert any(f["category"] == "ACUTE_RESPIRATORY_FAILURE" for f in flags)
    print(f"✔ 3. Respiratory Failure: Triggered {flags[0]['category']}")

    # --------------------------------------------------------------------------
    # 4. ACUTE GI BLEED & SHOCK
    # --------------------------------------------------------------------------
    text_gi = "Had vomiting blood twice and black stool with fainting."
    is_flagged, flags = detector.has_red_flags(text_gi)
    assert is_flagged is True
    assert any(f["category"] == "ACUTE_GI_BLEED" for f in flags)
    print(f"✔ 4. GI Bleed Detection: Triggered {flags[0]['category']}")

    # --------------------------------------------------------------------------
    # 5. THUNDERCLAP HEADACHE (SAH)
    # --------------------------------------------------------------------------
    text_headache = "Sudden worst headache of life with severe neck stiffness."
    is_flagged, flags = detector.has_red_flags(text_headache)
    assert is_flagged is True
    assert any(f["category"] == "SEVERE_HEADACHE_THUNDERCLAP" for f in flags)
    print(f"✔ 5. Thunderclap Headache: Triggered {flags[0]['category']}")

    # --------------------------------------------------------------------------
    # 6. SNAKEBITE & POISONING (Rural India OPD)
    # --------------------------------------------------------------------------
    text_snake = "खेत में काम करते समय सांप ने काटा है और आंखों में अंधेरा छा रहा है।"
    is_flagged, flags = detector.has_red_flags(text_snake)
    assert is_flagged is True
    assert any(f["category"] == "SNAKEBITE_POISONING" for f in flags)
    print(f"✔ 6. Snakebite Detection (Hindi): Triggered {flags[0]['category']}")

    # --------------------------------------------------------------------------
    # 7. PSYCHIATRIC CRISIS
    # --------------------------------------------------------------------------
    text_psych = "I feel hopeless and want to end my life, suicidal thoughts."
    is_flagged, flags = detector.has_red_flags(text_psych)
    assert is_flagged is True
    assert any(f["category"] == "PSYCHIATRIC_CRISIS" for f in flags)
    print(f"✔ 7. Psychiatric Crisis: Triggered {flags[0]['category']}")

    # --------------------------------------------------------------------------
    # 8. MULTILINGUAL (TAMIL)
    # --------------------------------------------------------------------------
    text_tamil = "நெஞ்சு வலி மற்றும் மூச்சுத் திணறல்"  # Chest pain + breathlessness
    is_flagged, flags = detector.has_red_flags(text_tamil)
    assert is_flagged is True
    print("✔ 8. Tamil Emergency Trigger: Successfully detected")

    # --------------------------------------------------------------------------
    # 9. STRUCTURED PHYSIOLOGICAL VITALS
    # --------------------------------------------------------------------------
    # 9a. Hypertensive Crisis
    flags_htn = detector.check(vitals={"systolic_bp": 195, "diastolic_bp": 125})
    assert any(f["category"] == "HYPERTENSIVE_CRISIS" for f in flags_htn)
    print("✔ 9a. Vitals: Hypertensive Crisis (195/125 mmHg) detected")

    # 9b. Circulatory Shock (Hypotension)
    flags_shock = detector.check(vitals={"systolic_bp": 78})
    assert any(f["category"] == "HYPOTENSION_CIRCULATORY_SHOCK" for f in flags_shock)
    print("✔ 9b. Vitals: Circulatory Shock (BP 78 mmHg) detected")

    # 9c. Critical Hypoxemia
    flags_spo2 = detector.check(vitals={"spo2": 82})
    assert any(f["category"] == "SEVERE_HYPOXEMIA" for f in flags_spo2)
    print("✔ 9c. Vitals: Severe Hypoxemia (SpO2 82%) detected")

    # 9d. Severe Hypoglycemia
    flags_sugar = detector.check(vitals={"blood_glucose": 42})
    assert any(f["category"] == "SEVERE_NEUROGLYCOPENIC_HYPOGLYCEMIA" for f in flags_sugar)
    print("✔ 9d. Vitals: Severe Hypoglycemia (42 mg/dL) detected")

    # --------------------------------------------------------------------------
    # 10. COMBINED TEXT + VITALS
    # --------------------------------------------------------------------------
    combo_flags = detector.check(
        text="Feeling dizzy after fever for 2 days",
        vitals={"systolic_bp": 82, "spo2": 88},
    )
    assert len(combo_flags) >= 2  # Shock + Hypoxemia
    print(f"✔ 10. Combined Text & Vitals: Detected {len(combo_flags)} emergency alerts simultaneously")

    # --------------------------------------------------------------------------
    # 11. NEGATIVE CONTROLS (Zero False Positives)
    # --------------------------------------------------------------------------
    benign_inputs = [
        "I have mild right knee pain when climbing stairs for 2 weeks",
        "Routine checkup for vegetarian diet_veg follow up",
        "Need refilling of my diabetes medicines",
    ]
    for b in benign_inputs:
        is_f, _ = detector.has_red_flags(b, vitals={"systolic_bp": 120, "spo2": 98, "heart_rate": 72})
        assert is_f is False, f"False positive triggered for benign input: {b}"
    print("✔ 11. Negative Controls: Zero false positives on benign inputs verified")

    print("\n--- ALL RED FLAG DETECTOR TESTS PASSED 100% ---")


if __name__ == "__main__":
    test_red_flag_suite()

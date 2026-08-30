"""Automated test suite verifying MediKiosk Dialogue Manager, SOCRATES, AYUSH, and Red Flags."""

import sys
from pathlib import Path

# Add root and backend to path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
for p in [str(root_dir), str(backend_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.services.dialogue.dialogue_manager import DialogueManager


def test_dialogue_manager_suite():
    print("\n--- Running MediKiosk Dialogue Manager Test Suite ---")

    # --------------------------------------------------------------------------
    # 1. INITIAL OPEN-ENDED QUESTION (All 3 Languages)
    # --------------------------------------------------------------------------
    dm_hi = DialogueManager(language="hi", mode="ALLOPATHIC")
    q_hi, opts_hi, is_final = dm_hi.start_interview()
    assert "अस्पताल किस तकलीफ" in q_hi
    assert len(opts_hi) > 0
    assert not is_final
    print(f"✔ 1a. Initial Open-Ended Question (Hindi): '{q_hi[:45]}...'")

    dm_en = DialogueManager(language="en", mode="ALLOPATHIC")
    q_en, opts_en, _ = dm_en.start_interview()
    assert "Please tell me what problem" in q_en
    print(f"✔ 1b. Initial Open-Ended Question (English): '{q_en}'")

    dm_ta = DialogueManager(language="ta", mode="ALLOPATHIC")
    q_ta, opts_ta, _ = dm_ta.start_interview()
    assert "பிரச்சனை" in q_ta
    print(f"✔ 1c. Initial Open-Ended Question (Tamil): '{q_ta[:45]}...'")

    # --------------------------------------------------------------------------
    # 2. FULL ALLOPATHIC INTERVIEW WITH SOCRATES PAIN FLOW
    # --------------------------------------------------------------------------
    print("\n--- Testing Allopathic SOCRATES Flow ---")
    dm = DialogueManager(language="en", mode="ALLOPATHIC")
    q, opts, _ = dm.start_interview()
    state = dm.current_state

    # Turn 1: Chief Complaint (Voice input: Chest pain)
    q, opts, is_final = dm.get_next_question(state, "I have severe chest pain and tightness")
    state = dm.current_state
    assert state == "HPI_DURATION"
    assert dm.collected_data["is_pain"] is True
    print(f"✔ Turn 1 -> Next: {state} | Question: '{q}'")

    # Turn 2: HPI Duration (Touch answer)
    q, opts, is_final = dm.get_next_question(state, "1-3_days")
    state = dm.current_state
    assert state == "HPI_SOCRATES_CHARACTER"
    print(f"✔ Turn 2 -> Next: {state} (SOCRATES Character)")

    # Turn 3: HPI SOCRATES Character
    q, opts, is_final = dm.get_next_question(state, "heavy_pressure")
    state = dm.current_state
    assert state == "HPI_SOCRATES_RADIATION"
    print(f"✔ Turn 3 -> Next: {state} (SOCRATES Radiation)")

    # Turn 4: HPI SOCRATES Radiation
    q, opts, is_final = dm.get_next_question(state, "left_arm")
    state = dm.current_state
    assert state == "HPI_SOCRATES_SEVERITY"
    print(f"✔ Turn 4 -> Next: {state} (SOCRATES Severity)")

    # Turn 5: HPI SOCRATES Severity
    q, opts, is_final = dm.get_next_question(state, "moderate_6")
    state = dm.current_state
    assert state == "PAST_MEDICAL_HISTORY"
    print(f"✔ Turn 5 -> Next: {state} (Past Medical History)")

    # Turn 6: Past Medical History
    q, opts, is_final = dm.get_next_question(state, "hypertension")
    state = dm.current_state
    assert state == "DRUG_HISTORY"
    print(f"✔ Turn 6 -> Next: {state} (Drug History)")

    # Turn 7: Drug History
    q, opts, is_final = dm.get_next_question(state, "bp_meds")
    state = dm.current_state
    assert state == "ALLERGY_HISTORY"
    print(f"✔ Turn 7 -> Next: {state} (Allergy History)")

    # Turn 8: Allergy History
    q, opts, is_final = dm.get_next_question(state, "none")
    state = dm.current_state
    assert state == "FAMILY_HISTORY"
    print(f"✔ Turn 8 -> Next: {state} (Family History)")

    # Turn 9: Family History
    q, opts, is_final = dm.get_next_question(state, "family_diabetes")
    state = dm.current_state
    assert state == "PERSONAL_HISTORY"
    print(f"✔ Turn 9 -> Next: {state} (Personal History / Lifestyle)")

    # Turn 10: Personal History
    q, opts, is_final = dm.get_next_question(state, "diet_veg")
    state = dm.current_state
    assert state == "REVIEW_OF_SYSTEMS"
    print(f"✔ Turn 10 -> Next: {state} (Review of Systems)")

    # Turn 11: Review of Systems -> Allopathic Complete
    q, opts, is_final = dm.get_next_question(state, "none")
    state = dm.current_state
    assert state == "COMPLETED"
    assert is_final is True
    print(f"✔ Turn 11 -> Allopathic Complete: '{q[:50]}...'")

    # --------------------------------------------------------------------------
    # 3. AYUSH MODE (DASHAVIDHA PARIKSHA)
    # --------------------------------------------------------------------------
    print("\n--- Testing AYUSH Dashavidha Pariksha Flow ---")
    dm_ayush = DialogueManager(language="hi", mode="AYUSH")
    dm_ayush.start_interview()
    # Fast forward to ROS
    dm_ayush.current_state = "REVIEW_OF_SYSTEMS"
    q, opts, is_final = dm_ayush.get_next_question("REVIEW_OF_SYSTEMS", "none")
    assert dm_ayush.current_state == "AYUSH_PRAKRITI"
    print(f"✔ AYUSH Branch -> Next: {dm_ayush.current_state} (Prakriti Assessment)")

    q, opts, is_final = dm_ayush.get_next_question("AYUSH_PRAKRITI", "vata_pitta")
    assert dm_ayush.current_state == "AYUSH_AGNI_KOSHTHA"
    print(f"✔ AYUSH Branch -> Next: {dm_ayush.current_state} (Agni & Koshtha)")

    q, opts, is_final = dm_ayush.get_next_question("AYUSH_AGNI_KOSHTHA", "samagni")
    assert dm_ayush.current_state == "COMPLETED"
    assert is_final is True
    print(f"✔ AYUSH Completed successfully!")

    # --------------------------------------------------------------------------
    # 4. RED FLAG EMERGENCY DETECTION (Halts Interview Immediately)
    # --------------------------------------------------------------------------
    print("\n--- Testing Red-Flag Emergency Halting ---")
    dm_rf = DialogueManager(language="hi", mode="ALLOPATHIC")
    dm_rf.start_interview()

    # Patient triggers: chest pain + difficulty breathing in Hindi
    critical_speech = "मुझे सीने में बहुत तेज दर्द है और सांस लेने में बहुत तकलीफ हो रही है"
    q_alert, opts_alert, is_final_alert = dm_rf.get_next_question("CHIEF_COMPLAINT", critical_speech)

    assert dm_rf.red_flag_triggered is True
    assert dm_rf.current_state == "RED_FLAG_HALTED"
    assert is_final_alert is True
    assert len(opts_alert) == 0
    assert "आपातकालीन चेतावनी" in q_alert
    assert dm_rf.red_flag_details is not None
    print(f"✔ Red-Flag Triggered: Category: {dm_rf.red_flag_details['category']}")
    print(f"✔ Interview halted immediately. Alert prompt: '{q_alert[:60]}...'")

    print("\n--- ALL DIALOGUE TESTS PASSED 100% ---")


if __name__ == "__main__":
    test_dialogue_manager_suite()

"""Finite State Machine Clinical Dialogue Manager for MediKiosk.

Orchestrates medical history taking across Allopathic (SOCRATES) and AYUSH
(Dashavidha Pariksha) workflows, red-flag emergency halting, and LLM entity extraction.
"""

from typing import Any, Dict, List, Optional, Tuple

try:
    from services.dialogue.llm_extractor import llm_extractor
    from services.dialogue.question_bank import QUESTION_BANK
    from services.dialogue.red_flags import check_clinical_red_flags
except ImportError:
    from .llm_extractor import llm_extractor
    from .question_bank import QUESTION_BANK
    from .red_flags import check_clinical_red_flags


class DialogueManager:
    """Clinical dialogue state engine with multimodal touch/voice support."""

    def __init__(self, language: str = "hi", mode: str = "ALLOPATHIC") -> None:
        """Initialize dialogue session.
        
        Args:
            language: 'hi' (Hindi), 'en' (English), 'ta' (Tamil).
            mode: 'ALLOPATHIC' or 'AYUSH'.
        """
        self.language = language.lower() if language.lower() in ("hi", "en", "ta") else "hi"
        self.is_ayush = mode.upper() == "AYUSH"
        self.current_state = "INIT"
        self.collected_data: Dict[str, Any] = {
            "chief_complaint": None,
            "is_pain": False,
            "hpi": {},
            "past_medical": [],
            "medications": [],
            "allergies": [],
            "family_history": [],
            "personal_history": [],
            "review_of_systems": [],
            "ayush_assessments": {},
        }
        self.red_flag_triggered = False
        self.red_flag_details: Optional[Dict[str, Any]] = None

    def start_interview(self) -> Tuple[str, List[Dict[str, str]], bool]:
        """Begin clinical interview with the open-ended chief complaint question."""
        self.current_state = "CHIEF_COMPLAINT"
        q_data = QUESTION_BANK["CHIEF_COMPLAINT"]
        question = q_data["question"].get(self.language, q_data["question"]["en"])
        options = self._format_options(q_data["touch_options"])
        return question, options, False

    def get_next_question(
        self, current_state: str, user_response: str
    ) -> Tuple[str, List[Dict[str, str]], bool]:
        """Advance dialogue state machine and return next question and touch options.
        
        Args:
            current_state: Current state of interview.
            user_response: Free-text voice transcription or touch option value.
            
        Returns:
            Tuple of: (question_text, touch_options_list, is_final)
        """
        self.current_state = current_state

        # 1. IMMEDIATE RED-FLAG CHECK
        is_rf, rf_info = check_clinical_red_flags(user_response)
        if is_rf:
            self.red_flag_triggered = True
            self.red_flag_details = rf_info
            self.current_state = "RED_FLAG_HALTED"
            
            emergency_prompts = {
                "en": "EMERGENCY ALERT: Your symptoms indicate an urgent medical emergency. Please remain seated; an emergency triage nurse has been alerted and is approaching your kiosk right now.",
                "hi": "आपातकालीन चेतावनी: आपके लक्षण गंभीर चिकित्सा स्थिति का संकेत देते हैं। कृपया यहीं बैठें; आपातकालीन नर्स को तुरंत सूचित कर दिया गया है और वह आपके पास आ रही हैं।",
                "ta": "அவசர எச்சரிக்கை: உங்கள் அறிகுறிகள் உடனடி மருத்துவ அவசரத்தைக் குறிக்கின்றன. தயவுசெய்து அமர்ந்திருங்கள்; அவசர சிகிச்சை செவிலியருக்கு தகவல் தெரிவிக்கப்பட்டு வருகிறது.",
            }
            emergency_msg = emergency_prompts.get(self.language, emergency_prompts["en"])
            return emergency_msg, [], True

        # 2. EXTRACT USER RESPONSE & UPDATE COLLECTED DATA
        self._record_user_response(current_state, user_response)

        # 3. DETERMINE NEXT STATE IN STATE MACHINE FLOW
        next_state = self._determine_next_state(current_state)
        self.current_state = next_state

        # 4. HANDLE FINAL COMPLETION STATE
        if next_state == "COMPLETED":
            completion_messages = {
                "en": "Thank you. Your clinical history has been successfully documented. Please collect your summary token and proceed to the triage desk.",
                "hi": "धन्यवाद! आपका नैदानिक इतिहास सफलतापूर्वक दर्ज कर लिया गया है। कृपया अपनी पर्ची लेकर परामर्श कक्ष में जाएं।",
                "ta": "நன்றி! உங்கள் மருத்துவ விவரங்கள் வெற்றிகரமாகப் பதிவு செய்யப்பட்டன. தயவுசெய்து உங்கள் டோக்கனைப் பெற்றுக்கொண்டு மருத்துவரை அணுகவும்.",
            }
            final_text = completion_messages.get(self.language, completion_messages["en"])
            return final_text, [], True

        # 5. RETRIEVE NEXT QUESTION & TOUCH CHIP OPTIONS
        q_data = QUESTION_BANK.get(next_state)
        if not q_data:
            return "Interview complete.", [], True

        question_text = q_data["question"].get(self.language, q_data["question"]["en"])
        options = self._format_options(q_data["touch_options"])
        return question_text, options, False

    def _determine_next_state(self, state: str) -> str:
        """State transition table enforcing clinical order and branching."""
        is_pain = self.collected_data.get("is_pain", False)

        if state == "CHIEF_COMPLAINT":
            return "HPI_DURATION"

        if state == "HPI_DURATION":
            # If symptom involves pain, route through SOCRATES character/radiation
            return "HPI_SOCRATES_CHARACTER" if is_pain else "HPI_SOCRATES_SEVERITY"

        if state == "HPI_SOCRATES_CHARACTER":
            return "HPI_SOCRATES_RADIATION"

        if state == "HPI_SOCRATES_RADIATION":
            return "HPI_SOCRATES_SEVERITY"

        if state == "HPI_SOCRATES_SEVERITY":
            return "PAST_MEDICAL_HISTORY"

        if state == "PAST_MEDICAL_HISTORY":
            return "DRUG_HISTORY"

        if state == "DRUG_HISTORY":
            return "ALLERGY_HISTORY"

        if state == "ALLERGY_HISTORY":
            return "FAMILY_HISTORY"

        if state == "FAMILY_HISTORY":
            return "PERSONAL_HISTORY"

        if state == "PERSONAL_HISTORY":
            return "REVIEW_OF_SYSTEMS"

        if state == "REVIEW_OF_SYSTEMS":
            # Branch to AYUSH Dashavidha Pariksha if requested
            return "AYUSH_PRAKRITI" if self.is_ayush else "COMPLETED"

        if state == "AYUSH_PRAKRITI":
            return "AYUSH_AGNI_KOSHTHA"

        if state == "AYUSH_AGNI_KOSHTHA":
            return "COMPLETED"

        return "COMPLETED"

    def _record_user_response(self, state: str, response: str) -> None:
        """Store extracted entities into clinical state representation."""
        resp = response.strip()

        if state == "CHIEF_COMPLAINT":
            parsed = llm_extractor.parse_chief_complaint(resp)
            self.collected_data["chief_complaint"] = parsed.get("complaint", resp)
            self.collected_data["is_pain"] = parsed.get("is_pain", False)
            self.collected_data["organ_system"] = parsed.get("organ_system", "General")

        elif state.startswith("HPI_"):
            self.collected_data["hpi"][state] = resp

        elif state == "PAST_MEDICAL_HISTORY":
            self.collected_data["past_medical"].append(resp)

        elif state == "DRUG_HISTORY":
            self.collected_data["medications"].append(resp)

        elif state == "ALLERGY_HISTORY":
            self.collected_data["allergies"].append(resp)

        elif state == "FAMILY_HISTORY":
            self.collected_data["family_history"].append(resp)

        elif state == "PERSONAL_HISTORY":
            self.collected_data["personal_history"].append(resp)

        elif state == "REVIEW_OF_SYSTEMS":
            self.collected_data["review_of_systems"].append(resp)

        elif state.startswith("AYUSH_"):
            self.collected_data["ayush_assessments"][state] = resp

    def _format_options(self, raw_options: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Format option dictionary into localized UI label and value pairs."""
        formatted = []
        for opt in raw_options:
            lbl_dict = opt.get("label", {})
            label = lbl_dict.get(self.language, lbl_dict.get("en", ""))
            formatted.append({"label": label, "value": opt.get("value", "")})
        return formatted

"""OpenAI gpt-4o-mini fast extractor for MediKiosk dialogue manager."""

import json
import logging
import re
from typing import Any, Dict, Optional

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    from config import settings
except ImportError:
    from ...config import settings

logger = logging.getLogger(__name__)


class LLMClinicalExtractor:
    """Fast, low-token extractor using OpenAI gpt-4o-mini for clinical entity parsing."""

    def __init__(self) -> None:
        self.api_key = settings.OPENAI_API_KEY
        self.model = settings.OPENAI_MODEL or "gpt-4o-mini"
        self.client = None

        if OpenAI and self.api_key and not self.api_key.startswith("mock_"):
            try:
                self.client = OpenAI(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI client ({e}). Using local extractor.")

    def parse_chief_complaint(self, text: str) -> Dict[str, Any]:
        """Extract chief complaint, determine if symptom involves pain, and gauge severity."""
        if not text or not text.strip():
            return {"complaint": "Unknown", "is_pain": False, "duration": None}

        # Attempt OpenAI fast extraction with gpt-4o-mini (low token limit)
        if self.client:
            try:
                prompt = (
                    "Extract clinical chief complaint from this Indian hospital patient response. "
                    "Return ONLY a JSON object with keys: 'complaint' (short English string), "
                    "'is_pain' (boolean), 'organ_system' (Cardiovascular/Respiratory/GI/Musculoskeletal/Other). "
                    f"Patient input: \"{text}\""
                )
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a clinical NLP extractor. Respond with concise JSON only."},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=100,
                    temperature=0.0,
                    stream=False,
                    timeout=4.0,
                )
                if hasattr(response, "choices") and response.choices:
                    content = response.choices[0].message.content
                    if content:
                        return json.loads(content)
            except Exception as e:
                logger.warning(f"OpenAI extraction failed ({e}), falling back to heuristic parsing.")

        # Resilient Local Rule-based Fallback
        lower = text.lower()
        pain_keywords = ["pain", "dard", "दर्द", "vali", "வலி", "ache", "pressure", "heavy", "भारीपन", "stabbing", "चुभन"]
        is_pain = any(k in lower for k in pain_keywords)

        organ = "General"
        if any(k in lower for k in ["chest", "सीने", "छाती", "दिल", "heart"]):
            organ = "Cardiovascular"
        elif any(k in lower for k in ["stomach", "पेट", "abdomen", "gas"]):
            organ = "Gastrointestinal"
        elif any(k in lower for k in ["breath", "सांस", "cough", "खांसी"]):
            organ = "Respiratory"
        elif any(k in lower for k in ["joint", "knee", "कमर", "जोड़", "body"]):
            organ = "Musculoskeletal"

        return {
            "complaint": text.strip(),
            "is_pain": is_pain,
            "organ_system": organ,
        }

    def summarize_section_response(self, section: str, user_response: str) -> Dict[str, Any]:
        """Convert patient free-text speech into standardized medical section entities."""
        return {
            "section": section,
            "raw_response": user_response,
            "extracted_values": [user_response.strip()],
        }


llm_extractor = LLMClinicalExtractor()

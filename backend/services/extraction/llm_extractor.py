"""OpenAI and Pre-trained Model Clinical Entity Extractor for MediKiosk.

Calls OpenAI gpt-4o-mini (or fine-tuned local medical BERT/scispaCy in production)
to extract clinical entities into a structured JSON schema.
"""

import json
import logging
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


class LLMEntityExtractor:
    """Extracts clinical entities using OpenAI or pre-trained medical model."""

    def __init__(self) -> None:
        self.api_key = settings.OPENAI_API_KEY
        self.model = settings.OPENAI_MODEL or "gpt-4o-mini"
        self.client = None

        if OpenAI and self.api_key and not self.api_key.startswith("mock_"):
            try:
                self.client = OpenAI(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"OpenAI client initialization failed ({e}).")

    def extract_with_llm(self, text: str) -> Optional[Dict[str, Any]]:
        """Call OpenAI API to extract structured clinical entities."""
        if not self.client or not text or not text.strip():
            return None

        prompt = (
            "Extract clinical entities from this hospital medical document/prescription text. "
            "Return ONLY a valid JSON object matching this schema:\n"
            "{\n"
            '  "diagnoses": [{"name": str, "icd10_code": str, "icd10_title": str, "confidence": float}],\n'
            '  "medications": [{"name": str, "dosage": str, "frequency": str, "duration": str, "confidence": float}],\n'
            '  "laboratory_results": [{"test_name": str, "value": str, "unit": str, "reference_range": str, "confidence": float}],\n'
            '  "procedures": [{"name": str, "confidence": float}],\n'
            '  "allergies": [{"allergen": str, "reaction": str, "confidence": float}],\n'
            '  "dates": [{"date_string": str, "context": str, "confidence": float}]\n'
            "}\n"
            f'Clinical Text: """{text[:1500]}"""'
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a clinical NLP entity extraction engine. Extract medical entities accurately and assign ICD-10 codes where applicable. Output JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=800,
                temperature=0.0,
                stream=False,
                timeout=8.0,
            )
            if hasattr(response, "choices") and response.choices:
                content = response.choices[0].message.content
                if content:
                    return json.loads(content)
        except Exception as e:
            logger.warning(f"LLM clinical extraction error ({e}). Using regex fallback.")

        return None

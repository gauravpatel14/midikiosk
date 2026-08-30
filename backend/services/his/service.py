"""HIS Integration Service and Factory for MediKiosk.

Loads configuration from his_config.json and routes transmissions
to the designated HISAdapter (FHIR, HL7 v2, Webhook, or Mock).
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from services.his.adapters import FHIRHISAdapter, HL7v2HISAdapter, MockHISAdapter, WebhookHISAdapter
    from services.his.base import HISAdapter
except ImportError:
    from .adapters import FHIRHISAdapter, HL7v2HISAdapter, MockHISAdapter, WebhookHISAdapter
    from .base import HISAdapter

logger = logging.getLogger(__name__)


class HISIntegrationService:
    """Central dispatch service for Hospital Information System connectivity."""

    def __init__(self, config_path: Optional[str] = None) -> None:
        self.config_path = config_path or str(Path(__file__).resolve().parent.parent / "his_config.json")
        self.config = self._load_config()
        self.active_adapter_name = self.config.get("active_adapter", "mock")
        self.adapter: HISAdapter = self._initialize_adapter(self.active_adapter_name)

    def _load_config(self) -> Dict[str, Any]:
        """Load HIS configuration file if present."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error reading his_config.json ({e}). Using defaults.")
        return {"active_adapter": "mock"}

    def _initialize_adapter(self, adapter_name: str) -> HISAdapter:
        """Factory method to instantiate the requested HIS adapter."""
        name = adapter_name.lower()

        if name == "fhir":
            cfg = self.config.get("fhir", {})
            return FHIRHISAdapter(
                endpoint_url=cfg.get("endpoint_url", "https://his.hospital.org/fhir/r4"),
                auth_token=cfg.get("token"),
            )
        elif name == "hl7v2":
            cfg = self.config.get("hl7v2", {})
            return HL7v2HISAdapter(
                host=cfg.get("host", "127.0.0.1"),
                port=cfg.get("port", 2575),
                sending_app=cfg.get("sending_app", "MEDIKIOSK"),
                sending_facility=cfg.get("sending_facility", "AIIA_OPD"),
            )
        elif name == "webhook":
            cfg = self.config.get("webhook", {})
            return WebhookHISAdapter(
                webhook_url=cfg.get("url", "https://his.hospital.org/api/v1/clinical-notes"),
                secret_key=cfg.get("secret_key", "medikiosk_secret"),
            )
        else:
            return MockHISAdapter()

    def set_adapter(self, adapter_name: str) -> None:
        """Hot-swap the active HIS adapter dynamically."""
        self.active_adapter_name = adapter_name.lower()
        self.adapter = self._initialize_adapter(self.active_adapter_name)

    def send_summary(
        self,
        patient_id: str,
        summary: Dict[str, Any],
        documents: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Dispatch clinical summary to the configured hospital information system."""
        return self.adapter.send_summary(patient_id, summary, documents)


# Singleton instance
his_service = HISIntegrationService()

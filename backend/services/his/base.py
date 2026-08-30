"""Hospital Information System (HIS) Adapter Interface for MediKiosk.

Defines the abstract interface for dispatching clinical summaries and documents
to hospital EMR systems via FHIR R4, HL7 v2, or Webhooks.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class HISAdapter(ABC):
    """Abstract Base Class for Hospital Information System integration adapters."""

    @abstractmethod
    def send_summary(
        self,
        patient_id: str,
        summary: Dict[str, Any],
        documents: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Dispatch clinical summary and scanned documents to the hospital system.
        
        Args:
            patient_id: Unique hospital patient ID or ABHA ID.
            summary: Dictionary containing structured clinical history & summary texts.
            documents: Optional list of scanned document metadata and file pointers.
            
        Returns:
            Dict containing reception status, transmission receipt ID, and acknowledgment.
        """
        pass

"""
Storage adapter interface for document persistence.

Each adapter stores/loads document snapshots. The document layer uses
an adapter (if attached) to persist every mutation and to reload
documents across server restarts.

The adapter interface is generic enough for file, S3, Postgres, etc.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict
from typing import Any


class StorageAdapter(ABC):
    """Interface for document storage backends.

    Each document is stored as a dict with keys:
      - document: DocumentNode as dict
      - elements: {element_id: ElementNode as dict}
      - metadata: {created, updated, version, ...}
    """

    @abstractmethod
    def save(self, doc_id: str, data: dict[str, Any]) -> bool:
        """Persist a document snapshot. Returns True on success."""
        ...

    @abstractmethod
    def load(self, doc_id: str) -> dict[str, Any] | None:
        """Load a document snapshot. Returns None if not found."""
        ...

    @abstractmethod
    def delete(self, doc_id: str) -> bool:
        """Delete a document. Returns True if deleted."""
        ...

    @abstractmethod
    def list_documents(self) -> list[dict[str, Any]]:
        """Return summary of all stored documents (id, name, version, updated)."""
        ...

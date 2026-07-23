"""Storage adapters for document persistence."""

from avge_engine.storage.adapter import StorageAdapter
from avge_engine.storage.file_adapter import FileStorageAdapter

__all__ = ["StorageAdapter", "FileStorageAdapter"]

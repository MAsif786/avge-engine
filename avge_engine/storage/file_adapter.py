"""
File-based storage adapter — saves documents as JSON files on disk.

Each document is a .json file named <doc_id>.json in a storage directory.
Includes document metadata and all regions as serializable dicts.

Supports hot-reload: saves every mutation, loads on demand.
Uses atomic writes (write to .tmp → rename) to prevent race conditions
when MCP and API servers access the same file concurrently.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from avge_engine.storage.adapter import StorageAdapter
from avge_engine.storage.compact import decode_snapshot, encode_snapshot


class FileStorageAdapter(StorageAdapter):
    """Store documents as JSON files in a directory."""

    def __init__(self, directory: str = ".avge_data") -> None:
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, doc_id: str) -> Path:
        return self._dir / f"{doc_id}.json"

    def save(self, doc_id: str, data: dict[str, Any]) -> bool:
        """Atomically serialize document dict to a JSON file.

        Writes to a temporary file then renames (atomic on POSIX)
        to prevent partial reads from concurrent processes.
        """
        path = self._path(doc_id)
        serializable = _make_serializable(data)
        try:
            compact = encode_snapshot(serializable)
            content = json.dumps(compact, separators=(",", ":"), default=str)
            fd, tmp_path = tempfile.mkstemp(dir=self._dir, suffix=".tmp")
            try:
                with os.fdopen(fd, "w") as f:
                    f.write(content)
                os.replace(tmp_path, path)
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
            return True
        except (OSError, TypeError) as e:
            print(f"[FileStorage] Save error {doc_id}: {e}")
            return False

    def load(self, doc_id: str) -> dict[str, Any] | None:
        """Load a document from its JSON file.

        Returns the decoded dict or None if file doesn't exist.
        """
        path = self._path(doc_id)
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text())
            return decode_snapshot(raw)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[FileStorage] Load error {doc_id}: {e}")
            return None

    def delete(self, doc_id: str) -> bool:
        """Delete a document file."""
        path = self._path(doc_id)
        if not path.exists():
            return False
        path.unlink()
        return True

    def list_documents(self) -> list[dict[str, Any]]:
        """Scan the storage directory and return summaries of all documents."""
        results: list[dict[str, Any]] = []
        for path in sorted(self._dir.glob("doc_*.json")):
            try:
                data = json.loads(path.read_text())
                doc = data.get("document", {})
                meta = data.get("metadata", {})
                results.append({
                    "id": doc.get("id", path.stem),
                    "name": doc.get("name", ""),
                    "version": doc.get("version", 0),
                    "region_count": len(data.get("regions", {})),
                    "updated": meta.get("updated", ""),
                    "storage_format": meta.get("storage_format", "legacy"),
                })
            except (json.JSONDecodeError, OSError):
                continue
        return results


def _make_serializable(obj: Any) -> Any:
    """Recursively convert dataclasses and tuples to JSON-serializable forms."""
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _make_serializable(v) for k, v in obj.__dict__.items()}
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_serializable(v) for v in obj]
    if isinstance(obj, float):
        return obj
    return obj

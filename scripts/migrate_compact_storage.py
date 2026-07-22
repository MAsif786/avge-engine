#!/usr/bin/env python3
"""Rewrite AVGE JSON documents into the compact storage format.

Dry-run is the default. Pass --write to update files in place.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from avge_engine.storage.compact import decode_snapshot, encode_snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "directory",
        nargs="?",
        default=".avge_data",
        help="Directory containing doc_*.json files.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Rewrite files in place. Omit for dry-run size report.",
    )
    parser.add_argument(
        "--doc-id",
        help="Migrate only one document ID, for example doc_123.",
    )
    args = parser.parse_args()

    directory = Path(args.directory)
    if not directory.exists():
        parser.error(f"directory not found: {directory}")

    total_old = 0
    total_new = 0
    count = 0
    paths = [directory / f"{args.doc_id}.json"] if args.doc_id else sorted(directory.glob("doc_*.json"))
    for path in paths:
        if not path.exists():
            print(f"skip {path.name}: file not found")
            continue
        try:
            old_bytes = path.read_bytes()
            data = json.loads(old_bytes)
            data = decode_snapshot(data)
            compact = encode_snapshot(data)
            new_bytes = json.dumps(compact, separators=(",", ":"), default=str).encode()
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            print(f"skip {path.name}: {exc}")
            continue

        total_old += len(old_bytes)
        total_new += len(new_bytes)
        count += 1
        delta = len(new_bytes) - len(old_bytes)
        print(f"{path.name}: {len(old_bytes)} -> {len(new_bytes)} bytes ({delta:+d})")

        if args.write:
            _atomic_write(path, new_bytes)

    if count:
        saved = total_old - total_new
        pct = saved / total_old * 100 if total_old else 0
        mode = "rewrote" if args.write else "dry-run"
        print(f"{mode}: {count} docs, {total_old} -> {total_new} bytes, saved {saved} ({pct:.1f}%)")
    else:
        print("No documents found.")
    return 0


def _atomic_write(path: Path, content: bytes) -> None:
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


if __name__ == "__main__":
    raise SystemExit(main())

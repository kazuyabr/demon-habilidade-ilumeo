"""Local filesystem DocumentStorage adapter.

Keeps uploaded files under ``UPLOAD_DIR`` keyed by hash to dedupe content
(idempotency) and avoid path traversal. S3/GCS would implement the same port.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from risklens.core.config import settings


class FsDocumentStorage:
    def __init__(self, root: str | None = None) -> None:
        self.root = Path(root or settings.upload_dir).resolve()

    async def save(self, filename: str, data: bytes) -> str:
        digest = hashlib.sha256(data).hexdigest()
        ext = Path(filename).suffix.lower() or ".bin"
        rel = Path(f"{digest[:2]}/{digest}{ext}")
        target = self.root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return str(rel).replace("\\", "/")

    async def read(self, storage_path: str) -> bytes:
        path = self._safe(storage_path)
        return path.read_bytes()

    async def delete(self, storage_path: str) -> None:
        path = self._safe(storage_path)
        if path.exists():
            path.unlink()

    def _safe(self, storage_path: str) -> Path:
        candidate = (self.root / storage_path).resolve()
        if not candidate.is_relative_to(self.root):
            raise ValueError("invalid storage path")
        return candidate

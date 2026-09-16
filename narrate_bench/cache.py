"""Content-hash cache: ContentCache.key/has/path/write_atomic."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Callable


class ContentCache:
    def __init__(self, root: Path):
        self.root = Path(root)

    def key(
        self,
        stage: str,
        engine_id: str,
        voice_id: str,
        params: dict,
        model_version: str,
        chunk_id: str,
    ) -> str:
        payload = stage + engine_id + voice_id + json.dumps(params, sort_keys=True) + model_version + chunk_id
        return hashlib.sha256(payload.encode()).hexdigest()

    def path(self, key: str) -> Path:
        return self.root / key[:2] / key

    def has(self, key: str) -> bool:
        return self.path(key).exists()

    def write_atomic(self, key: str, producer: Callable[[Path], None]) -> Path:
        final_path = self.path(key)
        tmp_path = final_path.with_suffix(final_path.suffix + ".tmp")
        final_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            producer(tmp_path)
            os.replace(tmp_path, final_path)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()
        return final_path

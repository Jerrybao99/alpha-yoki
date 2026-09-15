"""锐评本地缓存：事实 + 提示词版本 + Provider/模型 的 SHA-1 指纹 → data/cache/review/<sha>.json。
只缓存校验通过的结果；损坏或不完整的条目一律视为未命中。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from src.llm.contracts import REVIEW_FIELDS, ReviewFacts, ReviewResult, ReviewStatus


class FileReviewCache:
    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    @property
    def root(self) -> Path:
        return self._root

    def key(self, facts: ReviewFacts, prompt_version: str, provider: str, model: str) -> str:
        payload = {
            "facts": facts.to_dict(),
            "prompt_version": prompt_version,
            "provider": provider,
            "model": model,
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha1(encoded.encode("utf-8")).hexdigest()

    def _path(self, key: str) -> Path:
        return self._root / f"{key}.json"

    def get(self, key: str) -> ReviewResult | None:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            payload: Any = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict) or not all(isinstance(payload.get(field), str) for field in REVIEW_FIELDS):
            return None
        try:
            status = ReviewStatus(str(payload.get("status", ReviewStatus.SUCCESS)))
        except ValueError:
            status = ReviewStatus.SUCCESS
        return ReviewResult(
            highlight=payload["highlight"],
            risk=payload["risk"],
            comment=payload["comment"],
            status=status,
            provider=str(payload.get("provider", "")),
            model=str(payload.get("model", "")),
            attempts=int(payload.get("attempts", 0) or 0),
        )

    def put(self, key: str, result: ReviewResult) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        payload = {
            "highlight": result.highlight,
            "risk": result.risk,
            "comment": result.comment,
            "status": result.status.value,
            "provider": result.provider,
            "model": result.model,
            "attempts": result.attempts,
        }
        self._path(key).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

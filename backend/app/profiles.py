from __future__ import annotations

import json
from pathlib import Path

from .schemas import AccessibilityProfile


DEFAULT_PROFILE_PATH = Path(__file__).resolve().parent / "config" / "profiles.json"


class ProfileRegistry:
    def __init__(self, path: Path = DEFAULT_PROFILE_PATH) -> None:
        raw = json.loads(path.read_text(encoding="utf-8"))
        self._profiles = {
            name: AccessibilityProfile.model_validate(value)
            for name, value in raw.items()
        }

    def get(self, name: str) -> AccessibilityProfile:
        try:
            return self._profiles[name]
        except KeyError as exc:
            raise ValueError(f"지원하지 않는 접근성 프로필입니다: {name}") from exc

    def all(self) -> list[AccessibilityProfile]:
        return list(self._profiles.values())


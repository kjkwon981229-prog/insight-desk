from __future__ import annotations

import json
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Mapping


def _default_interest_base() -> dict[str, int]:
    return {
        "baseball_sabermetrics": 3,
        "ai_tech": 3,
        "design_color_type": 3,
        "kpop": 3,
        "contest_benefits": 3,
        "kbo_hanwha": 2,
        "economy": 2,
        "psat_recruitment": 2,
    }


def _default_pass_overrides() -> dict[str, float]:
    # 한화 소식은 "가끔, 점수가 높을 때만" 보여 준다(명세 9-3).
    return {"kbo_hanwha": 8.0}


@dataclass(frozen=True, slots=True)
class CurationConfig:
    pass_score: float = 7.0
    max_daily: int = 5
    max_per_topic: int = 2
    dedup_days: int = 7
    dedup_jaccard: float = 0.6
    min_body_chars: int = 300
    feedback_min: float = -2.0
    feedback_max: float = 1.0
    interest_base: Mapping[str, int] = field(default_factory=_default_interest_base)
    pass_score_overrides: Mapping[str, float] = field(default_factory=_default_pass_overrides)

    def pass_score_for(self, topic_id: str) -> float:
        return float(self.pass_score_overrides.get(topic_id, self.pass_score))


# 기록 재생·구조 시험은 "예전 파이프라인의 동작"을 보는 것이므로 선별 기준을 끈 설정으로 돌린다.
# (실제 발행은 항상 config/curation.json을 쓴다.)
REPLAY_CURATION_JSON: dict[str, object] = {
    "pass_score": 0.0,
    "max_daily": 99,
    "max_per_topic": 99,
    "min_body_chars": 0,
    "pass_score_overrides": {},
}

_VALID_KEYS = frozenset(item.name for item in fields(CurationConfig))


def load_curation_config(path: Path | None) -> CurationConfig:
    if path is None or not path.exists():
        return CurationConfig()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("config must be a JSON object")
    unknown = set(data.keys()) - _VALID_KEYS
    if unknown:
        raise ValueError(f"unknown config keys: {sorted(unknown)}")
    return CurationConfig(**data)

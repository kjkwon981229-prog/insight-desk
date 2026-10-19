from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from .config import CurationConfig
from .history import SeenHistory
from .text import content_words


CONTEST_REASONS = (
    "contest_deadline_passed",
    "contest_deadline_under_7d",
    "contest_ineligible",
    "benefit_costs_money",
    "contest_unverified",
    "contest_not_related",
)

_AD_KEYWORDS = ("광고", "협찬", "홍보")
_AD_PHRASES = ("최저가", "쿠폰", "할인코드", "제휴 링크", "수수료를 지급", "구매 링크", "파트너스 활동")
_CLICKBAIT_PHRASES = ("충격", "경악", "알고 보니", "결국 터졌다", "이럴 수가", "난리 난", "대박", "소름", "?!", "…?")
# 낚시 문구 자체의 낱말은 제목-본문 어휘 비교에서 뺀다(꾸밈말이므로 본문에 없어도 정상).
_CLICKBAIT_TOKENS = content_words(" ".join(_CLICKBAIT_PHRASES))


@dataclass(frozen=True, slots=True)
class FilterResult:
    rejected: bool
    reason: str | None


def apply_hard_filters(
    *,
    title: str,
    body: str,
    url: str,
    topic_id: str,
    negative_context: Sequence[str],
    history: SeenHistory,
    now: datetime,
    cfg: CurationConfig,
) -> FilterResult:
    if not url.startswith(("http://", "https://")):
        return FilterResult(rejected=True, reason="no_source")

    body_stripped = "".join(body.split())
    if len(body_stripped) < cfg.min_body_chars:
        return FilterResult(rejected=True, reason="thin_content")

    combined = title + " " + body
    for phrase in _AD_PHRASES:
        if phrase in combined:
            return FilterResult(rejected=True, reason="ad_sponsored")

    ad_ctx_items: list[str] = []
    other_ctx_items: list[str] = []
    for ctx in negative_context:
        if any(kw in ctx for kw in _AD_KEYWORDS):
            ad_ctx_items.append(ctx)
        else:
            other_ctx_items.append(ctx)

    for ctx in ad_ctx_items:
        if ctx in title:
            return FilterResult(rejected=True, reason="ad_sponsored")
        if body.count(ctx) >= 2:
            return FilterResult(rejected=True, reason="ad_sponsored")

    for ctx in other_ctx_items:
        if ctx in title:
            return FilterResult(rejected=True, reason="ad_sponsored")

    title_words = content_words(title) - _CLICKBAIT_TOKENS
    if len(title_words) >= 2:
        body_words = content_words(body)
        if body_words:
            overlap = len(title_words & body_words)
            ratio = overlap / len(title_words)
        else:
            ratio = 0.0
        has_clickbait = any(p in title for p in _CLICKBAIT_PHRASES)
        if ratio < 0.4 and has_clickbait:
            return FilterResult(rejected=True, reason="clickbait")

    if history.is_duplicate(
        topic_id=topic_id,
        title=title,
        now=now,
        days=cfg.dedup_days,
        jaccard_threshold=cfg.dedup_jaccard,
    ):
        return FilterResult(rejected=True, reason="duplicate_7d")

    return FilterResult(rejected=False, reason=None)

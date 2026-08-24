from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urlparse


MAX_HEADLINE_CHARS = 120
MAX_SUMMARY_CHARS = 420
PSAT_TOPIC = "PSAT·공채 일정"
KBO_HANWHA_TOPIC = "KBO·한화 이글스"
KPOP_TOPIC = "엔터·음악·K-POP"
PSAT_FORBIDDEN = (
    "Preparatory Student Academic",
    "PSAT 아카데미",
    "NCAA",
)
_HANWHA_TOPIC_TERMS = ("한화", "한화 이글스")
_KBO_HEADLINE_SCOPE_CUES = ("한화", "KBO", "프로야구")
_KBO_ENTERTAINMENT_ENTITY_CUES = ("그룹", "아이돌", "멤버", "가수", "배우")
_KBO_ENTERTAINMENT_ACTION_CUES = ("승리 요정", "시구", "시타")
_KPOP_HEADLINE_SCOPE_CUES = (
    "K-POP",
    "케이팝",
    "가수",
    "그룹",
    "아이돌",
    "앨범",
    "음원",
    "차트",
    "음악",
    "뮤직",
    "음반",
    "컴백",
    "데뷔",
    "콘서트",
    "공연",
    "무대",
    "수상",
    "빌보드",
    "Billboard",
    "HYBE",
    "하이브",
    "SM",
    "JYP",
    "YG",
    "BTS",
    "방탄소년단",
    "블랙핑크",
    "아이브",
    "뉴진스",
    "세븐틴",
)
_CONTEXT_DEPENDENT_SUMMARY_LEADS = (
    "여기에 ",
    "여기에,",
    "이후 ",
    "이 딜러는 ",
    "이번 ",
    "팬들의 ",
)
_CONTEXT_DEPENDENT_SUMMARY_PHRASES = ("이번 상황",)
_BARE_ANNIVERSARY_LEAD_RE = re.compile(r"^데뷔\s+\d+\s*주년을\s+맞은\s+가운데(?:\s|$)")
_BARE_RANKING_CUES = ("최고의 루키",)
_BARE_RANKING_CONTEXT_TERMS = (
    "K탑스타",
    "KTOPSTAR",
    "투표",
    "랭킹",
    "차트",
    "부문",
    "시상식",
    "어워드",
    "수상",
)
_NON_EVENT_ANALYTICAL_ENDINGS = (
    "설명하기 어렵다",
    "설명하기 힘들다",
    "것으로 보인다",
    "것으로 보입니다",
    "것으로 풀이된다",
    "것으로 풀이됩니다",
)
_NON_EVENT_ATTENTION_ENDINGS = (
    "관심이 쏠리고 있다",
    "관심이 쏠리고 있습니다",
    "관심이 모이고 있다",
    "관심이 모이고 있습니다",
    "주목을 받고 있다",
    "주목받고 있다",
)
_EVALUATIVE_CONDITION_MARKERS = ("해야", "돼야", "되어야")
_EVALUATIVE_CONDITION_ENDINGS = (
    "가능하다고 봤다",
    "필요하다고 봤다",
    "가능하다고 평가했다",
    "필요하다고 평가했다",
    "의미가 있다고 봤다",
)
_DESCRIPTIVE_ATTRIBUTE_CUES = (
    "장르",
    "사운드",
    "스타일",
    "분위기",
    "매력",
    "탑라인",
    "트랙",
    "색채",
    "특징",
)
_DESCRIPTIVE_PREDICATE_CUES = (
    "대비를 이루",
    "은유한다",
    "표현한다",
    "보여준다",
    "담아낸다",
    "결합한",
    "특징이다",
)
_CONCRETE_EVENT_PREDICATE_CUES = (
    "발매했다",
    "공개했다",
    "개최했다",
    "출시했다",
    "체결했다",
    "수주했다",
    "선정됐다",
    "수상했다",
    "승리했다",
    "발표했다",
    "밝혔다",
    "확정했다",
    "도입했다",
    "시행했다",
    "데뷔했다",
)
_CONDITIONAL_EVENT_CUES = (
    "발표",
    "밝혔다",
    "결정",
    "도입",
    "시행",
    "공개",
    "추진",
    "합의",
    "체결",
    "승인",
    "확정",
)
_STALE_DATE_CONTEXT_CUES = ("공개된", "열린", "개최된", "진행된", "발표된", "출시된", "방송된")
_SPORTS_CONTEXT_CUES = ("경기에서", "전에서", "경기 중", "경기에")
_STALE_SPORTS_RETROSPECTIVE_ENDINGS = ("나왔다", "벌어졌다", "기록됐다", "기록되었다")
_PAST_YEAR_BACKGROUND_CUES = ("부터", "이후", "이래")
_CURRENT_EVENT_CUES = ("올해", "오늘", "현재", "최근")
_SENTENCE_TERMINALS = ".!?。！？"
_YEAR_RE = re.compile(r"(?<!\d)(20\d{2})년")
_MONTH_DAY_RE = re.compile(r"(?<!\d)(?:(20\d{2})년\s*)?(1[0-2]|0?[1-9])월\s*([0-2]?\d|3[01])일")
_CONDITIONAL_SCENARIO_RE = re.compile(r"\s(?:경우|시)\s")
_URL_DATE_RE = re.compile(r"(?<!\d)(20\d{2})(0[1-9]|1[0-2])([0-2]\d|3[01])")
_DATE_LED_SUBJECTLESS_SPORTS_RESULT_RE = re.compile(
    r"^(?:지난\s+)?\d{1,2}일\s+[^,.]{0,60}?(?:경기|전)에서\s+\d+\s*(?:타수|이닝|분|경기)\b"
)


def _classes(attrs: list[tuple[str, str | None]]) -> set[str]:
    value = dict(attrs).get("class") or ""
    return set(value.split())


def _normalize(value: str) -> str:
    return " ".join(value.split()).casefold()


def _sentence_identity(value: str) -> str:
    return _normalize(value).rstrip(_SENTENCE_TERMINALS).rstrip()


def _bare_ranking_fragment(value: str) -> bool:
    normalized = " ".join(value.split())
    has_bare_ranking = (
        any(cue in normalized for cue in _BARE_RANKING_CUES)
        or re.search(r"\d+\s*주\s*연속\s*1위", normalized) is not None
    )
    if not has_bare_ranking:
        return False
    folded = normalized.casefold()
    return not any(term.casefold() in folded for term in _BARE_RANKING_CONTEXT_TERMS)


def _context_dependent_summary(value: str) -> bool:
    normalized = " ".join(value.split())
    if any(normalized.startswith(cue) for cue in _CONTEXT_DEPENDENT_SUMMARY_LEADS):
        return True
    if any(phrase in normalized for phrase in _CONTEXT_DEPENDENT_SUMMARY_PHRASES):
        return True
    if _BARE_ANNIVERSARY_LEAD_RE.search(normalized) is not None:
        return True
    if _DATE_LED_SUBJECTLESS_SPORTS_RESULT_RE.search(normalized) is not None:
        return True
    return _bare_ranking_fragment(normalized)


def _non_event_analytical_summary(value: str) -> bool:
    normalized = " ".join(value.split()).rstrip(_SENTENCE_TERMINALS).rstrip()
    if normalized.endswith(_NON_EVENT_ANALYTICAL_ENDINGS):
        return True
    if normalized.endswith(_NON_EVENT_ATTENTION_ENDINGS):
        return True
    if (
        any(marker in normalized for marker in _EVALUATIVE_CONDITION_MARKERS)
        and normalized.endswith(_EVALUATIVE_CONDITION_ENDINGS)
    ):
        return True
    return (
        any(cue in normalized for cue in _DESCRIPTIVE_ATTRIBUTE_CUES)
        and any(cue in normalized for cue in _DESCRIPTIVE_PREDICATE_CUES)
        and not any(cue in normalized for cue in _CONCRETE_EVENT_PREDICATE_CUES)
    )


def _conditional_analytical_summary(value: str) -> bool:
    normalized = " ".join(value.split())
    has_reporting_event = any(cue in normalized for cue in _CONDITIONAL_EVENT_CUES)
    if "더라도" in normalized and "이어야" in normalized:
        return not has_reporting_event
    if _CONDITIONAL_SCENARIO_RE.search(normalized) is None:
        return False
    return not has_reporting_event


def _stale_sports_retrospective_summary(value: str) -> bool:
    normalized = " ".join(value.split())
    years = [int(item) for item in _YEAR_RE.findall(normalized)]
    if not years or not any(year < datetime.now(timezone.utc).year for year in years):
        return False
    if not any(cue in normalized for cue in _SPORTS_CONTEXT_CUES):
        return False
    if "장면" not in normalized and "기록" not in normalized:
        return False
    terminal_stripped = normalized.rstrip(_SENTENCE_TERMINALS).rstrip()
    return terminal_stripped.endswith(_STALE_SPORTS_RETROSPECTIVE_ENDINGS)


def _stale_explicit_past_year_summary(value: str) -> bool:
    normalized = " ".join(value.split())
    match = _YEAR_RE.match(normalized)
    if match is None:
        return False
    now_year = datetime.now(timezone.utc).year
    if int(match.group(1)) >= now_year:
        return False
    if f"{now_year}년" in normalized or any(cue in normalized for cue in _CURRENT_EVENT_CUES):
        return False
    following = normalized[match.end() : match.end() + 8].lstrip()
    return not any(following.startswith(cue) for cue in _PAST_YEAR_BACKGROUND_CUES)


def _stale_dated_context_summary(value: str) -> bool:
    if _stale_sports_retrospective_summary(value):
        return False
    if _stale_explicit_past_year_summary(value):
        return True
    normalized = " ".join(value.split())
    now = datetime.now(timezone.utc)
    for match in _MONTH_DAY_RE.finditer(normalized):
        if match.start() > 32:
            continue
        year_text, month_text, day_text = match.groups()
        year = int(year_text) if year_text is not None else now.year
        try:
            candidate = datetime(year, int(month_text), int(day_text), tzinfo=timezone.utc)
        except ValueError:
            continue
        if year_text is None and candidate > now:
            try:
                candidate = candidate.replace(year=year - 1)
            except ValueError:
                continue
        if (now - candidate).total_seconds() <= 72 * 60 * 60:
            continue
        tail = normalized[match.end() : match.end() + 24]
        if any(cue in tail for cue in _STALE_DATE_CONTEXT_CUES):
            return True
    return False


def _stale_source_url(value: str) -> bool:
    parsed = urlparse(value)
    haystack = f"{parsed.path}?{parsed.query}"
    today = datetime.now(timezone.utc).date()
    for match in _URL_DATE_RE.finditer(haystack):
        try:
            candidate = date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            continue
        if (today - candidate).days > 3:
            return True
    return False


class FeedParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stories: list[dict[str, str]] = []
        self._story: dict[str, str] | None = None
        self._field: str | None = None
        self._field_depth = 0
        self._story_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        classes = _classes(attrs)
        attributes = dict(attrs)
        if self._story is None and tag == "article" and "story-row" in classes:
            self._story = {
                "event_id": attributes.get("data-event-id") or "",
                "topic": "",
                "headline": "",
                "summary": "",
            }
            self._story_depth = 1
            return
        if self._story is None:
            return
        self._story_depth += 1
        if self._field is not None:
            self._field_depth += 1
            return
        if tag == "h3":
            self._field = "headline"
            self._field_depth = 1
        elif tag == "p" and "story-summary" in classes:
            self._field = "summary"
            self._field_depth = 1
        elif tag == "span" and "story-topic" in classes:
            self._field = "topic"
            self._field_depth = 1

    def handle_endtag(self, tag: str) -> None:
        if self._story is None:
            return
        if self._field is not None:
            self._field_depth -= 1
            if self._field_depth == 0:
                self._field = None
        self._story_depth -= 1
        if self._story_depth == 0:
            self.stories.append(self._story)
            self._story = None
            self._field = None
            self._field_depth = 0

    def handle_data(self, data: str) -> None:
        if self._story is not None and self._field is not None:
            self._story[self._field] += data


def _validate_source_audit(
    stories: list[dict[str, str]],
    source_audit: dict[str, object],
) -> tuple[int, int, int]:
    rendered_sources = source_audit.get("rendered_sources")
    if not isinstance(rendered_sources, list):
        raise ValueError("FEED_QUALITY_SOURCE_AUDIT_MISSING")
    html_event_ids = [story["event_id"].strip() for story in stories]
    audit_event_ids: list[str] = []
    seen_source_groups: set[str] = set()
    seen_content: set[str] = set()
    invalid_source_url_indices: list[int] = []
    stale_source_url_indices: list[int] = []
    duplicate_sources = 0
    duplicate_source_content = 0
    for index, item in enumerate(rendered_sources, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"FEED_QUALITY_SOURCE_AUDIT_INVALID:{index}")
        event_id = str(item.get("event_id") or "").strip()
        source_group_key = str(item.get("source_group_key") or "").strip()
        content_sha256 = str(item.get("content_sha256") or "").strip()
        source_url = str(item.get("source_url") or "").strip()
        parsed_source_url = urlparse(source_url)
        source_url_valid = (
            parsed_source_url.scheme in {"http", "https"}
            and bool(parsed_source_url.netloc)
            and parsed_source_url.username is None
            and parsed_source_url.password is None
        )
        if not event_id or not source_group_key or not content_sha256:
            raise ValueError(f"FEED_QUALITY_SOURCE_AUDIT_INVALID:{index}")
        if not source_url_valid:
            invalid_source_url_indices.append(index)
        elif _stale_source_url(source_url):
            stale_source_url_indices.append(index)
        audit_event_ids.append(event_id)
        if source_group_key in seen_source_groups:
            duplicate_sources += 1
        else:
            seen_source_groups.add(source_group_key)
        if content_sha256 in seen_content:
            duplicate_source_content += 1
        else:
            seen_content.add(content_sha256)
    if html_event_ids != audit_event_ids:
        raise ValueError("FEED_QUALITY_SOURCE_AUDIT_EVENT_MISMATCH")
    if duplicate_sources:
        raise ValueError(f"FEED_QUALITY_DUPLICATE_SOURCE:{duplicate_sources}")
    if duplicate_source_content:
        raise ValueError(f"FEED_QUALITY_DUPLICATE_SOURCE_CONTENT:{duplicate_source_content}")
    if invalid_source_url_indices:
        raise ValueError(f"FEED_QUALITY_SOURCE_AUDIT_INVALID:{invalid_source_url_indices[0]}")
    if stale_source_url_indices:
        raise ValueError(f"FEED_QUALITY_STALE_SOURCE_URL:{stale_source_url_indices[0]}")
    return duplicate_sources, duplicate_source_content, len(stale_source_url_indices)


def validate_html(
    html: str,
    *,
    source_audit: dict[str, object] | None = None,
) -> dict[str, object]:
    parser = FeedParser()
    parser.feed(html)
    stories = parser.stories
    if not stories:
        raise ValueError("FEED_QUALITY_NO_STORIES")

    seen_headlines: set[str] = set()
    seen_summaries: set[str] = set()
    seen_content: set[tuple[str, str]] = set()
    duplicate_headlines = 0
    duplicate_summaries = 0
    duplicate_content = 0
    headline_summary_collisions = 0
    context_dependent_summaries = 0
    non_event_analytical_summaries = 0
    conditional_analytical_summaries = 0
    stale_dated_contexts = 0
    stale_sports_retrospectives = 0
    topic_binding_violations = 0
    max_headline = 0
    max_summary = 0
    psat_forbidden_hits: list[str] = []

    for index, story in enumerate(stories, start=1):
        event_id = story["event_id"].strip()
        headline = story["headline"].strip()
        summary = story["summary"].strip()
        topic = story["topic"].strip()
        if not event_id or not headline or not summary:
            raise ValueError(f"FEED_QUALITY_INCOMPLETE_STORY:{index}")
        max_headline = max(max_headline, len(headline))
        max_summary = max(max_summary, len(summary))
        if len(headline) > MAX_HEADLINE_CHARS:
            raise ValueError(f"FEED_QUALITY_HEADLINE_TOO_LONG:{index}:{len(headline)}")
        if len(summary) > MAX_SUMMARY_CHARS:
            raise ValueError(f"FEED_QUALITY_SUMMARY_TOO_LONG:{index}:{len(summary)}")

        headline_key = _normalize(headline)
        summary_key = _normalize(summary)
        if _sentence_identity(headline) == _sentence_identity(summary):
            headline_summary_collisions += 1
        if _context_dependent_summary(summary):
            context_dependent_summaries += 1
        if _non_event_analytical_summary(summary):
            non_event_analytical_summaries += 1
        if _conditional_analytical_summary(summary):
            conditional_analytical_summaries += 1
        if _stale_sports_retrospective_summary(summary):
            stale_sports_retrospectives += 1
        elif _stale_dated_context_summary(summary):
            stale_dated_contexts += 1

        if topic == KBO_HANWHA_TOPIC:
            combined_visible = f"{headline}\n{summary}"
            entertainment_crossover = (
                any(cue in combined_visible for cue in _KBO_ENTERTAINMENT_ENTITY_CUES)
                and any(cue in combined_visible for cue in _KBO_ENTERTAINMENT_ACTION_CUES)
            )
            if entertainment_crossover:
                topic_binding_violations += 1
            elif not any(term in combined_visible for term in _HANWHA_TOPIC_TERMS):
                topic_binding_violations += 1
            elif not any(cue.casefold() in headline.casefold() for cue in _KBO_HEADLINE_SCOPE_CUES):
                topic_binding_violations += 1
        elif topic == KPOP_TOPIC:
            if not any(cue.casefold() in headline.casefold() for cue in _KPOP_HEADLINE_SCOPE_CUES):
                topic_binding_violations += 1

        if headline_key in seen_headlines:
            duplicate_headlines += 1
        else:
            seen_headlines.add(headline_key)
        if summary_key in seen_summaries:
            duplicate_summaries += 1
        else:
            seen_summaries.add(summary_key)
        content_key = (headline_key, summary_key)
        if content_key in seen_content:
            duplicate_content += 1
        else:
            seen_content.add(content_key)
        if topic == PSAT_TOPIC:
            combined = f"{headline}\n{summary}".casefold()
            for forbidden in PSAT_FORBIDDEN:
                if forbidden.casefold() in combined:
                    psat_forbidden_hits.append(forbidden)

    if headline_summary_collisions:
        raise ValueError(f"FEED_QUALITY_HEADLINE_SUMMARY_COLLISION:{headline_summary_collisions}")
    if context_dependent_summaries:
        raise ValueError(f"FEED_QUALITY_CONTEXT_DEPENDENT_SUMMARY:{context_dependent_summaries}")
    if non_event_analytical_summaries:
        raise ValueError(f"FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY:{non_event_analytical_summaries}")
    if conditional_analytical_summaries:
        raise ValueError(f"FEED_QUALITY_CONDITIONAL_ANALYTICAL_SUMMARY:{conditional_analytical_summaries}")
    if stale_sports_retrospectives:
        raise ValueError(f"FEED_QUALITY_STALE_SPORTS_RETROSPECTIVE:{stale_sports_retrospectives}")
    if stale_dated_contexts:
        raise ValueError(f"FEED_QUALITY_STALE_DATED_CONTEXT:{stale_dated_contexts}")
    if topic_binding_violations:
        raise ValueError(f"FEED_QUALITY_TOPIC_BINDING:{topic_binding_violations}")
    if duplicate_headlines:
        raise ValueError(f"FEED_QUALITY_DUPLICATE_HEADLINE:{duplicate_headlines}")
    if duplicate_summaries:
        raise ValueError(f"FEED_QUALITY_DUPLICATE_SUMMARY:{duplicate_summaries}")
    if duplicate_content:
        raise ValueError(f"FEED_QUALITY_DUPLICATE_CONTENT:{duplicate_content}")
    if psat_forbidden_hits:
        raise ValueError("FEED_QUALITY_PSAT_FALSE_POSITIVE:" + ",".join(sorted(set(psat_forbidden_hits))))

    duplicate_sources = 0
    duplicate_source_content = 0
    stale_source_urls = 0
    if source_audit is not None:
        duplicate_sources, duplicate_source_content, stale_source_urls = _validate_source_audit(stories, source_audit)

    return {
        "status": "PASS",
        "story_count": len(stories),
        "max_headline_chars": max_headline,
        "max_summary_chars": max_summary,
        "headline_summary_collisions": headline_summary_collisions,
        "context_dependent_summaries": context_dependent_summaries,
        "non_event_analytical_summaries": non_event_analytical_summaries,
        "conditional_analytical_summaries": conditional_analytical_summaries,
        "stale_dated_contexts": stale_dated_contexts,
        "stale_sports_retrospectives": stale_sports_retrospectives,
        "topic_binding_violations": topic_binding_violations,
        "duplicate_headlines": duplicate_headlines,
        "duplicate_summaries": duplicate_summaries,
        "duplicate_content": duplicate_content,
        "duplicate_sources": duplicate_sources,
        "duplicate_source_content": duplicate_source_content,
        "stale_source_urls": stale_source_urls,
        "psat_forbidden_hits": 0,
        "html_sha256": hashlib.sha256(html.encode("utf-8")).hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("html", type=Path)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    html = args.html.read_text(encoding="utf-8")
    source_audit = None
    if args.audit is not None:
        source_audit = json.loads(args.audit.read_text(encoding="utf-8"))
        if not isinstance(source_audit, dict):
            raise ValueError("FEED_QUALITY_SOURCE_AUDIT_INVALID_ROOT")
    report = validate_html(html, source_audit=source_audit)
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("FEED_QUALITY_PASS " + " ".join(f"{key}={value}" for key, value in report.items() if key != "status"))


if __name__ == "__main__":
    main()

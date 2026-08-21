from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one patch anchor, found {count}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


# 1) Manual push notifications: each manual workflow run is its own delivery
# identity. Scheduled notifications remain once-per-day/type/source.
replace_once(
    "push-worker/src/index.js",
    '''function notificationMarkerKey(date, type, source) {
  return `${NOTIFICATION_PREFIX}${date}:${type}:${source}`;
}
''',
    '''function notificationMarkerKey(date, type, source, runId = "") {
  if (source === "manual") {
    return `${NOTIFICATION_PREFIX}${date}:${type}:${source}:${runId}`;
  }
  return `${NOTIFICATION_PREFIX}${date}:${type}:${source}`;
}
''',
)
replace_once(
    "push-worker/src/index.js",
    '''function notificationPayload(type, env) {
  const ready = type === "READY";
  return {
    title: ready ? "오늘 브리핑 준비 완료" : "오늘 브리핑 업데이트 실패",
    body: ready ? "Insight Desk 오늘 브리핑을 확인하세요." : "마지막 정상 브리핑을 유지하고 있습니다.",
    tag: ready ? "insight-desk-ready" : "insight-desk-failure",
    url: `${configuredOrigin(env)}/insight-desk/`,
  };
}
''',
    '''function notificationPayload(type, env, { source = "other", runId = "" } = {}) {
  const ready = type === "READY";
  const baseTag = ready ? "insight-desk-ready" : "insight-desk-failure";
  return {
    title: ready ? "오늘 브리핑 준비 완료" : "오늘 브리핑 업데이트 실패",
    body: ready ? "Insight Desk 오늘 브리핑을 확인하세요." : "마지막 정상 브리핑을 유지하고 있습니다.",
    tag: source === "manual" && runId ? `${baseTag}-${runId}` : baseTag,
    url: `${configuredOrigin(env)}/insight-desk/`,
  };
}
''',
)
replace_once(
    "push-worker/src/index.js",
    '''  // Source is part of the idempotency identity.  A manual READY must not
  // consume the schedule READY slot for the same date and type.
  const markerKey = notificationMarkerKey(date, type, source);
  let existing = await env.PUSH_SUBSCRIPTIONS.get(markerKey);
  // Read legacy markers only for non-schedule callers.  Existing pre-source
  // markers remain compatible without allowing them to mask a schedule run.
  if (!existing && source !== "schedule") {
    existing = await env.PUSH_SUBSCRIPTIONS.get(legacyNotificationMarkerKey(date, type));
  }
''',
    '''  // Scheduled delivery is idempotent for the day. Manual workflow runs
  // are idempotent per run so a fresh operator-triggered validation can emit
  // its own result without consuming or being consumed by another run.
  const markerKey = notificationMarkerKey(date, type, source, runId);
  let existing = await env.PUSH_SUBSCRIPTIONS.get(markerKey);
  // Pre-source legacy markers correspond to the old generic caller only.
  // They must never suppress a new explicit manual run.
  if (!existing && source === "other") {
    existing = await env.PUSH_SUBSCRIPTIONS.get(legacyNotificationMarkerKey(date, type));
  }
''',
)
replace_once(
    "push-worker/src/index.js",
    '''  const payload = notificationPayload(type, env);
''',
    '''  const payload = notificationPayload(type, env, { source, runId });
''',
)
replace_once(
    "push-worker/src/index.js",
    '''  const markerKey = notificationMarkerKey(date, type, source);
  const active = inFlightNotifications.get(markerKey);
''',
    '''  const markerKey = notificationMarkerKey(date, type, source, runId);
  const active = inFlightNotifications.get(markerKey);
''',
)

worker_test = Path("push-worker/test/worker.test.js")
worker_text = worker_test.read_text(encoding="utf-8")
insert_before = 'test("same-isolate concurrent retries share one delivery operation", async () => {'
if worker_text.count(insert_before) != 1:
    raise SystemExit("worker test insertion anchor mismatch")
manual_test = r'''test("distinct manual runs deliver independently while the same manual run dedupes", async () => {
  const env = environment();
  await handleRequest(request("/subscribe", { method: "POST", body: subscription }), env);
  const auth = { Authorization: `Bearer ${sendToken}` };
  const tags = [];
  const sendNotification = async (_stored, message) => { tags.push(message.tag); };
  const send = (runId) => handleRequest(
    request("/send", {
      method: "POST",
      body: { date: "2026-08-21", run_id: runId, type: "READY", source: "manual" },
      headers: auth,
    }),
    env,
    undefined,
    { sendNotification },
  );

  const first = await send("manual-100-1");
  const retry = await send("manual-100-1");
  const secondRun = await send("manual-101-1");

  assert.equal(first.status, 200);
  assert.equal((await retry.json()).duplicate, true);
  assert.equal((await secondRun.json()).duplicate, false);
  assert.equal(tags.length, 2);
  assert.notEqual(tags[0], tags[1]);
  assert.match(tags[0], /manual-100-1$/);
  assert.match(tags[1], /manual-101-1$/);
});

'''
worker_text = worker_text.replace(insert_before, manual_test + insert_before, 1)
legacy_start = worker_text.index('test("legacy delivery markers are normalized without an invalid response state"')
legacy_end = worker_text.index('test("delivery states distinguish no subscribers', legacy_start)
legacy_block = worker_text[legacy_start:legacy_end]
legacy_block = legacy_block.replace('source: "manual"', 'source: "other"')
worker_text = worker_text[:legacy_start] + legacy_block + worker_text[legacy_end:]
worker_test.write_text(worker_text, encoding="utf-8")


# 2) Editorial materiality: low-information primary focus cannot escape merely
# by being classified into a nominally strong event family.
old_materiality = '''def _briefing_materiality_passes(title_text: str, topic: Topic, event_type: str) -> bool:
    """Separate factual event validity from scarce daily-briefing value."""

    if event_type not in _SOFT_BRIEFING_EVENT_TYPES:
        return True

    # Reuse the already-locked semantic relation contract. Personnel changes,
    # partner/program selections, affiliation changes, and other complete
    # actor-action-object relations are material even when their broad event
    # family is ANNOUNCEMENT.
    if typed_event_relation(title_text) is not None:
        return True

    family = _topic_family(topic)
    low_information = any(_contains(title_text, marker) for marker in _COMMON_LOW_INFORMATION_CONTENT_MARKERS)

    if family == "kpop":
        if event_type == "ENTERTAINMENT_EVENT":
            return bool(
                any(_contains(title_text, marker) for marker in ("컴백", "콘서트", "공연", "월드투어", "앨범", "음원", "발매"))
                and not low_information
            )
        return bool(
            any(pattern.search(normalize_text(title_text)) for pattern in _KPOP_BRIEFING_MATERIAL_PATTERNS)
            and not low_information
        )

    if family == "ai":
        technical_object = any(_contains(title_text, marker) for marker in _AI_MATERIAL_OBJECT_MARKERS)
        material_action = any(_contains(title_text, marker) for marker in _AI_MATERIAL_ACTION_MARKERS)
        return bool(technical_object and material_action and not low_information)

    if family == "economy":
        low_information = low_information or any(_contains(title_text, marker) for marker in _ECONOMY_LOW_INFORMATION_MARKERS)
        return bool(any(_contains(title_text, marker) for marker in _ECONOMY_MATERIAL_MARKERS) and not low_information)

    if family == "kbo":
        return bool(any(_contains(title_text, marker) for marker in _KBO_MATERIAL_MARKERS) and not low_information)

    if family == "psat":
        low_information = low_information or any(_contains(title_text, marker) for marker in _PSAT_LOW_INFORMATION_MARKERS)
        return bool(any(_contains(title_text, marker) for marker in _PSAT_MATERIAL_MARKERS) and not low_information)

    return not low_information
'''
new_materiality = '''def _briefing_materiality_passes(title_text: str, topic: Topic, event_type: str) -> bool:
    """Separate factual event validity from scarce daily-briefing value.

    Event typing answers "did something happen?"; this gate answers the
    separate question "does this deserve one of today's scarce briefing
    slots?"  Low-information primary focus therefore remains rejectable even
    when a generic marker accidentally promotes it into a strong event family.
    """

    # Reuse the already-locked semantic relation contract. Personnel changes,
    # partner/program selections, affiliation changes, and other complete
    # actor-action-object relations are material regardless of their broad
    # event family.
    if typed_event_relation(title_text) is not None:
        return True

    family = _topic_family(topic)
    normalized = normalize_text(title_text)
    low_information = any(_contains(title_text, marker) for marker in _COMMON_LOW_INFORMATION_CONTENT_MARKERS)
    background_material_context = bool(
        low_information
        and re.search(
            r"(?:출시|발매|컴백|데뷔|공연|콘서트|수상|발표|공개|규제|시행|경기|선발)"
            r".{0,12}(?:기념|앞두고|맞아|맞이해)",
            normalized,
        )
    )
    strong_event_family = event_type not in _SOFT_BRIEFING_EVENT_TYPES

    if family == "kpop":
        material_event = any(pattern.search(normalized) for pattern in _KPOP_BRIEFING_MATERIAL_PATTERNS)
        if background_material_context:
            return False
        if material_event:
            return True
        if low_information:
            return False
        if strong_event_family:
            return True
        if event_type == "ENTERTAINMENT_EVENT":
            return any(
                _contains(title_text, marker)
                for marker in ("컴백", "콘서트", "공연", "월드투어", "앨범", "음원", "발매")
            )
        return False

    if family == "ai":
        technical_object = any(_contains(title_text, marker) for marker in _AI_MATERIAL_OBJECT_MARKERS)
        material_action = any(_contains(title_text, marker) for marker in _AI_MATERIAL_ACTION_MARKERS)
        strong_action = any(
            _contains(title_text, marker)
            for marker in ("출시", "도입", "투자", "인수", "계약", "규제", "허가", "공급", "수주", "전환")
        )
        if background_material_context:
            return False
        if low_information:
            return bool(technical_object and strong_action)
        if strong_event_family:
            return True
        return bool(technical_object and material_action)

    if family == "economy":
        low_information = low_information or any(_contains(title_text, marker) for marker in _ECONOMY_LOW_INFORMATION_MARKERS)
        if low_information:
            return False
        if strong_event_family:
            return True
        return any(_contains(title_text, marker) for marker in _ECONOMY_MATERIAL_MARKERS)

    if family == "kbo":
        material = any(_contains(title_text, marker) for marker in _KBO_MATERIAL_MARKERS)
        if background_material_context:
            return False
        if low_information:
            return material
        if strong_event_family:
            return True
        return material

    if family == "psat":
        low_information = low_information or any(_contains(title_text, marker) for marker in _PSAT_LOW_INFORMATION_MARKERS)
        if low_information:
            return False
        if strong_event_family:
            return True
        return any(_contains(title_text, marker) for marker in _PSAT_MATERIAL_MARKERS)

    if low_information:
        return False
    return strong_event_family or event_type in _SOFT_BRIEFING_EVENT_TYPES
'''
replace_once("insight_desk/pipeline/editorial.py", old_materiality, new_materiality)

materiality_test = Path("tests/test_briefing_materiality.py")
materiality_text = materiality_test.read_text(encoding="utf-8")
anchor = '    def test_intentional_materiality_rejection_is_not_false_empty_recall_risk(self) -> None:\n'
if materiality_text.count(anchor) != 1:
    raise SystemExit("materiality test insertion anchor mismatch")
new_test = '''    def test_low_information_primary_focus_cannot_hide_in_strong_event_family(self) -> None:
        rejected = (
            ("kpop-release-background", "kpop", "K-POP", "아이브, 신곡 발매 기념 댄스 챌린지 공개", "아이브가 신곡 발매를 기념해 댄스 챌린지 영상을 공개했다."),
            ("ai-release-background", "ai_tech", "OpenAI", "OpenAI 새 AI 모델 출시 기념 CEO 인터뷰 영상 공개", "OpenAI가 새 AI 모델 출시를 기념해 CEO 인터뷰 영상을 공개했다."),
            ("psat-study-strong", "psat_recruitment", "7급 공채", "7급 공채 PSAT 합격 공부법 영상 공개", "7급 공채 PSAT 합격 공부법을 설명하는 영상을 공개했다."),
        )
        for key, topic_id, query, title, summary in rejected:
            assessment = self.assessment(key, topic_id, query, title, summary)
            self.assertFalse(assessment.qualified, (title, assessment.event.event_type, assessment.reasons))
            self.assertIn("LOW_BRIEFING_MATERIALITY", assessment.reasons, title)

        kept = self.assessment(
            "ai-real-release-with-interview",
            "ai_tech",
            "OpenAI",
            "OpenAI 새 AI 모델 출시, CEO 인터뷰도 공개",
            "OpenAI가 8월 21일 새 AI 모델을 출시했고 CEO 인터뷰도 공개했다.",
        )
        self.assertNotIn("LOW_BRIEFING_MATERIALITY", kept.reasons)
        self.assertTrue(kept.event.passed)

'''
materiality_test.write_text(materiality_text.replace(anchor, new_test + anchor, 1), encoding="utf-8")


# 3) Shared Korean summary style contract derived from the seven user-locked
# principles. Only deterministic defects are machine-gated; the complete
# human editorial policy is stored in docs below.
summary_insert = r'''
_SUMMARY_TRANSLATIONESE_RE = re.compile(
    r"(?:결정을\s*내렸|영향을\s*미쳤|(?:발표|진행|검토)를\s*했)"
)
_SUMMARY_ABSTRACT_SENTENCE_RE = re.compile(
    r"(?:^|(?<=[.!?。！？])\s+)(?:논란이\s*커졌다|우려가\s*제기됐다|성과를\s*냈다)(?=$|[.!?。！？])"
)
_SUMMARY_REDUNDANT_CONCLUSION_RE = re.compile(
    r"(?:^|(?<=[.!?。！？])\s+)(?:종합하면|요약하면|결론적으로)\b"
)
_SUMMARY_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?。！？])\s+")
_SUMMARY_LEADING_SUBJECT_RE = re.compile(
    r"^\s*([A-Za-z0-9가-힣·&.'’-]{2,30})(?:은|는|이|가)(?=\s)"
)


def summary_style_issues(value: str) -> tuple[str, ...]:
    """Return deterministic violations of the Korean news-summary SSOT.

    This deliberately enforces only the subset that can be judged without
    guessing: obvious translationese nominalization, unattributed abstract
    evaluation as a whole sentence, forced concluding prose, and immediate
    repetition of the same explicit subject across adjacent sentences.
    """

    text = normalize_text(value)
    if not text:
        return ("EMPTY",)
    issues: list[str] = []
    if _SUMMARY_TRANSLATIONESE_RE.search(text):
        issues.append("TRANSLATIONESE")
    if _SUMMARY_ABSTRACT_SENTENCE_RE.search(text):
        issues.append("ABSTRACT_EVALUATION")
    if _SUMMARY_REDUNDANT_CONCLUSION_RE.search(text):
        issues.append("REDUNDANT_CONCLUSION")

    previous_subject = ""
    for sentence in _SUMMARY_SENTENCE_SPLIT_RE.split(text):
        match = _SUMMARY_LEADING_SUBJECT_RE.match(sentence)
        subject = normalize_text(match.group(1)) if match else ""
        if subject and previous_subject and subject == previous_subject:
            issues.append("REPEATED_SUBJECT")
            break
        previous_subject = subject or previous_subject
    return tuple(dict.fromkeys(issues))

'''
synthesis = Path("insight_desk/pipeline/synthesis.py")
synthesis_text = synthesis.read_text(encoding="utf-8")
style_anchor = '\n\ndef editorial_text_issues(value: str) -> tuple[str, ...]:\n'
if synthesis_text.count(style_anchor) != 1:
    raise SystemExit("synthesis style insertion anchor mismatch")
synthesis_text = synthesis_text.replace(style_anchor, '\n' + summary_insert + '\ndef editorial_text_issues(value: str) -> tuple[str, ...]:\n', 1)
usable_anchor = '''    if editorial_text_issues(clean_summary):
        return False
'''
if synthesis_text.count(usable_anchor) != 1:
    raise SystemExit("synthesis usability anchor mismatch")
synthesis_text = synthesis_text.replace(
    usable_anchor,
    usable_anchor + '''    if summary_style_issues(clean_summary):
        return False
''',
    1,
)
synthesis.write_text(synthesis_text, encoding="utf-8")

replace_once(
    "scripts/validate_live_acceptance.py",
    '''    editorial_text_issues,
    relation_summary_preserves_fact,
    summary_why_redundant,
''',
    '''    editorial_text_issues,
    relation_summary_preserves_fact,
    summary_style_issues,
    summary_why_redundant,
''',
)
replace_once(
    "scripts/validate_live_acceptance.py",
    '''        headline_issues = editorial_text_issues(headline)
        summary_issues = editorial_text_issues(summary)
''',
    '''        headline_issues = editorial_text_issues(headline)
        summary_issues = editorial_text_issues(summary)
        summary_style = summary_style_issues(summary)
''',
)
replace_once(
    "scripts/validate_live_acceptance.py",
    '''        composition_issues = set(headline_issues + summary_issues).intersection(
            {"MALFORMED_PARTICLE_STACK"}
        )
''',
    '''        composition_issues = set(headline_issues + summary_issues).intersection(
            {"MALFORMED_PARTICLE_STACK"}
        ) | set(summary_style)
''',
)

Path("tests/test_news_summary_principles.py").write_text(r'''from __future__ import annotations

import unittest
from pathlib import Path

from insight_desk.pipeline.synthesis import is_usable_synthesis, summary_style_issues


class KoreanNewsSummaryPrincipleTests(unittest.TestCase):
    def test_fact_first_natural_korean_passes(self) -> None:
        summary = (
            "금융당국이 8월 21일부터 레버리지 ETF 투자한도를 100만원으로 제한한다. "
            "기존 한도는 300만원이었다."
        )
        self.assertEqual(summary_style_issues(summary), ())

    def test_translationese_is_rejected(self) -> None:
        self.assertIn("TRANSLATIONESE", summary_style_issues("정부가 규제 강화 결정을 내렸다."))
        self.assertFalse(
            is_usable_synthesis(
                "정부, 규제 강화",
                "정부가 규제 강화 결정을 내렸다.",
                source_count=2,
            )
        )

    def test_repeated_subject_is_rejected_when_subject_did_not_change(self) -> None:
        issues = summary_style_issues(
            "삼성전자는 2분기 영업이익이 20% 늘었다. 삼성전자는 설비투자도 확대했다."
        )
        self.assertIn("REPEATED_SUBJECT", issues)

    def test_unattributed_abstract_evaluation_and_forced_conclusion_are_rejected(self) -> None:
        self.assertIn("ABSTRACT_EVALUATION", summary_style_issues("우려가 제기됐다."))
        self.assertIn(
            "REDUNDANT_CONCLUSION",
            summary_style_issues("회사는 투자를 2조원으로 늘렸다. 종합하면 중요한 변화다."),
        )

    def test_live_validator_uses_the_same_style_contract(self) -> None:
        validator = Path("scripts/validate_live_acceptance.py").read_text(encoding="utf-8")
        self.assertIn("summary_style_issues(summary)", validator)

    def test_policy_document_contains_all_seven_locked_rules(self) -> None:
        policy = Path("docs/news-summary-korean-principles.md").read_text(encoding="utf-8")
        for number in range(1, 8):
            self.assertIn(f"## {number}.", policy)


if __name__ == "__main__":
    unittest.main()
''', encoding="utf-8")

Path("docs").mkdir(exist_ok=True)
Path("docs/news-summary-korean-principles.md").write_text('''# 뉴스 기사 요약용 한국어 문장 작성 원칙

이 문서는 Insight Desk의 한국어 기사 요약 SSOT다. 생성기와 검수기는 이 원칙보다 느슨한 별도 문체 기준을 두지 않는다.

## 1. 기사에서 확인된 사실과 발생한 일을 중심으로 쓴다
누가 무엇을 했는지, 무엇이 달라졌는지, 언제·어디서 일이 벌어졌는지를 먼저 적는다. 수치, 날짜, 결정, 발표, 조치, 결과처럼 확인할 수 있는 정보를 우선한다. 중요성을 강조하려고 형용사를 덧붙이지 말고 사건의 규모나 영향을 보여주는 사실을 제시한다.

## 2. 주체가 이어지면 반복하지 않고 사건의 진행을 바로 서술한다
앞 문장에서 정부, 기업, 인물 등 주체가 이미 정해졌다면 같은 이름이나 대명사를 계속 반복하지 않는다. 발표했다, 밝혔다, 늘었다, 줄었다, 결정했다처럼 동작과 변화부터 이어 쓴다. 주체가 바뀌거나 서로 다른 입장을 대비할 때만 다시 밝힌다.

## 3. 기사체를 번역하지 않고 자연스러운 한국어 문장으로 다시 짠다
원문의 문장 구조나 명사 표현을 그대로 옮기지 않는다. ‘결정을 내렸다’, ‘영향을 미쳤다’처럼 불필요하게 늘어진 표현은 가능하면 ‘결정했다’, ‘영향을 줬다’처럼 뜻이 바로 드러나는 동사로 바꾼다. 영어식 수식 구조와 긴 명사 나열을 피하고 한국어에서 실제로 읽기 쉬운 조사와 어순을 쓴다.

## 4. 핵심 사실은 짧게, 조건과 배경이 필요한 내용은 충분히 쓴다
사건의 핵심 결과나 새로운 사실은 짧은 문장으로 분명하게 적는다. 원인, 전제 조건, 비교 기준, 예외가 함께 있어야 정확해지는 내용은 한 문장에 필요한 만큼 담는다. 모든 문장을 같은 길이로 맞추지 않는다.

## 5. 문단은 하나의 사건 흐름이나 쟁점이 끝나는 자리에서 끊는다
같은 내용을 마지막 문장에서 다시 요약하지 않는다. 발표 내용, 후속 조치, 반응, 수치, 배경 가운데 해당 문단에 필요한 마지막 정보에서 멈춘다. 다음 쟁점으로 넘어갈 때는 별도의 결론 문장을 억지로 붙이지 않는다.

## 6. 사실 사이의 관계는 문장 순서로 드러낸다
원인이 확인되면 원인 다음에 결과를 둔다. 기존 수치와 새 수치, 정부와 야당, 회사와 노조처럼 비교할 대상은 가까이 배치한다. 시간순으로 이해해야 하는 사건은 발생 순서대로 정리한다. 배열만으로 관계가 분명하면 ‘한편’, ‘이에 따라’, ‘이와 관련해’ 같은 연결 표현을 습관적으로 붙이지 않는다.

## 7. 평가와 추상어를 줄이고 구체적인 대상·행동·수치를 남긴다
‘논란이 커졌다’, ‘우려가 제기됐다’, ‘성과를 냈다’처럼 범위가 불분명한 표현만 남기지 않는다. 누가 어떤 문제를 지적했는지, 어떤 수치가 얼마나 변했는지, 어떤 조치가 실제로 시행됐는지를 적는다. 기사나 공식 자료가 평가를 포함할 경우에는 평가 주체와 근거를 함께 밝힌다.

## 기계 검증 범위

현재 validator가 deterministic하게 차단하는 항목은 다음과 같다.

- 명백한 번역투·명사화 표현
- 같은 주체를 바로 다음 문장 첫머리에서 불필요하게 반복하는 문장
- 평가 주체 없이 독립 문장으로 남은 추상 평가
- `종합하면`, `요약하면`, `결론적으로`로 덧붙이는 억지 결론

나머지 원칙은 사실 보존, 사건 역할, 시간·인과 관계, primary focus 계약과 사람의 최종 live audit를 함께 적용한다.
''', encoding="utf-8")

print("final closure patch applied")

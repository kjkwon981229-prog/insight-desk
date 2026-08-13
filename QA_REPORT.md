# QA_REPORT

## 현재 post-Sol 검사 대상

latest Sol convergence HEAD `55c31740e1e28e5410ae1232372f04114e55ad1f`, CI #193(298 Python + 13 Worker), Sol ownership/focus/material synthesis closure, Run #96 fresh live acceptance 및 이번 local closure를 함께 기록한다.

- 이번 local closure: Python 298개 및 Push Worker 13개 통과
- Run #92 KBO·경제 targeted live reproof: `PENDING` (Run #93에서는 해당 후보가 선택되지 않음)
- Run #96 fresh workflow dispatch: `PASS` (selected 1건, human audit PASS)
- next live: actual `07:30 KST` schedule

## False-pass 철회

Historical Run #12는 News·Trend 수집과 Pages 배포에는 성공했지만, 실제 selected story 10개가 모두 single-source였고 저정보·`OTHER`·generic 후보가 다수였다. PSAT biography, incidental K-POP mention, KBO merchandise/문화성 결과도 통과했다. 따라서 이전 QA의 콘텐츠 PASS와 `CONDITIONAL_PASS_EXTERNAL_ACCEPTANCE_ONLY`는 무효다. 현재 판정은 문서 하단의 post-Sol 상태를 따른다.

## Fresh live acceptance

Run #96 (`workflow_dispatch`, ID `31678835800`, HEAD `55c31740…`)은 build·artifact validation·live editorial acceptance·Pages deploy를 모두 통과했다. selected story는 1건이며 `semantic_error_count`, `primary_focus_error_count`, `korean_composition_error_count`, `summary_why_duplication_count`, `duplicate_event_count` 등 live validator counters가 모두 0이었다. 선택된 `BTS 아리랑, 빌보드 앨범 차트 14위`는 같은 AWARD_CHART event와 14위 fact를 유지했고, `why_it_matters`는 중복 방지를 위해 빈 값이다. READY push는 `DELIVERED`(sent 4, failed 0, pruned 0)였고, 실제 iPhone READY 표시·개수·tap/open은 아직 별도 gate다.

Run #94/#95의 KBO·경제 exact live reproof는 Run #96에서 해당 event가 selected되지 않아 `PENDING`으로 유지한다. 이는 fresh general acceptance PASS와 모순되지 않는다.

## 선택·콘텐츠 검증

| 검사 | 결과 |
|---|---|
| 다섯 관심사 SSOT·query family | 통과 |
| topic candidate budget·fair retrieval | 통과 |
| topic-local ranking·coverage floor | 통과 |
| conditional topic omission·no filler | 통과 |
| saturation cap·cap relaxation | 통과 |
| publisher diversity vs raw source count | 통과 |
| cross-topic attribution | 통과 |
| topic-diverse enrichment allocation | 통과 |
| overview not first story·no single-story hero | 통과 |
| 10-day selection matrix | local regression 유지 |
| dual `sim`/`date` retrieval | local regression 추가 |
| title/lead intent relevance | local regression 추가 |
| concrete event / single-source gate | local regression 추가 |
| generic live acceptance hard gate | local validator 추가 |
| raw snippet·ellipsis·cluster debug copy 차단 | 통과 |
| contextual next signal·compact trend | 통과 |
| live content 잘린 snippet/key fact 누출 차단 | 통과 |
| live content generic summary·저신호 filler 차단 | 통과 |

## PWA·artifact 검증

- 모든 root/latest/archive/date page에 manifest, favicon, Apple touch icon, theme color, Apple web-app meta, viewport contract 존재 — 로컬·공개 페이지 통과
- `display: standalone`, 아이콘 192/512, Candidate 5 provenance — 통과
- manifest icon 파일 존재·경로 검사 — 통과
- `viewport-fit=cover`, safe-area CSS — 통과
- push 전용 service worker·notification click 유지, briefing HTML fetch/cache handler 없음 — 의도한 정책과 일치
- internal topic ID·selection audit·local filesystem path·secret 공개 차단 — 통과
- local link·UTF-8·artifact validator — 통과

## Historical 자동 테스트

```text
compileall = PASS
unittest = PASS (62/62)
fixture site = PASS
synthesis fixture A-J = PASS
artifact validation = PASS
Ruff F/I (변경 PWA/validator 파일) = PASS
Ruff 전체 = NOT CLAIMED (기존 E501)
mypy = NOT CLAIMED (환경 미설치)
```

## 이전 원격 검증 — 콘텐츠 품질 판정 철회

| 검사 | 결과 |
|---|---|
| 최종 CI | 성공 · `31334275366` |
| Pages Run #12 | build `93297582968` / deploy `93297710682` 성공 · `31334331280` |
| 실제 NCP News/Trend | `COMPLETE`, `publish=true` · Run #12 (수집 성공만 유효; editorial PASS 철회) |
| artifact validation | 성공 · Pages artifact `9043866757` |
| 공개 URL | 정상 · manifest/icon/apple head, UTF-8, internal links, archive 확인 |

## 브라우저 범위

- cloud browser desktop viewport `1363px`에서 실제 공개 root/latest/archive/date 페이지의 UTF-8·내부 링크·가로 overflow·금지 문구·archive 이동·PWA head를 확인했다.
- 실제 live 콘텐츠에서 `...`/`…`, `관련 내용이 확인됐다`, cluster debug 문구 및 내부 topic ID가 사용자 화면에 없는 것을 확인했다.
- 정확한 320/375/390/430/768/1024/1440px 각각의 브라우저 렌더와 실제 iPhone Safari는 이 환경에서 직접 완료하지 않았다.
- iPhone 상태는 사용자의 physical-device acceptance 후에만 `YES`로 바꾼다.

## 현재 게이트(실제 schedule 전)

```text
BASELINE_CI_193 = PASS (298 Python + 13 Worker)
LOCAL_POST_SOL_CLOSURE = PASS (298 Python + 13 Worker)
RUN93_GENERAL_PRODUCTION_SMOKE = PASS
RUN94_RUN95_SOL_REPLAY = PASS
RUN92_TARGETED_KBO_LIVE_REPROOF = PENDING
RUN92_TARGETED_ECON_LIVE_REPROOF = PENDING
RUN96_FRESH_LIVE_ACCEPTANCE = PASS
MANUAL_WORKFLOW_DISPATCH = RUN96 ONLY
ACTUAL_SCHEDULE_0730 = PENDING
PAGES_DEPLOYMENT_VERIFIED = PASS (Run #96)
PAGES_URL_VERIFIED = PASS (Run #96)
MOBILE_BROWSER_VERIFIED = PARTIAL
IPHONE_SAFARI_VERIFIED = PENDING
PARTIAL_FAILURE_VERIFIED = YES
TOTAL_FAILURE_PRESERVATION_VERIFIED = YES
SECRET_SCAN_VERIFIED = YES
SCHEDULED_RUN_VERIFIED = PENDING
```

## 현재 판정

`READY_FOR_FINAL_PHYSICAL_TIME_ACCEPTANCE`

Run #96 fresh live의 selected-story 전수 human audit까지 통과했지만, 실제 schedule provenance·READY 알림의 iPhone 표시·개수·tap/open·watchdog 전에는 `PRODUCTION_FINAL`로 올리지 않는다.

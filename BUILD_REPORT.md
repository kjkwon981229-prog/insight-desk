# BUILD_REPORT

## 현재 판정

- 복구 수준: `LEVEL D — CONTRACT RECONSTRUCTION` 이후 post-Sol hardening
- 현재 상태: `READY_FOR_FINAL_PHYSICAL_TIME_ACCEPTANCE`
- latest Sol convergence HEAD: `55c31740e1e28e5410ae1232372f04114e55ad1f`
- 기준 CI #193: Python 298개 및 Push Worker 13개 통과
- 이번 오프라인 closure: Python 298개 및 Push Worker 13개 통과
- Run #92 human acceptance 실패는 ownership closure 전의 historical evidence이며, Run #93 general smoke는 build·artifact·machine editorial acceptance·Pages·push까지 통과했다.
- Run #94/#95 replay와 Sol focus/material synthesis/Korean composition validator closure는 현재 HEAD에서 통과했다.
- Run #96 fresh `workflow_dispatch`는 build·artifact·machine editorial acceptance·Pages·READY push까지 통과했고 selected story 1건 human audit도 통과했다. 실제 `07:30 KST` schedule은 아직 별도 gate다.
- Run #12의 원격 NCP/Pages 성공은 수집·배포 성공 증거일 뿐이며, 실제 selected story 품질 감사에서 false pass가 확인되어 최종 판정을 철회했다.

## 최신 fresh live acceptance

| 항목 | 결과 |
|---|---|
| Run | [#96 · 31678835800](https://github.com/kjkwon981229-prog/insight-desk/actions/runs/31678835800) |
| trigger / HEAD | `workflow_dispatch` / `55c31740e1e28e5410ae1232372f04114e55ad1f` |
| build / artifact / editorial | `SUCCESS` / `PASS` / `PASS` |
| selected / strong rejected | `1` / `0` |
| semantic counters | all `0` |
| deploy / public URL | `SUCCESS` / <https://kjkwon981229-prog.github.io/insight-desk/> |
| READY push | `DELIVERED`, sent `4`, failed `0`, pruned `0` |
| human audit | selected story 1건 `PASS` |

선택 story는 `BTS 아리랑, 빌보드 앨범 차트 14위`이며 summary는 같은 AWARD_CHART event의 14위 fact를 보존한다. `why_it_matters`는 summary 반복을 피하기 위해 비워졌다. KBO·경제 exact live reproof는 이번 run에서 selected되지 않아 별도 `PENDING`이다.

## 현재 공식 source 상태

| source | 상태 |
|---|---|
| OpenDART | `IMPLEMENTED_LIVE_HEALTHY_POSITIVE_PENDING` |
| KOSIS | `IMPLEMENTED_AND_OFFLINE_VALIDATED` |
| ECOS | `CREDENTIAL_REQUIRED` |
| PSAT official | `IMPLEMENTED_LIVE_HEALTHY_POSITIVE_PENDING` |
| KBO official | `IMPLEMENTED_LIVE_HEALTHY_POSITIVE_PENDING` |
| Hanwha official | `IMPLEMENTED_LIVE_HEALTHY_POSITIVE_PENDING` |
| OpenAI official | `BLOCKED_EXTERNAL` (HTTP 403) |
| Google AI official | `IMPLEMENTED_LIVE_HEALTHY_POSITIVE_PENDING` |
| HYBE | `IMPLEMENTED_LIVE_HEALTHY_POSITIVE_PENDING` |
| SM | `IMPLEMENTED_LIVE_HEALTHY_POSITIVE_PENDING` |
| JYP | `IMPLEMENTED_LIVE_HEALTHY_POSITIVE_PENDING` |

`*_POSITIVE_PENDING`은 adapter health와 deterministic same-event fixture는 확인했지만, 해당 fresh run에서 실제 same-event positive가 없었다는 뜻이다. source는 discovery feed가 아니며, query-only/entity-only match로 story를 만들지 않는다.
- 원본 Windows working tree를 복구한 결과가 아니라, 확정된 모바일 웹 계약을 기준으로 재구축한 결과다.

## 이번 production recovery 변경

- News retrieval을 query별 `sort=sim` + `sort=date` bounded dual channel로 분리하고, shared query/channel 요청을 재사용한다.
- 제목·원문 metadata·lead를 우선하는 intent relevance gate를 추가했다. biography·quotation·부차적 언급은 제목 중심 사건 신호가 없으면 탈락한다.
- concrete event gate, single-source policy, source diversity/evidence 분리, event signature clustering, 이전 latest 기반 `NEW/UPDATE/UNCHANGED/UNKNOWN_HISTORY`를 연결했다.
- 최종 lineup은 품질 gate 이후에만 0~10개로 선택한다. 10개를 채우지 않으며, `01/02`는 실제 editorial score 순위다.
- live acceptance artifact는 selected story별 source/publisher/retrieval/relevance/event/evidence/novelty/why_selected를 기록하고, Pages 공개 payload에서는 제거한다.
- 이전 live false-positive 사례는 blacklist가 아니라 일반화된 PSAT biography, K-POP incidental mention, KBO merchandise, generic fallback, truncated metadata 회귀로 고정했다.

## A. 관심사·선정 구조

원래의 `global score → top 10 → first story hero` 구조는 최종 편집 권한으로 사용하지 않는다. `config/topics.json`을 관심사 SSOT로 두고 다음 다섯 영역을 독립적으로 처리한다.

- AI·테크
- 엔터·음악·K-POP
- 경제·투자
- KBO·한화 이글스
- PSAT·공채 일정

각 topic에 query family와 공정 candidate budget을 적용하고, topic-local quality·publisher diversity·공식 근거·신선도·중복 밀도를 사용해 후보를 평가한다. 이후 core coverage floor, conditional omission, 남은 slot 경쟁, saturation penalty와 topic cap을 적용한다. 개인 priority는 동률에 가까운 후보의 보조 신호로만 사용한다.

source item 수 자체는 중요도 보너스로 사용하지 않는다. 같은 매체의 재전송은 diminishing return으로 보고, 서로 다른 publisher와 official evidence를 근거 품질 신호로 사용한다.

cross-topic 중복은 `matched_topic_ids`로 보존한다. config 순서가 story 소유권을 빼앗지 않는다. enrichment 후보도 topic-diverse round-robin으로 배정한다.

## B. 홈 경험

첫 story를 자동 hero로 승격하지 않는다. 홈은 `오늘의 브리핑 → 관심사별 lead signal → 오늘 볼 뉴스 → 검색 관심 흐름 → 데이터 기준` 순서로 생성된다. overview는 선택된 lineup의 story 수·대표 관심사·trend 상태에서 만들며 첫 story summary를 복사하지 않는다.

내부 cluster 수, API 작업 수, enrichment 카운터, internal topic ID는 기본 화면에 노출하지 않는다. 전체 selection 사유는 Actions의 `selection-audit` artifact에만 남긴다.

## C. 데이터·콘텐츠 계약

- NAVER Search 결과는 1차 근거로 유지한다.
- metadata enrichment는 선택적이며 실패해도 수집 상태를 실패로 바꾸지 않는다.
- `SEARCH_SNIPPET`, `ENRICHED_METADATA`, `OFFICIAL_SOURCE` provenance를 구분한다.
- fact-first synthesis, contextual evidence, story-specific next signal을 유지한다.
- raw snippet truncation, generic next-signal filler, cluster debug copy를 사용자 화면에서 차단한다.
- Search Trend ratio는 원시 검색량이 아닌 동일 keyword group 내부의 상대 관심지수다.
- batch 간 absolute ratio 비교와 global popularity ranking은 하지 않는다.
- 기사 게시 시각과 사건 발생 시각의 구분을 유지한다.

### 이전 live 콘텐츠 감사에서 확인된 false pass

Pages Run #12의 실제 NCP 결과를 다시 읽어 다음 결함을 확인했다.

- 잘린 NAVER description 조각이 key fact 후보로 흘러갈 수 있었다.
- 선택된 10개가 모두 single-source였고, 모두 `UNCERTAIN`에 가까운 저정보 후보였으며, 다수가 `OTHER` event와 generic headline/summary였다.
- PSAT biography 문구, 부차적 아이돌 언급, KBO 상품/문화성 기사처럼 query token은 맞지만 관심사 의도와 사건 중심이 맞지 않는 후보가 들어왔다.
- 이 결과 때문에 Run #12의 콘텐츠 PASS와 `CONDITIONAL_PASS_EXTERNAL_ACCEPTANCE_ONLY` 기록을 철회했다.

이번 수정본에서는 잘림 표식이 있는 텍스트를 fact/변화량에서 제외하고, headline을 화면에서 정리하며, query relevance·concrete event·evidence·novelty를 통과하지 못한 후보는 selection filler로 사용하지 않도록 했다. 정보가 부족한 단일 출처와 generic synthesis는 core lineup과 live acceptance에서 차단한다. 없는 사실은 만들지 않는다.

## D. PWA·배포

- `display: standalone`, `start_url`, `scope`, theme/background color, Apple web-app meta, `viewport-fit=cover`, safe-area CSS를 연결했다.
- 승인된 아이콘 보드의 Candidate 5 영역을 그대로 추출하고 리사이즈하여 `icon-192.png`, `icon-512.png`, `apple-touch-icon.png`, `favicon.png`로 연결했다. 새 아이콘 geometry를 생성하지 않았다.
- manifest provenance: `APPROVED_CANDIDATE_5_EXTRACTED`
- push 전용 service worker와 notification click 경로를 유지한다. briefing HTML을 fetch/cache하는 offline-first handler는 추가하지 않는다.
- total failure·render failure·validation failure에서는 새 Pages 배포를 하지 않고 기존 정상 사이트를 보존한다.
- 최신 페이지에만 Asia/Seoul 기준 freshness 표시를 적용하고, 날짜 archive에는 stale 경고를 적용하지 않는다.

## Historical Run #12 원격 증거

| 항목 | 결과 |
|---|---|
| 저장소 | [kjkwon981229-prog/insight-desk](https://github.com/kjkwon981229-prog/insight-desk) |
| 최종 소스 commit | `23c572afe7bd8e2240f1cc6bda4431dd2572ca44` |
| 최종 CI | [Run · 31334275366](https://github.com/kjkwon981229-prog/insight-desk/actions/runs/31334275366) 성공 · 48 tests |
| 최종 Pages workflow | [Run #12 · 31334331280](https://github.com/kjkwon981229-prog/insight-desk/actions/runs/31334331280) build/deploy 성공 |
| Pages build job | `93297582968` 성공 · 실제 NCP status `COMPLETE`, `publish=true` |
| Pages deploy job | `93297710682` 성공 · 실제 공개 URL 평가 성공 |
| Pages artifact | ID `9043866757`, 363,516 bytes, `sha256:fdb1f41482c4c6ff5b7f43ddd63e26cc00c3a1d002b90a42844d920bc19abe94` |
| selection audit artifact | ID `9043866490`, 6,029 bytes, secret 없는 내부 감사 산출물 |
| 공개 주소 | [Insight Desk](https://kjkwon981229-prog.github.io/insight-desk/) |

Run #12는 최종 콘텐츠 안전 수정과 Candidate 5 icon/head contract가 포함된 commit을 실제 NCP `COMPLETE`로 빌드하고, artifact validation을 거쳐 Pages에 배포한 증거다. 로그에는 NCP secret이 `***`로 마스킹되어 있고, artifact에는 manifest·192/512 icon·Apple touch icon·favicon이 포함되어 있다.

## Historical 로컬 검증

- `python3 -m compileall -q insight_desk scripts tests` — 통과
- `python3 -m unittest discover -s tests -q` — `62/62` 통과
- fixture `COMPLETE` 생성 — 통과
- synthesis A–J fixture 생성 — 통과
- fixture/synthesis artifact validator — 통과
- selection multi-day matrix A–J — 통과
- enrichment success·403·timeout·malformed HTML·missing OG·fallback — 통과
- News-only·Trends-only·PARTIAL·TOTAL_FAILURE — 통과
- secret redaction·cache 보안·Trend semantics — 통과
- internal ID·금지 microcopy·hero coupling 회귀 — 통과
- 변경 PWA/validator/content 파일 Ruff `F,I` — 통과

전체 Ruff 기본 실행은 기존 장문 HTML/CSS E501이 남아 전체 통과로 기록하지 않는다. mypy는 실행 환경에 설치되어 있지 않아 통과로 주장하지 않는다.

## 현재 post-Sol 게이트

```text
BASELINE_CI_193 = PASS (298 Python + 13 Worker)
LOCAL_POST_SOL_CLOSURE = PASS (298 Python + 13 Worker)
RUN93_GENERAL_PRODUCTION_SMOKE = PASS
RUN94_RUN95_SOL_REPLAY = PASS
RUN92_TARGETED_KBO_LIVE_REPROOF = PENDING
RUN92_TARGETED_ECON_LIVE_REPROOF = PENDING
RUN96_FRESH_LIVE_ACCEPTANCE = PASS (workflow_dispatch, human audit PASS)
MANUAL_WORKFLOW_DISPATCH = RUN96 ONLY
ACTUAL_SCHEDULE_0730 = PENDING
PAGES_DEPLOYMENT_VERIFIED = PASS (Run #96)
PAGES_URL_VERIFIED = PASS (Run #96)
MOBILE_BROWSER_VERIFIED = PARTIAL (cloud desktop viewport + responsive source/artifact checks)
IPHONE_SAFARI_VERIFIED = PENDING
PARTIAL_FAILURE_VERIFIED = YES (local regression)
TOTAL_FAILURE_PRESERVATION_VERIFIED = YES (local regression)
SECRET_SCAN_VERIFIED = YES
SCHEDULED_RUN_VERIFIED = PENDING
PWA_MANIFEST_VERIFIED = YES (local artifact)
PWA_ICON_VERIFIED = YES (artifact + public page head)
```

## 남은 외부 확인

1. iPhone Safari에서 첫 화면·가로 밀림·뉴스 원문·archive·다크 모드를 확인한다.
2. 첫 `07:30 KST` 예약 실행 acceptance는 실제 schedule event 이후 확인한다.

## 현재 릴리스 상태

`READY_FOR_FINAL_PHYSICAL_TIME_ACCEPTANCE`

Run #96 fresh live의 selected story 전수 human audit까지 통과했지만, 실제 schedule provenance·READY push의 iPhone 표시·개수·tap/open·watchdog 전에는 `PRODUCTION_FINAL`을 주장하지 않는다.

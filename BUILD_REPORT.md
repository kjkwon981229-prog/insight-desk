# BUILD_REPORT

## 현재 판정

- 복구 수준: `LEVEL D — CONTRACT RECONSTRUCTION`
- 현재 검증 단계: 실제 NCP·Actions·Pages 재검증 완료; 물리 iPhone과 첫 예약 실행만 외부 확인 대기
- 원본 Windows working tree를 복구한 결과가 아니라, 확정된 모바일 웹 계약을 기준으로 재구축한 결과다.

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

### 실제 live 콘텐츠 감사에서 고친 결함

Pages의 실제 NCP 결과를 다시 읽어 다음 두 결함을 확인했다.

- 잘린 NAVER description 조각이 key fact 후보로 흘러갈 수 있었다.
- 정보가 부족한 단일 검색 결과가 `관련 내용이 확인됐다` 같은 무의미한 문구로 채워질 수 있었다.

`23c572a`에서 잘림 표식이 있는 텍스트를 fact/변화량에서 제외하고, headline을 완전한 절로 정리했으며, query relevance와 관측 가능한 신호가 없는 후보는 selection filler로 사용하지 않도록 수정했다. 정보가 부족한 단일 출처는 한계가 드러나는 문구로 표시하고, 없는 사실은 만들지 않는다.

## D. PWA·배포

- `display: standalone`, `start_url`, `scope`, theme/background color, Apple web-app meta, `viewport-fit=cover`, safe-area CSS를 연결했다.
- 승인된 아이콘 보드의 Candidate 5 영역을 그대로 추출하고 리사이즈하여 `icon-192.png`, `icon-512.png`, `apple-touch-icon.png`, `favicon.png`로 연결했다. 새 아이콘 geometry를 생성하지 않았다.
- manifest provenance: `APPROVED_CANDIDATE_5_EXTRACTED`
- service worker는 추가하지 않았다. 매일 갱신되는 정적 브리핑에서 오래된 offline HTML이 최신 결과처럼 보일 위험을 피하기 위한 의도적 선택이다.
- total failure·render failure·validation failure에서는 새 Pages 배포를 하지 않고 기존 정상 사이트를 보존한다.
- 최신 페이지에만 Asia/Seoul 기준 freshness 표시를 적용하고, 날짜 archive에는 stale 경고를 적용하지 않는다.

## 원격 증거

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

## 로컬 검증

- `python3 -m compileall -q insight_desk scripts tests` — 통과
- `python3 -m unittest discover -s tests -q` — `48/48` 통과
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

## 최종 게이트(현재 단계)

```text
LOCAL_TESTS_VERIFIED = YES (48/48)
LIVE_NCP_NEWS_VERIFIED = YES (Pages #12, status COMPLETE)
LIVE_NCP_TREND_VERIFIED = YES (Pages #12, status COMPLETE)
GITHUB_ACTIONS_VERIFIED = YES (CI 31334275366; Pages 31334331280)
PAGES_DEPLOYMENT_VERIFIED = YES
PAGES_URL_VERIFIED = YES
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

`CONDITIONAL_PASS_EXTERNAL_ACCEPTANCE_ONLY`

물리 iPhone Safari와 아직 도달하지 않은 첫 예약 실행만 외부 acceptance로 남아 있다. 코드·선정·PWA·실제 NCP·Actions·Pages·artifact·공개 URL gate는 확인했다.

`NO_KNOWN_FURTHER_MODIFICATIONS_WITHIN_SCOPE = YES`

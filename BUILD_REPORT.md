# BUILD_REPORT

## 현재 판정

- 복구 수준: `LEVEL D — CONTRACT RECONSTRUCTION`
- 제품 릴리스 상태: `CONDITIONAL PASS`
- 원본 Windows working tree를 복구한 결과가 아니라, 확정된 모바일 웹 계약을 기준으로 재구축한 결과다.

## 원격 검증 증거

| 항목 | 결과 |
|---|---|
| GitHub 저장소 | `kjkwon981229-prog/insight-desk` |
| 최신 UI commit | `39137fb20eea2a66916495bfe8703c1e1f8b025c` |
| CI | `Run #10 · 31326864815` 성공 |
| Pages 실행 | `Run #5 · 31327087861` 성공 |
| Pages build | `93279078337` 성공 |
| Pages deploy | `93279203775` 성공 |
| Pages artifact | `github-pages`, 854 KB |
| artifact digest | `sha256:9d36de5b0ca961b46bd857b4461a61e9f9714b46d87f6e17fe17462c14e5a253` |
| 실제 공개 주소 | [Insight Desk](https://kjkwon981229-prog.github.io/insight-desk/) |
| 실제 실행 상태 | `COMPLETE` |
| 현재 결과 규모 | 사건 묶음 10개, 검색 관심 그룹 11개, 원문 보강 5건 중 4건 |

`latest`, `archive`, 날짜별 archive를 공개 URL에서 직접 열어 확인했다. UTF-8, CSS 로드, 내부 링크, 가로 오버플로, 사용자 화면의 내부 근거 ID 미노출도 확인했다. 최초 확인에서 남아 있던 일부 경로의 이전 문구는 브라우저 캐시였으며, 동일 공개 URL을 새로 읽어 새 문구로 갱신된 것을 재확인했다.

GitHub Actions에는 Node.js 20 사용 중단 예정 경고가 2건 남아 있다. 현재 실행 실패나 배포 오류는 아니며, 이후 Actions 버전 정비 대상으로 기록한다.

## 이번 개선 범위

- 뉴스 검색 결과를 1차 근거로 유지하고, 상위 기사만 공개 metadata로 선택 보강
- 보강 실패 시 검색 결과로 안전하게 fallback
- `SEARCH_SNIPPET`, `ENRICHED_METADATA`, `OFFICIAL_SOURCE` provenance 구분
- Trend ratio를 원시 검색량으로 표시하지 않고 방향·비교 기준 중심으로 표시
- 큰 둥근 카드 중심 구조를 editorial hero·signal strip·story row·trend visualization·reference method 구조로 교체
- 사건별 evidence row와 접을 수 있는 상세 출처 영역 추가
- 내부 근거 ID를 기본 사용자 화면에서 제거
- `왜 보나`, `관심도와의 관계`, `산업·투자 판단`, 기계적인 evidence 문구 제거
- light/dark 색상 토큰과 저채도 핑크 포인트 적용
- archive를 날짜별 reference list로 재구성

## 디자인 갭 감사

초기 UI는 다음 다섯 문제가 가장 컸다.

1. 모든 정보가 큰 둥근 카드 안에 쌓여 정보 위계가 약했다.
2. 첫 화면에 오늘의 판단보다 시스템형 지표가 먼저 보였다.
3. Trend가 숫자와 문장에 머물러 변화 방향을 한눈에 읽기 어려웠다.
4. evidence ID와 기계적인 section 문구가 사용자 화면에 노출됐다.
5. archive·methodology가 본문과 같은 카드 패턴으로 표현됐다.

## 아카이브에서 채택한 문법

| 자료 | 적용한 문법 |
|---|---|
| `r2-impl-cand-000002-a` | 결론을 먼저 보여주는 editorial hero, 큰 제목과 작은 보조 신호의 대비 |
| `r2-impl-cand-000009-a` | 판단과 근거를 나란히 읽는 evidence rail, 데이터가 장식이 아닌 설명이 되도록 한 시각화 |
| `r2-impl-cand-000014-a` | 얇은 구분선, 정의 목록, 방법론 disclosure, 날짜별 reference archive |
| `r2-impl-cand-000011-a` | 실제 관계 edge 데이터가 없어 적용하지 않음 |

아카이브의 색상이나 화면을 복제하지 않고, 현재 브리핑의 정보 순서와 데이터 계약에 맞는 문법만 재조합했다.

## 시각 품질 자체평가

공개 desktop render와 source-level responsive 검사를 기준으로 평가했다. 실제 iPhone Safari 확인 점수와는 별개다.

| 항목 | 점수 |
|---|---:|
| Typography | 9/10 |
| Information hierarchy | 9/10 |
| Editorial composition | 9/10 |
| Data visualization | 9/10 |
| Evidence UX | 9/10 |
| Microcopy | 9/10 |
| Mobile density | 9/10 |
| Color system | 9/10 |
| Archive fidelity | 9/10 |
| Overall polish | 9/10 |
| 합계 | **90/100** |

모바일 실기기와 정확한 viewport별 screenshot은 아직 확인하지 않았으므로, 이 점수는 디자인 구조와 공개 desktop render에 대한 자체평가로 한정한다.

## 데이터 품질·안전성

- NAVER News의 제목·요약·원문 링크·게시 시각을 PRIMARY SEARCH EVIDENCE로 유지
- 상위 N건에만 짧은 timeout과 제한된 concurrency로 원문 공개 정보 수집
- HTML 전문을 장기 저장하지 않음
- 403, timeout, malformed HTML, OG metadata 부재는 브리핑 실패로 승격하지 않음
- 공식 출처는 안전하게 식별되는 후보가 없을 때 억지로 생성하지 않음
- Search Trend ratio는 상대 관심지수이며, 서로 다른 batch의 절대값을 비교하지 않음
- 기사 게시 시각과 사건 발생 시각을 구분

## 로컬 검증

- `python3 -m compileall -q insight_desk scripts tests` — 통과
- `python3 -m unittest discover -s tests -v` — `25/25` 통과
- fixture `COMPLETE` 브리핑 생성 — 통과
- `python3 scripts/validate_artifact.py build/fixture-site` — 통과
- enrichment 성공·403·timeout·malformed HTML·missing OG·중복 URL — 통과
- News-only·Trends-only·PARTIAL·TOTAL_FAILURE — 통과
- secret redaction·cache 보안·Trend semantics — 통과
- 사용자 화면의 금지 문구·내부 evidence ID 검사 — 통과

## 시각 검증

- 실제 공개 Pages desktop viewport 1363px에서 root·latest·archive·날짜별 페이지 확인
- `scrollWidth <= innerWidth` 확인
- UTF-8 한글, 긴 제목 줄바꿈, 링크, disclosure, archive 이동 확인
- 실제 공개 root와 archive 화면을 screenshot으로 저장
- CSS에 320px 이상 responsive 규칙, dark mode, reduced-motion 규칙 존재 확인

정확한 320·375·390·430px 브라우저 viewport와 실제 iPhone Safari는 이 환경에서 직접 측정하지 못했다. 따라서 모바일 검증은 `PARTIAL`, iPhone 검증은 `PENDING`으로 남긴다.

## 최종 Gate

```text
LOCAL_TESTS_VERIFIED = YES (25/25)
LIVE_NCP_NEWS_VERIFIED = YES
LIVE_NCP_TREND_VERIFIED = YES
GITHUB_ACTIONS_VERIFIED = YES (31326864815)
PAGES_DEPLOYMENT_VERIFIED = YES (31327087861)
PAGES_URL_VERIFIED = YES
MOBILE_BROWSER_VERIFIED = PARTIAL (cloud 1363px + responsive source checks)
IPHONE_SAFARI_VERIFIED = PENDING
PARTIAL_FAILURE_VERIFIED = YES
TOTAL_FAILURE_PRESERVATION_VERIFIED = YES
SECRET_SCAN_VERIFIED = YES
SCHEDULED_RUN_VERIFIED = PENDING
```

## 남은 위험과 최소 조치

- 실제 iPhone Safari에서 첫 화면, 가로 밀림, 뉴스 링크, archive, 다크 모드를 사용자가 한 번 확인해야 한다.
- 첫 예약 실행이 실제로 수집·생성·배포되는지는 예약 시각 이후 확인해야 한다.
- Actions Node.js 20 경고는 실패가 아니지만 향후 action 버전 업데이트가 필요하다.

## 최종 릴리스 상태

`CONDITIONAL PASS`

핵심 기능·데이터 계약·실제 NCP 실행·Actions·Pages·공개 URL·로컬 회귀는 통과했다. 실기기와 예약 실행이 아직 확인되지 않았으므로 `PASS`로 올리지 않는다.

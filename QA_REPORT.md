# QA_REPORT

## 검사 대상

Insight Desk 모바일 정적 브리핑의 최신 UI commit `39137fb`와 Pages 실행 `31327087861`.

## 기능·데이터 검증

| 검사 | 결과 |
|---|---|
| Python compileall | 통과 |
| 전체 테스트 | `25/25` 통과 |
| normalization·deduplication·clustering·scoring | 통과 |
| Trend 상대지수 의미 계약 | 통과 |
| metadata enrichment success | 통과 |
| metadata 403·timeout·malformed HTML·missing OG fallback | 통과 |
| enrichment 실패의 상태 독립성 | 통과 |
| COMPLETE | 통과 |
| NEWS_ONLY·TRENDS_ONLY·PARTIAL | 통과 |
| TOTAL_FAILURE 기존 Pages 보존 | 통과 |
| artifact validator | 통과 |
| Secret redaction·source/cache/HTML 검사 | 통과 |

## UI·정보구조 검증

- editorial hero에 오늘의 핵심 흐름을 우선 배치
- signal strip에 사건·검색 흐름·원문 보강을 압축 배치
- story row에 사건 제목·요약·출처 범위·상세 근거를 분리
- Trend를 방향·변화폭·sparkline으로 표시
- 방법론과 한계를 `details` disclosure로 이동
- archive를 날짜별 reference list로 구성
- 기본 화면에서 내부 evidence ID 제거
- `왜 보나`, `관심도와의 관계`, `산업·투자 판단`, `선택적 metadata`, 영문 section label 제거
- light/dark token과 핑크 포인트 확인

## 원격 검증

| 검사 | 실제 결과 |
|---|---|
| CI | `31326864815` 성공 |
| Pages build | `93279078337` 성공 |
| Pages deploy | `93279203775` 성공 |
| 실제 NCP 결과 | `COMPLETE` |
| 공개 root | 새 문구·10개 story·11개 trend 확인 |
| 공개 latest | 새 문구·CSS·UTF-8·내부 링크 확인 |
| 공개 archive | 날짜별 목록·링크 확인 |
| 공개 날짜별 archive | 새 문구·methodology disclosure·57개 링크 확인 |
| 가로 오버플로 | 1363px viewport에서 없음 |

초기 재확인에서 archive 경로에 이전 문구가 보였으나 브라우저 캐시였다. 새 Pages 실행 뒤 clean URL을 다시 열어 이전 문구가 사라진 것을 확인했다.

## 시각 검증 범위

- 실제 공개 root screenshot 저장
- 실제 공개 archive screenshot 저장
- 현재 cloud browser viewport: 1363px
- CSS responsive breakpoint: 760px
- 320·375·390·430·768·1024·1440px 별도 브라우저 렌더는 이 환경에서 실행하지 않음
- 실제 iPhone Safari는 사용자 확인 대기

## 최종 Gate

```text
LOCAL_TESTS_VERIFIED = YES (25/25)
LIVE_NCP_NEWS_VERIFIED = YES
LIVE_NCP_TREND_VERIFIED = YES
GITHUB_ACTIONS_VERIFIED = YES (31326864815)
PAGES_DEPLOYMENT_VERIFIED = YES (31327087861)
PAGES_URL_VERIFIED = YES
MOBILE_BROWSER_VERIFIED = PARTIAL
IPHONE_SAFARI_VERIFIED = PENDING
PARTIAL_FAILURE_VERIFIED = YES
TOTAL_FAILURE_PRESERVATION_VERIFIED = YES
SECRET_SCAN_VERIFIED = YES
SCHEDULED_RUN_VERIFIED = PENDING
```

## 최종 판정

`CONDITIONAL PASS`

구현·자동검증·실제 원격 실행·공개 경로 검증은 통과했다. 실제 iPhone Safari와 첫 예약 실행이 남아 있어 최종 `PASS`는 보류한다.

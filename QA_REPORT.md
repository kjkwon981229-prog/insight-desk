# QA_REPORT

## 검사 대상

현재 Work에서 LEVEL D로 재구축한 Insight Desk 모바일 웹 패키지.

## 자동 검증 결과

| 검사 | 결과 |
|---|---|
| Python compileall | 통과 |
| unit/contract tests | 24/24 통과 |
| NCP endpoint/header fake contract | 통과 |
| status machine | 통과 |
| normalization/dedup/trend semantics | 통과 |
| UTF-8/mobile viewport | 통과 |
| latest/archive/data JSON | 통과 |
| Pages required files/local links | 통과 |
| live NCP News/Trend | 실제 `COMPLETE` — run `31323695534` |
| GitHub Actions build | 통과 — run `31323695534` |
| Pages artifact upload/deploy | 통과 — run `31323695534` |
| 공개 최신·archive·날짜별 URL | 통과 |
| 공개 HTML UTF-8/CSS/Secret 패턴 | 통과 |
| iPhone 실기기 | 사용자 확인 대기 |
| 첫 예약 실행 | 대기 — 07:30 KST |

## 발견·수정 사항

- 기존 프로젝트 source가 없음을 확인해 원본 복구 주장을 제거했다.
- 구형 Windows·LLM·수동 실행 계약을 현재 사용자의 원격 모바일 웹 명령과 혼합하지 않았다.
- News/Trend 결과를 하나의 성공 플래그로 합치지 않고 독립 상태로 보존했다.
- 부분 성공은 게시하고 전체 실패·렌더링 실패·검증 실패는 배포를 차단한다.
- Trend ratio를 실제 검색량으로 표시하지 않도록 문구·계산·차트 라벨을 고정했다.
- Secret이 cache·HTML·JSON·workflow 로그에 남지 않는 경계를 테스트했다.
- 날짜별 archive와 실패 시 기존 Pages 보존 경로를 분리했다.
- 1차 원격 실행에서 Pages Source 미설정으로 deploy가 404 실패한 것을 확인했다.
- 사용자가 Pages Source를 `GitHub Actions`로 설정한 뒤 2차 실행에서 deploy 성공을 확인했다.
- 상위 기사 5건 이하에만 lightweight metadata 보강을 적용하고, 원문 HTML·전문은 저장하지 않도록 했다.
- metadata success·403·timeout·missing OG·malformed/empty HTML fallback을 회귀 테스트로 잠갔다.
- 보강 provenance를 `SEARCH_SNIPPET`·`ENRICHED_METADATA`·`OFFICIAL_SOURCE`로 분리했다.
- 000002·000009·000014 archive grammar를 hero·evidence·methodology/archive에 적용하고 000011 관계도는 데이터 부족으로 제외했다.
- CSS token·다크 모드·320px 이상 overflow 방어와 전체 HTML 내부 링크 검사를 추가했다.

## 남은 확인

실제 NCP 권한과 API 호출은 기존 원격 run `31323695534`에서 `COMPLETE`로 확인했다. 이번 UI/evidence 변경은 로컬 24개 테스트와 fixture artifact에서 검증했으며, 새 commit을 원격 main에 반영한 뒤 Pages workflow 재실행이 필요하다. 남은 검증은 새 UI의 원격 배포, iPhone Safari 실기기 표시와 첫 예약 실행이다.

## 최종 Gate

```text
LOCAL_TESTS_VERIFIED = YES (24/24)
LIVE_NCP_NEWS_VERIFIED = YES
LIVE_NCP_TREND_VERIFIED = YES
GITHUB_ACTIONS_VERIFIED = YES
PAGES_DEPLOYMENT_VERIFIED = YES
PAGES_URL_VERIFIED = YES
MOBILE_BROWSER_VERIFIED = YES (자동·공개 HTML/CSS)
IPHONE_SAFARI_VERIFIED = PENDING
PARTIAL_FAILURE_VERIFIED = YES
TOTAL_FAILURE_PRESERVATION_VERIFIED = YES
SECRET_SCAN_VERIFIED = YES
SCHEDULED_RUN_VERIFIED = PENDING
```

## 이번 개선 판정

`CONDITIONAL PASS` — 로컬 구현·회귀·artifact 검증 통과. 원격 Pages 재배포와 실제 iPhone Safari 확인 전에는 새 디자인에 대해 `PASS`로 올리지 않는다.

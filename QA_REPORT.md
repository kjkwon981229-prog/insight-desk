# QA_REPORT

## 검사 대상

현재 Work에서 LEVEL D로 재구축한 Insight Desk 모바일 웹 패키지.

## 자동 검증 결과

| 검사 | 결과 |
|---|---|
| Python compileall | 통과 |
| unit/contract tests | 18/18 통과 |
| NCP endpoint/header fake contract | 통과 |
| status machine | 통과 |
| normalization/dedup/trend semantics | 통과 |
| UTF-8/mobile viewport | 통과 |
| latest/archive/data JSON | 통과 |
| Pages required files/local links | 통과 |
| live NCP call | 미실행 — Secret 없음 |
| GitHub Actions/Pages remote run | 미실행 — 연결 repository가 대상 아님 |
| iPhone 실기기 | 미검증 |

## 발견·수정 사항

- 기존 프로젝트 source가 없음을 확인해 원본 복구 주장을 제거했다.
- 구형 Windows·LLM·수동 실행 계약을 현재 사용자의 원격 모바일 웹 명령과 혼합하지 않았다.
- News/Trend 결과를 하나의 성공 플래그로 합치지 않고 독립 상태로 보존했다.
- 부분 성공은 게시하고 전체 실패·렌더링 실패·검증 실패는 배포를 차단한다.
- Trend ratio를 실제 검색량으로 표시하지 않도록 문구·계산·차트 라벨을 고정했다.
- Secret이 cache·HTML·JSON·workflow 로그에 남지 않는 경계를 테스트했다.
- 날짜별 archive와 실패 시 기존 Pages 보존 경로를 분리했다.

## 남은 확인

실제 Secret 등록 뒤 Actions에서 한 번 실행해야 NCP 권한, API 한도, Pages 설정, 실기기 표시를 확인할 수 있다. 이 작업 공간에서는 해당 원격 검증을 완료했다고 판정하지 않는다.

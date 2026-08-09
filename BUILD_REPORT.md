# BUILD_REPORT

## 구현 판정

이 작업 공간에는 기존 Insight Desk working tree가 없었다. 따라서 이 보고서는 기존 Codex source의 복구 기록이 아니라, 사용자가 현재 확정한 GitHub Actions·NAVER API HUB·GitHub Pages 계약을 기준으로 새로 구현한 결과의 검증 기록이다.

현재 판정: `RECOVERY_COMPLETE_REMOTE_PENDING`

의미: 모바일 웹 실행 코드, workflow, Pages 산출물 구조, 테스트는 준비됐지만 실제 GitHub repository·NCP Secrets·Pages URL은 이 작업 공간에서 확인하지 않았다.

## 구현 범위

- NAVER API HUB News `GET /search/v1/news`
- NAVER API HUB Trend `POST /search-trend/v1/search`
- `X-NCP-APIGW-API-KEY-ID`, `X-NCP-APIGW-API-KEY` 인증 헤더
- 환경 변수 `NCP_CLIENT_ID`, `NCP_CLIENT_SECRET`만 사용
- UTF-8 뉴스 정규화와 HTML 강조 태그·entity 제거
- URL 정규화와 추적 파라미터 제거
- canonical URL·내용 hash·제목 유사도 기반 중복 제거
- 관심사별 결정론적 군집·점수
- Trend ratio의 그룹 내부 변화 계산
- `COMPLETE`부터 `VALIDATION_FAILURE`까지 단일 상태 기계
- 부분 성공 게시와 전체 실패 시 Pages 배포 생략
- 최신 페이지·날짜별 archive·archive index·JSON data
- iPhone Safari용 responsive CSS, 다크 모드, 색 이외의 상태 텍스트
- Pages artifact 파일·UTF-8·viewport·local link·secret 검사
- GitHub Actions 수동 실행·UTC 예약 실행·concurrency·Pages artifact/deploy
- 성공 site의 GitHub Actions cache 복원으로 archive 유지

## Provenance

| 영역 | 상태 | 근거 |
|---|---|---|
| NAVER endpoint/header contract | REIMPLEMENTED | 사용자 확정 계약과 NAVER 공식 문서 |
| News collector | REIMPLEMENTED | 기존 source 미확보, 계약 기반 표준 라이브러리 구현 |
| Trend collector/batching | REIMPLEMENTED | 5개 keyword group 제한을 적용한 계약 기반 구현 |
| normalization | REIMPLEMENTED | 이전 설계 요구와 현재 모바일 출력 계약 |
| deduplication | REIMPLEMENTED | 이전 설계 요구를 보수적 규칙으로 구현 |
| clustering/scoring | REIMPLEMENTED | 결정론적 로컬 분석 계약 |
| HTML renderer | REIMPLEMENTED | GitHub Pages·iPhone Safari 요구 |
| status model | REIMPLEMENTED | 현재 사용자 명령의 상태 enum과 배포 안전 규칙 |
| GitHub Actions workflow | REIMPLEMENTED | 현재 원격 실행 계약과 GitHub 공식 Pages workflow |
| topic presets | INFERRED | Library의 v1.1 설계에 있던 기본 관심사 |
| Windows UI, Credential Manager, Scheduler, PDF | UNAVAILABLE/EXCLUDED | 모바일 웹 최종 경로에서 제외 |
| Codex 최신 working tree | UNAVAILABLE | 현재 Work·workspace·연결 GitHub에서 미확보 |

## 검증 실행

- `python -m compileall -q insight_desk scripts tests` — 통과
- `python -m unittest discover -s tests -v` — 18개 통과
- `python scripts/build_fixture_site.py` — `COMPLETE True`
- `python scripts/validate_artifact.py build/fixture-site` — 통과
- Naver endpoint/header contract fake transport — 통과
- status machine matrix — 통과
- UTF-8/mobile viewport/archive JSON — 통과

## 미검증 범위

- 실제 NCP 자격 증명으로 News·Trend 라이브 호출
- 실제 API 권한·한도·계정 정책
- 실제 GitHub Actions runner에서의 workflow 실행
- 실제 Pages URL·iPhone Safari 실기기 표시
- GitHub Actions cache의 장기 보존 정책
- 320/375/390/430px 실기기 캡처 검증

위 항목은 현재 Work에 계정 권한과 Secret이 없어 성공했다고 쓰지 않았다.

## 변경하지 않은 영역

기존 source가 없으므로 보존할 정상 코드는 확인할 수 없었다. Windows판을 재구축하지 않았고, 최종 모바일 웹 실행 경로에 Windows 전용 dependency를 넣지 않았다.

## 비용·보안 확인

- 외부 생성형 AI API·SDK 없음
- NCP Secret을 source·JSON·cache·HTML·artifact·README에 기록하지 않음
- 인증 헤더는 요청 직전에만 구성
- URL allowlist는 Naver API HUB 두 endpoint로 코드상 고정
- workflow에서 Secret 값 자체를 출력하지 않음
- API 실패 시 stale cache를 최신 성공 데이터로 가장하지 않음

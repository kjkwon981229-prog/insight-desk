# BUILD_REPORT

## 구현 판정

이 작업 공간에는 기존 Insight Desk working tree가 없었다. 따라서 이 보고서는 기존 Codex source의 복구 기록이 아니라, 사용자가 현재 확정한 GitHub Actions·NAVER API HUB·GitHub Pages 계약을 기준으로 새로 구현한 결과의 검증 기록이다.

현재 판정: `RECOVERY_COMPLETE_REMOTE_PENDING`

의미: 실제 NCP News·Trend 호출, GitHub Actions 실행, Pages 배포와 공개 URL까지 확인했다. 다만 실제 iPhone Safari 확인과 첫 예약 실행 확인은 아직 사용자 확인 대기 상태다.

## 원격 실검증 결과

| 항목 | 실제 결과 |
|---|---|
| GitHub repository | `kjkwon981229-prog/insight-desk` |
| 반영 commit | `f3d9735eb4b1c44d3437c9a6cfab72027203c66e` |
| 1차 workflow run | `31323478041` — build/실제 수집/artifact 성공, Pages 비활성으로 deploy 실패 |
| Pages 설정 조치 | 사용자가 Source를 `GitHub Actions`로 변경 |
| 2차 workflow run | `31323695534` — build 성공, deploy 성공 |
| 실제 NCP 상태 | `COMPLETE` — News·Trend 모두 성공 |
| 실제 Pages URL | <https://kjkwon981229-prog.github.io/insight-desk/> |
| 공개 HTML 검증 | 최신·archive·날짜별 archive·UTF-8·CSS·내부 링크 확인 |
| 예약 실행 | `PENDING` — 첫 예약 시각 미도래 |
| iPhone Safari | `PENDING` — 사용자 실기기 확인 대기 |

1차 실행의 실패는 코드나 NCP 인증 오류가 아니라 repository의 Pages Source가 비활성 상태였기 때문이다. Pages Source를 `GitHub Actions`로 설정한 뒤 재실행했고, 2차 실행에서 deploy까지 성공했다.

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
- 상위 5건 기본값의 선택적 lightweight metadata enrichment
- `SEARCH_SNIPPET`·`ENRICHED_METADATA`·`OFFICIAL_SOURCE` provenance 모델
- metadata 403·timeout·불완전 HTML fallback과 보강 실패의 상태 독립성
- editorial hero·evidence rail·접을 수 있는 methodology/archive를 조합한 pink token UI

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
| metadata enrichment | REIMPLEMENTED | 상위 기사 공개 metadata만 추출하고 HTML 전문은 저장하지 않는 optional 계층 |
| evidence provenance | REIMPLEMENTED | 검색 근거와 원문 metadata를 JSON·화면에서 구분 |
| Visual Design Language Archive grammar | INFERRED/REIMPLEMENTED | 첨부 archive의 실제 preview·grammar metadata를 감사한 뒤 현재 데이터 계약에 맞게 선별 |
| status model | REIMPLEMENTED | 현재 사용자 명령의 상태 enum과 배포 안전 규칙 |
| GitHub Actions workflow | REIMPLEMENTED | 현재 원격 실행 계약과 GitHub 공식 Pages workflow |
| topic presets | INFERRED | Library의 v1.1 설계에 있던 기본 관심사 |
| Windows UI, Credential Manager, Scheduler, PDF | UNAVAILABLE/EXCLUDED | 모바일 웹 최종 경로에서 제외 |
| Codex 최신 working tree | UNAVAILABLE | 현재 Work·workspace·연결 GitHub에서 미확보 |

## 검증 실행

- `python -m compileall -q insight_desk scripts tests` — 통과
- `python -m unittest discover -s tests -v` — 24개 통과
- `python scripts/build_fixture_site.py` — `COMPLETE True`
- `python scripts/validate_artifact.py build/fixture-site` — 통과
- Naver endpoint/header contract fake transport — 통과
- status machine matrix — 통과
- UTF-8/mobile viewport/archive JSON — 통과
- 실제 GitHub Actions runner의 `COMPLETE` 실행 — 통과
- 실제 NCP News·Trend 호출 — `COMPLETE`로 확인
- 실제 Pages artifact upload/deploy — 통과
- 공개 최신·archive·날짜별 archive URL — 통과
- 공개 HTML/CSS Secret·로컬 경로 패턴 검사 — 누출 없음
- metadata parser/enrichment success·403·timeout·missing OG·bounded Top-N — 통과
- fixture HTML의 provenance·methodology·pink token·dark mode·내부 링크 — 통과

## 정보 품질·디자인 개선 기록

### Evidence

NAVER Search News의 제목·description·originallink·link·pubDate는 PRIMARY SEARCH EVIDENCE로 유지한다. 점수가 높은 상위 5건만 원문 URL에 짧은 timeout과 최대 3개 worker로 접근해 title/OG metadata/canonical/publisher/time을 추출한다. 원문 HTML은 저장하지 않고, 실패는 검색 수집 실패나 `PARTIAL`로 승격하지 않는다. 공식 출처 자동 탐색은 안전한 후보 식별 계약이 없으므로 이번 범위에서 억지로 활성화하지 않았다.

### Design sources

| Archive grammar | Insight Desk에 채택한 문법 |
|---|---|
| `r2-impl-cand-000002-a` | 핵심 판단 하나를 먼저 보여주는 editorial hero |
| `r2-impl-cand-000009-a` | 사건 카드의 지표·근거·판단 연결과 evidence rail |
| `r2-impl-cand-000014-a` | 데이터 기준·방법론·archive의 reference hierarchy |
| `r2-impl-cand-000011-a` | 현재 근거 데이터에 관계 edge가 없어 적용하지 않음 |

핑크는 `--accent`, `--accent-soft`, `--accent-dark` 토큰으로 active navigation·section marker·근거 rail·trend 강조에만 사용한다. 상태는 텍스트와 badge를 함께 사용하며 색만으로 판정하지 않는다.

## 남은 확인 범위

- 실제 iPhone Safari에서 첫 화면·가로 밀림·뉴스 링크·archive·다크 모드 확인
- 첫 예약 실행에서 자동 수집·게시까지 이어지는지 확인
- GitHub Actions cache의 장기 보존 정책

자동 모바일 검증은 artifact의 viewport·overflow·UTF-8 계약과 공개 HTML/CSS 로드 상태까지 확인했다. 실제 iPhone 화면은 별도 확인 전까지 성공으로 판정하지 않는다.

## 최종 Gate

```text
LOCAL_TESTS_VERIFIED = YES (24/24)
LIVE_NCP_NEWS_VERIFIED = YES
LIVE_NCP_TREND_VERIFIED = YES
GITHUB_ACTIONS_VERIFIED = YES (run 31323695534)
PAGES_DEPLOYMENT_VERIFIED = YES
PAGES_URL_VERIFIED = YES
MOBILE_BROWSER_VERIFIED = YES (자동·공개 HTML/CSS 검증)
IPHONE_SAFARI_VERIFIED = PENDING
PARTIAL_FAILURE_VERIFIED = YES (로컬 회귀 경로)
TOTAL_FAILURE_PRESERVATION_VERIFIED = YES (로컬 회귀 경로)
SECRET_SCAN_VERIFIED = YES
SCHEDULED_RUN_VERIFIED = PENDING
```

## 변경하지 않은 영역

기존 source가 없으므로 보존할 정상 코드는 확인할 수 없었다. Windows판을 재구축하지 않았고, 최종 모바일 웹 실행 경로에 Windows 전용 dependency를 넣지 않았다.

## 비용·보안 확인

- 외부 생성형 AI API·SDK 없음
- NCP Secret을 source·JSON·cache·HTML·artifact·README에 기록하지 않음
- 인증 헤더는 요청 직전에만 구성
- URL allowlist는 Naver API HUB 두 endpoint로 코드상 고정
- workflow에서 Secret 값 자체를 출력하지 않음
- API 실패 시 stale cache를 최신 성공 데이터로 가장하지 않음
- metadata cache에는 추출된 짧은 공개 필드만 저장하고 원문 HTML·기사 전문은 저장하지 않음

## 이번 개선 릴리즈 판정

`CONDITIONAL PASS`

로컬 코드·fixture·회귀 테스트·artifact 검증은 통과했다. 원격 main 반영 후에는 기존 workflow를 수동 실행해 새 UI가 실제 Pages artifact로 배포되는지 확인해야 하며, iPhone Safari와 예약 실행의 기존 `PENDING` 상태는 유지한다.

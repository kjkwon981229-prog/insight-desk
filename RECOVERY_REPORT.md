# RECOVERY_REPORT

## 복구 레벨

`LEVEL D — CONTRACT RECONSTRUCTION`

현재 Work에는 Insight Desk source, ZIP, workflow, generated site가 없었다. 연결된 GitHub repository는 `kjkwon981229-prog/-` 하나였지만, 확인 결과 Insight Desk가 아닌 `VOCA Loop PWA Icon Check`였고 관련 검색 결과도 없었다. Library에서 확인된 자료는 `INSIGHT_DESK_ARCHITECT_v1.1_ZERO_COST_READY.md`, 해당 QA 문서, 구형 `MASTER_SPEC.md`와 Windows 설계 문서였다.

## 확보한 자료

- v1.1 ZERO COST Windows 설계 계약
- v1.1 ZERO COST QA 문서
- 구형 master specification
- 현재 사용자가 제공한 모바일 웹·Actions·Pages·NCP 계약
- NAVER API HUB와 GitHub Pages 공식 문서
- 실제 생성된 GitHub repository `kjkwon981229-prog/insight-desk`
- 실제 workflow run 2회와 공개 Pages URL

## 확보하지 못한 자료

- 최신 Codex working tree
- 기존 Python source와 49개 파일 구조
- 기존 테스트 92개
- 기존 BUILD_REPORT/README/workflow
- 기존 generated HTML/PDF/SQLite cache
- 고장 난 노트북의 원본 Codex working tree
- 실제 iPhone Safari 화면 확인 결과
- 첫 예약 실행 결과

## Provenance 분류

### RECOVERED

- Library 설계 문서의 제품명·기본 관심사·NAVER endpoint/header 의미
- 사용자가 현재 명령에서 확정한 remote mobile web contract

### REIMPLEMENTED

- 모든 실행 source
- News/Trend collectors
- deterministic pipeline
- status machine
- mobile static renderer
- artifact validator
- GitHub Actions workflows
- regression tests

### INFERRED

- 기본 관심사별 검색어와 trend group의 최소 프리셋
- Actions cache를 이용한 성공 site archive 유지 방식

### UNAVAILABLE

- 기존 Windows application source
- 최신 mobile migration tree
- 실제 iPhone Safari 검증 결과
- 첫 예약 실행 결과

## 연속성 수준

제품 목표와 일부 설계 계약은 이어졌지만, 코드 수준의 연속성은 확인되지 않는다. 따라서 이 결과물을 “Codex 원본 working tree 복구본”이라고 부르지 않는다. 현재 산출물은 원본 유실 뒤의 계약 기반 재구축본이다.

## 원격 검증 결과

- 1차 run `31323478041`: News·Trend와 build는 성공했으나 Pages Source 미설정으로 deploy가 404 실패했다.
- 사용자가 Pages Source를 `GitHub Actions`로 설정했다.
- 2차 run `31323695534`: 실제 NCP `COMPLETE`, artifact 검증·업로드·Pages deploy 모두 성공했다.
- 공개 URL: <https://kjkwon981229-prog.github.io/insight-desk/>
- 최신·archive·날짜별 archive·UTF-8·CSS·공개 HTML Secret 패턴 검사를 통과했다.

## 사용자에게 필요한 다음 최소 행동

1. 위 Pages URL을 iPhone Safari에서 연다.
2. 첫 화면, 가로 밀림 없음, 뉴스 링크 하나, archive, 다크 모드를 확인한다.
3. 확인 후 결과를 알려준다.

예약 실행은 매일 07:30 KST로 설정되어 있으며, 실제 첫 예약 실행 전까지 `PENDING`이다.

## 최종 Gate

```text
LOCAL_TESTS_VERIFIED = YES (19/19)
LIVE_NCP_NEWS_VERIFIED = YES
LIVE_NCP_TREND_VERIFIED = YES
GITHUB_ACTIONS_VERIFIED = YES (31323695534)
PAGES_DEPLOYMENT_VERIFIED = YES
PAGES_URL_VERIFIED = YES
MOBILE_BROWSER_VERIFIED = YES (자동·공개 HTML/CSS)
IPHONE_SAFARI_VERIFIED = PENDING
PARTIAL_FAILURE_VERIFIED = YES
TOTAL_FAILURE_PRESERVATION_VERIFIED = YES
SECRET_SCAN_VERIFIED = YES
SCHEDULED_RUN_VERIFIED = PENDING
```

## 최종 판정

`RECOVERY_COMPLETE_REMOTE_PENDING`

실제 원격 수집·분석·Pages 배포까지 확인했지만, iPhone Safari 실기기 확인과 첫 예약 실행은 아직 남아 있다. 원본 Codex working tree를 복구한 것이 아니라 LEVEL D 계약 기반 재구축본이라는 provenance는 유지한다.

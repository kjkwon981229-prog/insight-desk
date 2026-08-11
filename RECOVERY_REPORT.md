# RECOVERY_REPORT

## 현재 post-Sol 상태

- post-Sol code closure HEAD: `421bae43a11f1e47bd4ce26f6b259927193cd88a`
- 기준 CI #190: Python 281개 및 Push Worker 13개 통과
- 이번 local closure: Python 289개 및 Push Worker 13개 통과
- Run #92 human acceptance 실패는 Sol event/fact ownership closure 전의 historical regression이다.
- Run #93 general production smoke는 build·artifact·machine editorial acceptance·Pages·push까지 통과했지만 KBO·경제 targeted live reproof는 실행되지 않았다.
- manual workflow dispatch는 실행하지 않았다. 다음 live evidence는 실제 `07:30 KST` schedule이다.
- 현재 판정: `READY_FOR_ACTUAL_SCHEDULED_ACCEPTANCE`

## 복구 수준

`LEVEL D — CONTRACT RECONSTRUCTION`

최신 Codex working tree와 기존 Windows source는 확보하지 못했다. 따라서 원본 코드 복구라고 주장하지 않고, 확정된 NAVER API·GitHub Actions·GitHub Pages·모바일 웹 계약을 기준으로 재구축한 결과로 기록한다.

## 자료 provenance

### 확보한 자료

- 모바일 웹·Actions·Pages·NCP 확정 계약
- 관심사·상태 모델·콘텐츠 품질 요구사항
- Visual Design Language Archive와 아이콘 탐구 보드
- 실제 GitHub repository와 workflow
- 실제 Pages 공개 결과

### 확보하지 못한 자료

- 최신 Codex working tree
- 기존 Windows application source
- 원래 92개 테스트와 원래 generated site
- 기존 SQLite/cache/dist 산출물
- 실제 iPhone Safari 확인 결과
- 첫 예약 실행 결과

### REIMPLEMENTED

- News·Trend collector와 deterministic analysis pipeline
- metadata enrichment·provenance·fallback
- StoryFacts 기반 synthesis·contextual evidence·next signal
- topic-local selection·coverage·conditional·saturation·cross-topic attribution
- mobile static renderer·freshness·PWA shell
- artifact validator·GitHub Actions·Pages workflow
- 회귀 테스트·selection audit artifact

### RECOVERED

- GitHub에 반영된 현재 remote workflow와 공개 Pages 결과
- Library에서 확인한 승인 아이콘 보드의 Candidate 5 artwork. 보드의 해당 영역을 새로 그리지 않고 추출·리사이즈했다.

### INFERRED

- 기본 다섯 관심사와 query family 구성
- archive 보존·freshness 표현
- archive grammar와 editorial panel을 모바일 웹으로 번역한 방식

### UNAVAILABLE / EXCLUDED

- Windows UI·Credential Manager·Task Scheduler·PyInstaller·desktop PDF workflow
- 원본 Codex source 수준의 연속성

## Historical remote continuity

- source commit: `23c572afe7bd8e2240f1cc6bda4431dd2572ca44`
- CI: [Run · 31334275366](https://github.com/kjkwon981229-prog/insight-desk/actions/runs/31334275366) 성공, 48 tests
- Pages: [Run #12 · 31334331280](https://github.com/kjkwon981229-prog/insight-desk/actions/runs/31334331280) build/deploy 성공, 실제 NCP `COMPLETE`
- 공개 주소: [Insight Desk](https://kjkwon981229-prog.github.io/insight-desk/)
- Pages artifact `9043866757`와 Candidate 5 icon/head contract를 공개 URL에서 재확인

실제 live 콘텐츠 재감사에서 잘린 snippet 조각과 무의미한 generic summary 가능성을 발견해 `23c572a`에서 수정했다. 수정 후 로컬 48개 테스트와 Pages Run #12 실제 결과를 다시 통과했다.

## Historical recovery 상태

이전 Pages Run #12는 배포 자체에는 성공했지만 실제 콘텐츠 selection false pass가 확인되어 완료 판정을 철회했다. 현재 작업은 원본 복구가 아니라, 그 false pass를 일반화된 deterministic retrieval/relevance/event/evidence/novelty/selection gate로 교정하는 production recovery다.

```text
BASELINE_CI_190 = PASS (281 Python + 13 Worker)
LOCAL_POST_SOL_CLOSURE = PASS (289 Python + 13 Worker)
RUN93_GENERAL_PRODUCTION_SMOKE = PASS
RUN92_TARGETED_KBO_LIVE_REPROOF = PENDING
RUN92_TARGETED_ECON_LIVE_REPROOF = PENDING
MANUAL_WORKFLOW_DISPATCH = NOT RUN
ACTUAL_SCHEDULE_0730 = PENDING
PAGES_DEPLOYMENT_VERIFIED = PASS (Run #93)
PAGES_URL_VERIFIED = PASS (Run #93)
MOBILE_BROWSER_VERIFIED = PARTIAL
IPHONE_SAFARI_VERIFIED = PENDING
SCHEDULED_RUN_VERIFIED = PENDING
SECRET_SCAN_VERIFIED = YES
PWA_ICON_VERIFIED = YES (artifact + public page head)
```

## 사용자에게 필요한 최소 행동

1. [Pages 주소](https://kjkwon981229-prog.github.io/insight-desk/)를 iPhone Safari에서 연다.
2. 첫 화면의 가로 밀림, 뉴스 원문 링크, archive, 다크 모드를 확인한다.
3. 첫 07:30 KST 예약 실행은 실제 실행 후 확인한다.

## 현재 판정

`READY_FOR_ACTUAL_SCHEDULED_ACCEPTANCE`

실제 schedule event의 selected stories 전수 audit, push provenance, iPhone 표시·tap/open 및 watchdog 확인 전에는 `PRODUCTION_FINAL`로 올리지 않는다.

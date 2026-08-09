# RECOVERY_REPORT

## 복구 수준

`LEVEL D — CONTRACT RECONSTRUCTION`

최신 Codex working tree와 기존 Windows source는 확보하지 못했다. 따라서 현재 결과물을 원본 코드 복구본이라고 주장하지 않고, 확정된 NAVER API·GitHub Actions·GitHub Pages·모바일 웹 계약을 기준으로 재구축한 결과로 기록한다.

## 자료와 provenance

### 확보한 자료

- 모바일 웹·Actions·Pages·NCP 확정 계약
- 제품·관심사·상태 모델 요구사항
- 첨부 Visual Design Language Archive
- 실제 생성된 GitHub 저장소와 원격 workflow
- 실제 Pages 공개 결과
- 첨부 Visual Design Language Archive의 실제 preview와 implementation 자료

### 확보하지 못한 자료

- 최신 Codex working tree
- 기존 Windows application source
- 기존 92개 테스트와 원래 generated site
- 기존 SQLite/cache/dist 산출물
- 실제 iPhone Safari 확인 결과
- 첫 예약 실행 결과

### REIMPLEMENTED

- News·Trend collector
- normalization·deduplication·clustering·scoring
- deterministic rule engine
- metadata enrichment과 provenance
- `StoryFacts` 기반 결정론적 summary·headline synthesis와 story-specific next signal
- mobile static renderer
- status machine·artifact validator
- GitHub Actions·Pages workflow
- 회귀 테스트

### INFERRED

- 기본 관심사 preset
- 일부 archive 유지 전략
- 첨부 디자인 문법의 제품 적용 방식

### UNAVAILABLE / EXCLUDED

- Windows UI·Credential Manager·Task Scheduler·PyInstaller·PDF desktop workflow
- 기존 Codex source 수준의 연속성

## 원격 연속성

- 최신 콘텐츠 commit: `39028d131594d75c98d485b5234b6fe3c6fd82cf`
- CI run: `31330863299` 성공
- Pages run: `31330889761` 성공
- Pages build: `93288833389` 성공
- Pages deploy: `93289017742` 성공
- 공개 주소: [Insight Desk](https://kjkwon981229-prog.github.io/insight-desk/)
- 실제 공개 root·latest·archive·날짜별 archive 확인 완료
- 실제 NCP News·Trend 결과가 `COMPLETE`로 게시됨

## 현재 상태

```text
LOCAL_TESTS_VERIFIED = YES (34/34)
LIVE_NCP_NEWS_VERIFIED = YES
LIVE_NCP_TREND_VERIFIED = YES
GITHUB_ACTIONS_VERIFIED = YES
PAGES_DEPLOYMENT_VERIFIED = YES
PAGES_URL_VERIFIED = YES
MOBILE_BROWSER_VERIFIED = PARTIAL
IPHONE_SAFARI_VERIFIED = PENDING
SCHEDULED_RUN_VERIFIED = PENDING
SECRET_SCAN_VERIFIED = YES
```

## 사용자에게 필요한 최소 행동

1. [Pages 주소](https://kjkwon981229-prog.github.io/insight-desk/)를 iPhone Safari에서 연다.
2. 첫 화면에 가로 밀림이 없는지 확인한다.
3. 뉴스 링크 하나를 연다.
4. 아카이브를 연다.
5. iPhone 다크 모드에서 다시 확인한다.

예약 실행은 매일 07:30 KST로 설정되어 있으며, 실제 첫 실행 전까지 `PENDING`이다.

## 최종 판정

`RECOVERY_COMPLETE_REMOTE_PENDING`

원격 코드·실제 NCP 수집·Actions·Pages·공개 URL까지 확인했지만, 실제 iPhone Safari와 첫 예약 실행은 아직 확인하지 않았다.

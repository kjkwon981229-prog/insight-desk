# Insight Desk package manifest

복구 레벨: `LEVEL D — CONTRACT RECONSTRUCTION`

원본 Windows working tree가 아니라 확정된 모바일 웹 계약을 기준으로 재구축한 프로젝트다.

## 핵심 구성

- `insight_desk/`: 수집·정규화·중복 제거·군집·점수·선정·합성·정적 renderer
- `config/topics.json`: 다섯 관심사, query family, candidate budget, selection cap의 SSOT
- `assets/icons/`: 승인 Candidate 5에서 추출·리사이즈한 PWA icon 세트
- `manifest.webmanifest`: standalone PWA 계약과 icon provenance
- `.github/workflows/insight-desk-pages.yml`: 수동·예약 수집과 Pages 배포
- `.github/workflows/ci.yml`: compile·tests·fixture artifact 검증
- `tests/`: 핵심·selection·synthesis·PWA 회귀 테스트
- `BUILD_REPORT.md`, `QA_REPORT.md`, `RECOVERY_REPORT.md`: provenance·검증·남은 external acceptance

## 사용자 설정

- GitHub repository에 업로드
- `NCP_CLIENT_ID`, `NCP_CLIENT_SECRET` repository secrets 등록
- Pages Source를 GitHub Actions로 설정
- Actions에서 Pages workflow 수동 실행

## 검증된 범위

- Python compileall
- `48/48` unittest
- 10-day selection matrix
- fixture COMPLETE 및 synthesis A–J site
- artifact validator
- UTF-8·local links·internal ID·secret·PWA head/icon 검사
- CI `31334275366` 성공
- Pages Run #12 `31334331280` build/deploy 성공, 실제 NCP `COMPLETE`
- 공개 URL의 PWA head·icon·latest/archive/date 경로 재확인

## 원격 보류 범위

- 실제 iPhone Safari physical-device acceptance
- 첫 07:30 KST scheduled run acceptance

# Insight Desk package manifest

복구 레벨: `LEVEL D — CONTRACT RECONSTRUCTION`

이 패키지는 기존 Codex working tree 복구본이 아니라, 현재 확정된 모바일 웹 계약을 기준으로 재구축한 프로젝트다.

핵심 실행:

- `python -m insight_desk.cli`
- `.github/workflows/insight-desk-pages.yml`
- `python -m unittest discover -s tests -v`

배포 전 사용자 입력:

- GitHub repository 업로드
- `NCP_CLIENT_ID` Secret 등록
- `NCP_CLIENT_SECRET` Secret 등록
- GitHub Pages Source를 GitHub Actions로 설정

검증된 로컬 범위:

- Python compileall
- 18개 unit/contract/integration-style test
- fixture 기반 COMPLETE site 생성
- Pages artifact validator
- UTF-8·모바일 viewport·archive·local link 검사

원격 미검증 범위:

- 실제 NCP API 호출
- 실제 GitHub Actions run
- 실제 Pages URL
- iPhone Safari 실기기 표시

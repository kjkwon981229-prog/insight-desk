# Insight Desk

Insight Desk는 NAVER Search News API와 NAVER Search Trend API에서 받은 자료를 외부 생성형 AI 없이 결정론적으로 정리해, GitHub Actions가 매일 정적 모바일 웹으로 게시하는 개인용 브리핑 시스템이다.

최종 사용 경로는 다음과 같다.

`GitHub Actions → NAVER API HUB → 정규화·중복 제거·군집·점수·규칙 분석 → GitHub Pages → iPhone Safari`

뉴스 전문, 외부 AI API, 유료 서버, NCP Server·Object Storage·Cloud Functions·별도 데이터베이스는 사용하지 않는다. NCP 자격 증명은 GitHub Repository Secrets에서만 읽는다.

## 포함된 구성

- `insight_desk/`: 수집·분석·상태 기계·정적 HTML 렌더러
- `config/topics.json`: 관심사와 검색어 프리셋
- `.github/workflows/insight-desk-pages.yml`: 수동·매일 실행과 Pages 배포
- `.github/workflows/ci.yml`: 컴파일·테스트·fixture artifact 검증
- `tests/`: 핵심 회귀 테스트
- `BUILD_REPORT.md`: 구현 범위와 검증 결과
- `RECOVERY_REPORT.md`: 원본 확보 상태와 복구 provenance

## iPhone에서 최초 연결할 때 필요한 최소 행동

Git CLI는 기본 경로로 요구하지 않는다.

1. GitHub에서 새 repository를 만들거나 사용 가능한 개인 repository를 준비한다.
2. 이 프로젝트의 파일과 폴더를 repository에 업로드한다. `.github/workflows/` 폴더까지 포함해야 한다.
3. NAVER Cloud Platform에서 기존에 노출된 적이 있는 키는 폐기하고 새 Client ID·Client Secret을 발급한다.
4. repository의 `Settings`를 연다.
5. `Secrets and variables` → `Actions`로 이동한다.
6. `New repository secret`을 선택한다.
7. 다음 두 이름을 정확히 등록한다.
   - `NCP_CLIENT_ID`
   - `NCP_CLIENT_SECRET`
8. 값은 대화나 코드에 붙여넣지 말고 GitHub 입력란에만 등록한다.
9. `Settings` → `Pages`에서 Build and deployment의 Source를 `GitHub Actions`로 선택한다.
10. repository의 `Actions` 탭에서 `Insight Desk Daily Pages`를 고르고 `Run workflow`를 누른다.
11. 실행이 성공하고 `deploy` 작업이 끝날 때까지 기다린다. Secret이 없거나 NAVER API가 실패하면 전체 실패로 기록하고 기존 Pages를 덮어쓰지 않는다.
12. `Settings` → `Pages`에 표시된 Pages 주소를 연다. 일반적인 프로젝트 Pages 주소는 `https://사용자명.github.io/저장소명/` 형태다.
13. iPhone Safari에서 페이지를 열고 공유 버튼 → `홈 화면에 추가`를 선택한다.
14. 다음부터는 홈 화면 아이콘으로 최신 브리핑과 `아카이브`를 연다.
15. `schedule`은 UTC 기준으로 등록되어 있으며 현재 workflow는 매일 22:30 UTC, 즉 한국 시간 다음 날 07:30에 실행되도록 설정되어 있다.

## 상태와 실패 보호

상태는 `COMPLETE`, `NEWS_ONLY`, `TRENDS_ONLY`, `PARTIAL`, `TOTAL_FAILURE`, `RENDER_FAILURE`, `VALIDATION_FAILURE` 중 하나로 단일 함수에서 판정한다.

- 뉴스와 트렌드가 모두 성공하면 `COMPLETE`
- 한쪽만 성공하면 성공한 자료만 게시
- 일부 관심사·배치만 실패하면 `PARTIAL`
- 둘 다 실패하거나 자격 증명이 없으면 새 Pages artifact를 업로드하지 않음
- 렌더링·검증 실패도 새 배포를 하지 않음

따라서 전체 실패가 발생해도 마지막 정상 Pages 결과는 유지된다. 아카이브는 성공한 workflow의 정적 site를 GitHub Actions cache에서 이어받으며, cache가 만료된 경우에는 이후 성공 실행부터 다시 축적된다.

## 데이터 의미

Search Trend의 `ratio`는 실제 검색 횟수가 아니라 상대 검색지수다. 서로 다른 API 요청 batch의 절대 ratio를 한 순위로 비교하지 않고, 각 그룹의 직전 구간 대비 변화만 표시한다.

뉴스는 제목·검색 요약·원문 링크만 사용한다. 게시 시각과 사건 발생 시각을 동일시하지 않으며, 제공 자료만으로 직접 인과관계를 확정하지 않는다.

## 로컬 검증

Python 3.11 이상에서 다음을 실행할 수 있다.

```bash
python -m compileall -q insight_desk scripts tests
python -m unittest discover -s tests -v
python scripts/build_fixture_site.py
python scripts/validate_artifact.py build/fixture-site
```

fixture 실행은 실제 NAVER 연결 성공을 의미하지 않는다. 실제 연결은 GitHub Secrets를 등록한 뒤 Actions에서만 확인한다.

## 공식 계약

- [NAVER API HUB 뉴스 검색](https://api.ncloud-docs.com/docs/naver-api-hub-search-news)
- [NAVER API HUB 검색어 트렌드](https://api.ncloud-docs.com/docs/naver-api-hub-search-trend)
- [GitHub Pages 사용자 정의 workflow](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)

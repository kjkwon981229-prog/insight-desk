# QA_REPORT

## 검사 대상

최종 소스 commit `23c572afe7bd8e2240f1cc6bda4431dd2572ca44`, 로컬 생성 artifact, 실제 NCP Pages Run #12.

## 선택·콘텐츠 검증

| 검사 | 결과 |
|---|---|
| 다섯 관심사 SSOT·query family | 통과 |
| topic candidate budget·fair retrieval | 통과 |
| topic-local ranking·coverage floor | 통과 |
| conditional topic omission·no filler | 통과 |
| saturation cap·cap relaxation | 통과 |
| publisher diversity vs raw source count | 통과 |
| cross-topic attribution | 통과 |
| topic-diverse enrichment allocation | 통과 |
| overview not first story·no single-story hero | 통과 |
| 10-day selection matrix | 통과 |
| raw snippet·ellipsis·cluster debug copy 차단 | 통과 |
| contextual next signal·compact trend | 통과 |
| live content 잘린 snippet/key fact 누출 차단 | 통과 |
| live content generic summary·저신호 filler 차단 | 통과 |

## PWA·artifact 검증

- 모든 root/latest/archive/date page에 manifest, favicon, Apple touch icon, theme color, Apple web-app meta, viewport contract 존재 — 로컬·공개 페이지 통과
- `display: standalone`, 아이콘 192/512, Candidate 5 provenance — 통과
- manifest icon 파일 존재·경로 검사 — 통과
- `viewport-fit=cover`, safe-area CSS — 통과
- service worker 미포함 — 의도한 정책과 일치
- internal topic ID·selection audit·local filesystem path·secret 공개 차단 — 통과
- local link·UTF-8·artifact validator — 통과

## 자동 테스트

```text
compileall = PASS
unittest = PASS (48/48)
fixture site = PASS
synthesis fixture A-J = PASS
artifact validation = PASS
Ruff F/I (변경 PWA/validator 파일) = PASS
Ruff 전체 = NOT CLAIMED (기존 E501)
mypy = NOT CLAIMED (환경 미설치)
```

## 원격 검증

| 검사 | 결과 |
|---|---|
| 최종 CI | 성공 · `31334275366` |
| Pages Run #12 | build `93297582968` / deploy `93297710682` 성공 · `31334331280` |
| 실제 NCP News/Trend | `COMPLETE`, `publish=true` · Run #12 |
| artifact validation | 성공 · Pages artifact `9043866757` |
| 공개 URL | 정상 · manifest/icon/apple head, UTF-8, internal links, archive 확인 |

## 브라우저 범위

- cloud browser desktop viewport `1363px`에서 실제 공개 root/latest/archive/date 페이지의 UTF-8·내부 링크·가로 overflow·금지 문구·archive 이동·PWA head를 확인했다.
- 실제 live 콘텐츠에서 `...`/`…`, `관련 내용이 확인됐다`, cluster debug 문구 및 내부 topic ID가 사용자 화면에 없는 것을 확인했다.
- 정확한 320/375/390/430/768/1024/1440px 각각의 브라우저 렌더와 실제 iPhone Safari는 이 환경에서 직접 완료하지 않았다.
- iPhone 상태는 사용자의 physical-device acceptance 후에만 `YES`로 바꾼다.

## 최종 게이트(현재 단계)

```text
LOCAL_TESTS_VERIFIED = YES (48/48)
LIVE_NCP_NEWS_VERIFIED = YES (Run #12)
LIVE_NCP_TREND_VERIFIED = YES (Run #12)
GITHUB_ACTIONS_VERIFIED = YES (CI 31334275366; Pages 31334331280)
PAGES_DEPLOYMENT_VERIFIED = YES
PAGES_URL_VERIFIED = YES
MOBILE_BROWSER_VERIFIED = PARTIAL
IPHONE_SAFARI_VERIFIED = PENDING
PARTIAL_FAILURE_VERIFIED = YES
TOTAL_FAILURE_PRESERVATION_VERIFIED = YES
SECRET_SCAN_VERIFIED = YES
SCHEDULED_RUN_VERIFIED = PENDING
```

## 현재 판정

`CONDITIONAL_PASS_EXTERNAL_ACCEPTANCE_ONLY`

외부에 남은 것은 physical iPhone Safari acceptance와 실제 첫 scheduled `07:30 KST` event뿐이다. 현재 코드·원격 배포 gate는 통과했다.

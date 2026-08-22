# Insight Desk — UI Re-Foundation

## Pink Editorial Intelligence / Soft Geometry V3

Status: `UI_DESIGN_FREEZE_V3` + `IMPLEMENTATION_PROTOTYPE_PASS` + `RENDERER_MAPPING_PASS`
Branch: `ui-refoundation-pink-v2`
Figma working file: `https://www.figma.com/design/hThXgfkZHUgI8BzOcFzqlU`

This document is the authoritative design/source ledger for the Insight Desk UI redesign.
The visual direction is frozen by user approval. Further UI work must implement or regression-test this direction rather than restart visual exploration.

## 1. Product character

Insight Desk must feel like a refined personal intelligence briefing rather than a generic news app, AI dashboard, BI tool, productivity app, or entertainment feed.

Target character:
- editorial intelligence
- personal briefing
- refined
- compact
- premium but not ornamental
- quiet confidence
- evidence-aware
- clearly non-generic

## 2. Pink remains a first-class brand primitive

Anchor palette:
- Brand pink: `#C35B78`
- Strong pink: `#943C59`
- Soft pink surface: `#F0D9E0`
- Pink ink: `#7D3049`
- Dark-mode pink: `#D27A98`
- Dark-mode strong pink: `#F0A1B9`

Primary uses:
1. current selection / active navigation
2. editorial focus / important change
3. evidence or verified emphasis
4. brand recognition
5. interaction focus

Pink must not flood every surface. Warm neutral and charcoal remain the default field so pink retains information value.

## 3. Product architecture

The product uses multiple view grammars rather than forcing one layout everywhere.

### D3 — Daily Edition / Soft Editorial
Primary home experience.
- daily edited edition rather than generic card feed
- one dominant event can lead the page
- cover story uses a large soft feature surface
- secondary stories remain editorially aligned

### E — Event Ledger
Event continuity/history experience.
- article feed is not the core mental model
- same event persists across state changes
- timeline expresses continuity across yesterday / today / future

**Data readiness:** design frozen, production renderer NOT ready. The current `ContractBundle` is a snapshot and does not contain persistent event-state history. Real E rendering must remain disabled until a history contract exists. Do not fabricate transitions from article fetch/publish timestamps.

### F3 — Split Desk / Soft Evidence
Desktop event-detail/evidence experience.
- master-detail structure
- event list on the left
- selected event facts, evidence, verification verdict, why-it-matters and optional watch-next on the right
- no numeric confidence is displayed because the current core contract does not define one

### G3 — Mobile Focus
Mobile focused-consumption experience.
- one event at a time
- pink may occupy a larger background field
- one dominant rounded event surface contains the current judgment unit
- state / evidence / optional watch-next appear as nested soft blocks
- mobile and desktop share the same factual view model

Mapping:
- Home → D3
- Event continuity/history → E when history contract exists
- Evidence/detail → F3
- Mobile focused consumption → G3

## 4. Soft Geometry V3 — frozen shape language

The supplied reference image was used only to clarify the desired rounded/blocky feel. Its layout, color system, typography, productivity-app structure and interaction model are NOT design references for Insight Desk.

Core rule:
> Straight lines organize the page. Rounded surfaces contain the units the user actually judges.

Radius hierarchy:
- `14px` — micro elements / small internal states
- `20px` — rows / compact information blocks
- `28px` — normal event and evidence cards
- `36px` — featured event / large evidence panel
- `44px` — mobile focus / dominant single-event surface

Where supported, moderate corner smoothing should create a squircle-like blunt silhouette rather than a simple geometric rounded rectangle.

Remain straight:
- page/canvas edges
- masthead/grid alignment
- major editorial rules
- timeline axes where continuity matters
- structural column boundaries

Become soft:
- cover story surfaces
- secondary event blocks
- evidence rows/panels
- selected event blocks
- mobile focus card
- state/value blocks
- watch-next block

Avoid:
- rounding every container indiscriminately
- excessive pill UI
- floating-card dashboard look
- generic iOS clone aesthetics
- glassmorphism
- generic AI gradients
- large soft shadows
- productivity-app visual language

## 5. Typography

Typography carries more hierarchy than decoration.

Rules:
- large editorial headline with tight tracking
- compact metadata labels
- Korean body text optimized for sustained reading
- stable numeric values only when the source contract actually provides them
- unnecessary English avoided in product content
- English used only where it functions as a concise system/brand label

## 6. Responsive targets

Frozen implementation targets:
- mobile 390px
- mobile 430px
- tablet portrait
- desktop 1280px+

Mobile is not a shrunken desktop. At mobile widths the home presentation changes from D3 to G3 while preserving the same factual event view model.

## 7. Required product states

Implementation/regression must support:
- normal briefing
- one important story only
- 8–10 story heavy day
- no qualifying stories
- partial source/verifier failure
- evidence available / unavailable
- verification indeterminate
- future / ongoing / completed / cancelled
- long Korean headline
- long Korean summary
- dark mode
- push permission state

## 8. Freeze decision

User approved Soft Geometry V3 as the final UI direction on 2026-08-23.

Therefore:
- `UI_DESIGN_FREEZE_V3 = YES`
- Pink retained = YES
- Soft Geometry shape grammar frozen = YES
- Multi-mode architecture frozen = YES
- Radical visual re-exploration = STOP

The previous A/A2 direction is no longer primary. D3 / E / F3 / G3 form the frozen UI architecture.

## 9. Implementation prototype result

Isolated implementation lives under:
- `design/prototype-v3/index.html`
- `design/prototype-v3/prototype.css`
- `design/prototype-v3/prototype.js`

Implemented:
- D3 desktop/tablet home
- E visual reference
- F3 evidence/detail
- G3 mobile home at <=640px
- 14/20/28/36/44 radius tokens
- light/dark token support
- 390/430/tablet/desktop responsive breakpoints
- supported / pending / context-only / partial-source-failure sample states
- focus-visible and reduced-motion hooks

CI result after PR #38:
- V3 prototype contract tests PASS
- clean-room benchmark PASS
- core/API import boundary PASS
- preserved PWA/config validation PASS
- preserved Push Worker tests PASS

Production `assets/css/style.css` and production renderer were not changed.

## 10. Renderer mapping result

Mapping implementation:
- `design/prototype-v3/view_model.py`
- `design/prototype-v3/RENDERER_MAPPING.md`

Current core fields that can populate D3/F3/G3:
- `RenderedBriefing.entries`
- `RenderedEntry.headline`
- `RenderedEntry.summary`
- `RenderedEntry.render_mode`
- `CandidateEvent.topic_id`
- `EventFact.temporal_state`
- `EventFact.event_date`
- `VerifiedClaim.verdict`
- `VerifiedClaim.evidence_ids`
- `EvidenceSpan`
- `RawArticle.provenance`
- `VerificationCheck.error_code`

Renderer invariants:
1. only supported claims may populate published entries
2. missing values are not converted into asserted facts
3. numeric confidence is forbidden unless a future validated contract explicitly defines it
4. watch-next remains optional/hidden because the current core contract does not provide it
5. event history remains unavailable until an explicit history contract exists
6. mobile and desktop use the same factual view model
7. partial verifier failure may be disclosed without inventing a score

CI result after PR #39: full infrastructure regression PASS.

## 11. Remaining UI work

Completed:
- [x] design direction freeze
- [x] implementation tokens
- [x] isolated D3/E/F3/G3 HTML/CSS prototype
- [x] 390/430/tablet/desktop responsive contract
- [x] core-to-UI renderer mapping
- [x] unsupported numeric confidence removed
- [x] CI regression against benchmark/API/PWA/Push

Still required before production UI integration:
- [ ] browser visual QA of the isolated prototype at target widths
- [ ] long-title / heavy-day visual stress pass on actual browser render
- [ ] dark-mode visual pass
- [ ] push permission state visual implementation
- [ ] actual event-history contract before enabling E in production
- [ ] renderer/PWA integration after engine output contract is production-ready

Figma MCP screenshot QA is currently blocked by the Starter-plan tool-call limit. No paid upgrade will be used to bypass it.

## 12. Implementation boundary

Do not restart design research unless a concrete implementation failure proves the frozen direction impossible or unsafe.
Do not copy prototype CSS into production by intuition.
Production integration must derive from this frozen contract and the validated renderer mapping.

Semantic engine development may now resume. UI production wiring is intentionally deferred until the engine output path is ready.

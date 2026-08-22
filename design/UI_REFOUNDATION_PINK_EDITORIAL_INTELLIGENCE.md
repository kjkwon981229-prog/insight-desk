# Insight Desk — UI Re-Foundation

## Pink Editorial Intelligence / Soft Geometry V3

Status: `UI_DESIGN_FREEZE_V3`
Branch: `ui-refoundation-pink-v2`
Figma working file: `https://www.figma.com/design/hThXgfkZHUgI8BzOcFzqlU`

This document is the authoritative design/source ledger for the Insight Desk UI redesign.
The visual direction is now frozen by user approval.
Further design work must refine, implement, or regression-test this direction rather than restart visual exploration.

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

Pink is retained and remains structural rather than decorative.

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

## 3. Design grammar

Primary blend:
- Editorial Layout — information hierarchy and sequencing
- International Typographic Style — disciplined grid and asymmetric balance
- Monochrome UI — hierarchy through tone, line, weight and spacing
- Layer / Page System — event → evidence → watch-next depth

Secondary borrowing only:
- Japandi — warmth and calm spacing
- Data-dense enterprise UI — evidence/detail views only
- Corporate SaaS — state clarity and controls only

## 4. Product architecture

The product uses multiple view grammars rather than forcing one layout everywhere.

### D3 — Daily Edition / Soft Editorial
Primary home experience.
- daily edited edition rather than generic card feed
- one dominant event can lead the page
- cover story uses a large soft feature surface
- secondary stories remain editorially aligned
- publication hierarchy remains visible despite softened geometry

### E — Signal Ledger
Event continuity/history experience.
- article feed is not the core mental model
- same event can persist across multiple state changes
- timeline expresses continuity across yesterday / today / future

### F3 — Split Desk / Soft Evidence
Desktop event-detail/evidence experience.
- master-detail structure
- event list on the left
- selected event facts, evidence, confidence, why-it-matters and watch-next on the right
- evidence units use soft rounded surfaces without becoming enterprise BI cards

### G3 — Mobile Focus / 390
Mobile focused-consumption experience.
- one event at a time
- pink can occupy a larger background field
- one dominant rounded event surface contains the current judgment unit
- state / evidence / watch-next appear as nested soft blocks

Mapping:
- Home → D3
- Event continuity/history → E
- Evidence/detail → F3
- Mobile focused consumption → G3

## 5. Soft Geometry V3 — frozen shape language

The supplied reference image was used only to clarify the desired rounded/blocky feel.
Its layout, color system, typography, productivity-app structure and interaction model are NOT design references for Insight Desk.

### Core rule

Straight lines organize the page. Rounded surfaces contain the units the user actually judges.

This keeps the product editorial while making it visually softer and more approachable.

### Radius hierarchy

- `14px` — micro elements / small internal states
- `20px` — rows / compact information blocks
- `28px` — normal event and evidence cards
- `36px` — featured event / large evidence panel
- `44px` — mobile focus / dominant single-event surface

Where supported, moderate corner smoothing should create a squircle-like blunt silhouette rather than a simple geometric rounded rectangle.

### What remains straight

- page/canvas edges
- masthead/grid alignment
- major editorial rules
- timeline axes where continuity matters
- primary column boundaries when they express structure

### What becomes soft

- cover story surfaces
- secondary event blocks
- evidence rows/panels
- selected event blocks
- mobile focus card
- state/value blocks
- watch-next block

### Avoid

- rounding every container indiscriminately
- excessive pill UI
- floating-card dashboard look
- generic iOS clone aesthetics
- glassmorphism
- generic AI gradients
- large soft shadows
- productivity-app visual language

## 6. Typography

Typography continues to carry more hierarchy than decoration.

Rules:
- large editorial headline with tight tracking
- compact metadata labels
- Korean body text optimized for sustained reading
- stable numeric values
- unnecessary English avoided in product content
- English used only where it functions as a concise system/brand label

## 7. Responsive targets

Required implementation coverage:
- mobile 390px
- mobile 430px
- tablet portrait
- desktop 1280px+

Mobile is not a shrunken desktop.

## 8. Required product states

Implementation/regression must support:
- normal briefing
- one important story only
- 8–10 story heavy day
- no qualifying stories
- partial source failure
- evidence available / unavailable
- verification indeterminate
- future / ongoing / completed / cancelled
- long Korean headline
- long Korean summary
- dark mode
- push permission state

## 9. Freeze decision

User approved Soft Geometry V3 as the final UI direction on 2026-08-23.

Therefore:
- `UI_DESIGN_FREEZE_V3 = YES`
- Pink retained = YES
- Soft Geometry shape grammar frozen = YES
- Multi-mode architecture frozen = YES
- Radical visual re-exploration = STOP
- Production CSS changed at freeze moment = NO

The previous A/A2 visual direction is no longer the primary product direction.
D3 / E / F3 / G3 form the frozen UI architecture.

## 10. Remaining work after design freeze

The remaining UI work is implementation and QA, not open-ended design exploration:

1. Translate the frozen V3 shape tokens and palette into implementation tokens.
2. Build isolated HTML/CSS prototypes for D3/F3/G3 and responsive states.
3. Implement 430px mobile and tablet portrait adaptations using the frozen grammar.
4. Implement evidence expand/collapse and event-detail transitions.
5. Implement push permission / notification state.
6. Verify accessibility, contrast, touch targets, safe-area spacing and long Korean text behavior.
7. Compare browser render against the frozen Figma reference when Figma MCP access is available.
8. Run visual regression and PWA/Push compatibility checks.
9. Only after implementation parity passes, integrate into production renderer.

## 11. Implementation boundary

Do not restart design research unless a concrete implementation failure proves the frozen direction impossible or unsafe.
Do not edit production styling by intuition.
Implementation must derive from this frozen design contract and the Figma V3 screens.

Semantic engine logic remains outside this design freeze and is not changed by this document.

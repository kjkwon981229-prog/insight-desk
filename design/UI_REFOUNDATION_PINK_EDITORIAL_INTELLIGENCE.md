# Insight Desk — UI Re-Foundation

## Pink Editorial Intelligence

Status: SOFT GEOMETRY V3 BUILT — VISUAL QA PENDING
Branch: `ui-refoundation-pink-v2`
Figma working file: `https://www.figma.com/design/hThXgfkZHUgI8BzOcFzqlU`

This document is the design/source ledger for the UI redesign before renderer implementation. It does not change semantic engine logic.

## 1. Product character

Insight Desk must feel like a refined personal intelligence briefing rather than a generic news app, AI dashboard, BI tool, or entertainment feed.

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

Pink should not flood every card. Warm neutral and charcoal remain the default field so pink retains information value.

## 3. Design grammar

Primary blend:
- Editorial Layout: information hierarchy and sequencing
- International Typographic Style: disciplined grid and asymmetric balance
- Monochrome UI: hierarchy through tone, line, weight and spacing
- Layer / Page System: article → evidence → watch-next depth

Secondary borrowing only:
- Japandi: warmth and calm spacing
- Data-dense enterprise UI: evidence/detail views only
- Corporate SaaS: state clarity and controls only

## 4. Architecture direction

The original A/A2 direction was judged too close to the preserved UI structure. Radical V2 introduced distinct modes:

### D — Daily Edition
Home reads as a daily edited edition, not a card feed.

### E — Signal Ledger
Event continuity and state changes are shown across time.

### F — Split Intelligence Desk
Desktop evidence/detail view uses master-detail structure.

### G — Focus Stack
Mobile prioritizes one event at a time.

Current product direction is multi-mode rather than forcing one layout everywhere:
- Home → D
- Event continuity/history → E
- Evidence/detail → F
- Mobile focused consumption → G

## 5. Soft Geometry V3 — latest user direction

The user explicitly requested a softer, chunkier silhouette while NOT asking to copy the supplied reference screen.

Only the rounded/blocky feel is borrowed. The reference app's layout, colors, typography, component arrangement, productivity-app character and interaction model are not adopted.

### Core rule

Straight lines organize the page. Rounded surfaces contain the units the user actually judges.

This prevents the product from becoming a generic all-cards mobile app.

### Radius hierarchy

- `14px` — micro elements / small internal states
- `20px` — rows / compact information blocks
- `28px` — normal event and evidence cards
- `36px` — featured event / large evidence panel
- `44px` — mobile focus / dominant single-event surface

Where supported in Figma, moderate corner smoothing is applied to create a squircle-like, blunt silhouette rather than a simple geometric rounded rectangle.

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

- rounding every single container
- excessive pills
- floating-card dashboard look
- generic iOS clone aesthetics
- glassmorphism
- gradient-heavy AI UI
- large soft shadows

## 6. Soft Geometry V3 screens created

Figma page: `Soft Geometry System — V3`

Created screens:

### D3 — Daily Edition / Soft Editorial
- daily-edition architecture retained
- cover story becomes a large soft feature surface
- editor note becomes a separate rounded editorial block
- secondary stories become chunky but still editorially aligned
- bottom-line and next-edition areas retain strong publication hierarchy

### F3 — Split Desk / Soft Evidence
- dark master rail retained
- individual event rows become soft rounded selection units
- right-side metrics use compact rounded blocks
- why-it-matters and evidence become larger soft evidence surfaces
- watch-next becomes a rounded charcoal panel with pink edge cue

### G3 — Mobile Focus / 390
- pink remains the dominant outer field
- one large 34px-radius event card contains the current judgment unit
- state / evidence / watch-next use smaller nested soft blocks
- the design keeps a single-event mobile reading model instead of reproducing the supplied reference layout

### Shape grammar board
A separate page section documents the 14/20/28/36/44 hierarchy and the rule that soft surfaces correspond to judgment units.

## 7. Typography

Typography continues to carry more hierarchy than decoration.

Rules:
- large editorial headline with tight tracking
- compact metadata labels
- Korean body text optimized for sustained reading
- stable numeric values
- unnecessary English avoided in product content

## 8. Responsive target

Required eventual coverage:
- mobile 390px
- mobile 430px
- tablet portrait
- desktop 1280px+

Mobile is not a shrunken desktop.

## 9. Required product states

The final system must support:
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

## 10. Current design gate

A candidate cannot be frozen unless:
- pink remains recognizably Insight Desk
- the softened geometry feels intentional rather than generic
- information hierarchy is clear within 2 seconds
- one dominant story can lead the page
- heavy days remain scannable
- evidence expands without redesigning the screen
- mobile and desktop both feel purpose-built
- dark mode remains coherent
- ordinary HTML/CSS/JS can implement the shape grammar

## 11. Visual QA status

Soft Geometry V3 screen construction completed successfully in Figma.

Immediate screenshot inspection could not be completed because the connected Figma Starter account reached its MCP call limit. The project will not use a paid upgrade to bypass this limit.

Therefore:
- V3 BUILT: YES
- VISUAL QA: PENDING
- DESIGN FREEZE: NO
- PRODUCTION CSS CHANGED: NO

The next Figma-capable session must begin with screenshots of D3, F3 and G3 and correct any spacing, radius, density or pink-balance defects before further design freeze work.

## 12. Current implementation policy

Do not edit production `assets/css/style.css` yet.
Figma remains the visual working source.
This repository document remains the decision/source ledger.
Only a visually audited winner may be translated into production CSS and renderer changes.

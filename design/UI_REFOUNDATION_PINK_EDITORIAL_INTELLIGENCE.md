# Insight Desk — UI Re-Foundation

## Pink Editorial Intelligence

Status: ACTIVE DESIGN EXPLORATION
Branch: `ui-refoundation-pink-v2`

This document freezes the design DNA for the UI redesign before new renderer implementation.
It does not change semantic engine logic.

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
- information-dense only where useful
- clearly non-generic

## 2. Pink is retained as a first-class brand primitive

Pink is NOT removed.
Pink is NOT a decorative afterthought.
Pink becomes the main semantic accent system.

Existing anchor colors are retained as the starting palette:
- Brand pink: `#C35B78`
- Strong pink: `#943C59`
- Soft pink surface: `#F0D9E0`
- Pink ink: `#7D3049`
- Dark-mode pink: `#D27A98`
- Dark-mode strong pink: `#F0A1B9`

Pink should primarily signal:
1. current selection / active navigation
2. editorial focus / important change
3. evidence or verified emphasis
4. brand recognition
5. interaction focus

Pink should NOT flood every card, paragraph, or chart. The default interface remains warm-neutral / charcoal so pink keeps information value.

## 3. Design grammar mix

Primary blend:

- 40% Editorial Layout
  - strong information hierarchy
  - publication-like sequencing
  - narrative rhythm instead of generic dashboard cards

- 30% International Typographic Style
  - mathematical grid
  - asymmetric balance
  - disciplined alignment
  - objective typography

- 20% Monochrome UI
  - information separated mainly by tone, line, weight and spacing
  - pink remains the deliberate exception

- 10% Layer / Page System
  - article → evidence → watch-next hierarchy
  - depth communicated through structure, not glass effects or heavy shadows

Secondary borrowing only:
- Japandi: warmth, calm negative space, restrained surface tone
- Data-dense enterprise UI: evidence tables and detail views only
- Corporate SaaS: state clarity and controls only

Do NOT let these secondary styles dominate the product identity.

## 4. Layout principles

### Home briefing
The page should read like a professionally edited briefing sheet, not a grid of interchangeable cards.

Order:
1. masthead / date / freshness state
2. one dominant 'what changed today' editorial lead
3. compact signal rail
4. story sequence ranked by relevance
5. trend / watch-next information
6. archive and evidence access

### Story anatomy
Each important story must be able to expose these layers without visually overwhelming the default view:

- WHAT CHANGED
- WHY IT MATTERS
- STATUS
- KEY FACTS
- EVIDENCE
- WATCH NEXT

Default view shows only the most decision-useful subset.
Evidence expands on demand.

## 5. Shape language

Preferred:
- squared / lightly rounded editorial blocks
- thin rules
- asymmetric columns
- narrow index rail
- occasional pink block or cut-out cue
- overlapping layers only where they communicate evidence depth

Avoid:
- pill-heavy UI
- excessive floating cards
- glassmorphism
- generic AI gradients
- blue SaaS dashboard conventions
- neon HUD styling
- excessive icon chrome
- large soft shadows

## 6. Typography

Typography must carry more of the hierarchy than decoration.

Rules:
- large editorial headline with tight tracking
- compact uppercase/small-label system for metadata
- Korean body text optimized for sustained reading
- numeric values tabular or visually stable where possible
- no unnecessary English in content UI
- English retained only for brand/system labels when genuinely useful

## 7. Icon / brand connection

Existing Insight Desk icon exploration established three useful visual grammars:

- Negative-Space Cut → precision / curation
- Asymmetric Editorial Block → editorial hierarchy
- Layer / Page System → evidence depth / curated intelligence

The new UI should reuse these principles so the icon and product surface feel like one design language.

## 8. Responsive targets

Must be designed and stress-tested at minimum for:
- mobile 390px class
- mobile 430px class
- tablet portrait
- desktop 1280px+

Mobile is not a shrunken desktop.
Desktop may introduce a persistent secondary evidence rail, but the editorial reading order must remain stable.

## 9. Required product states

Design exploration is not complete until these are explicitly represented:
- normal briefing
- 1 important story only
- 8–10 story heavy day
- no qualifying stories
- partial source failure
- evidence available / evidence unavailable
- verification indeterminate
- future / ongoing / completed / cancelled event states
- long Korean headline
- long Korean summary
- dark mode
- push permission state

## 10. Direction candidates

### A — Pink Editorial Intelligence — PRIMARY
Editorial 40 / Swiss 30 / Monochrome 20 / Layer 10.
This is the baseline to beat.

### B — Warm Personal Briefing
Editorial 40 / calm warm-negative-space 25 / Monochrome 20 / Swiss 15.
More intimate, but must not become lifestyle/wellness UI.

### C — Analytical Editorial Desk
Editorial 35 / data-dense evidence grammar 30 / Monochrome 25 / Swiss 10.
More analytical, but must not become enterprise BI.

## 11. Design gate

A candidate cannot be frozen unless it passes all of the following:
- pink remains recognizably part of Insight Desk
- information hierarchy is clear within 2 seconds
- one dominant story can visually lead the page
- 8–10 stories still remain scannable
- evidence can expand without redesigning the whole page
- mobile and desktop both feel intentionally designed
- dark mode remains coherent
- UI does not look like a generic AI/news/SaaS template
- current preserved PWA/Push functionality can be reattached without visual conflict
- implementation remains feasible with ordinary HTML/CSS/JS

## 12. Current implementation policy

Do not edit production CSS yet.
Design candidates are developed and compared first.
Only the final winner is translated into `assets/css/style.css` and renderer changes.

# Insight Desk Soft Geometry V3 — isolated implementation prototype

Status: IMPLEMENTATION PROTOTYPE — NOT PRODUCTION RENDERER

This directory translates the frozen `UI_DESIGN_FREEZE_V3` direction into ordinary HTML/CSS/JS without modifying the preserved production renderer or `assets/css/style.css`.

## Included modes

- D3 / Daily Edition: desktop and tablet home briefing
- E / Signal Ledger: event continuity and state history
- F3 / Split Desk: evidence and event-detail inspection
- G3 / Mobile Focus: mobile-first single-event briefing

## Frozen shape system

- 14px: micro state and small internal controls
- 20px: rows and compact information surfaces
- 28px: normal event/evidence cards
- 36px: featured event and large evidence surfaces
- 44px: dominant mobile focus surface

The intent is a soft, blunt silhouette rather than a generic all-card UI. Structural rules, timeline axes, canvas edges and editorial alignment remain straight where they express information architecture.

## Pink system

Pink remains the primary semantic brand accent. It signals editorial focus, current selection, verified/evidence emphasis and interaction focus. The neutral/charcoal field remains dominant so pink preserves information value.

## Responsive behavior

- desktop: D3 home, E ledger, F3 detail
- tablet: D3/E/F3 collapse progressively without changing reading order
- <= 640px: the home mode switches from the desktop Daily Edition to G3 Mobile Focus
- <= 430px: tighter soft-geometry tokens and spacing are applied

## Safety / failure states represented

- supported claim
- pending verification
- context-only evidence
- partial source failure
- future/scheduled temporal state

## Implementation boundary

Do not copy these files over the production renderer yet.

Promotion requires:
1. CI regression success.
2. visual QA at 390, 430, tablet portrait and desktop widths.
3. long-Korean-title and heavy-day stress review.
4. dark-mode review.
5. implementation parity against the frozen Figma direction.
6. only then translate the approved tokens/components into the production renderer and `assets/css/style.css`.

No external frontend library, network runtime dependency or paid service is introduced by this prototype.

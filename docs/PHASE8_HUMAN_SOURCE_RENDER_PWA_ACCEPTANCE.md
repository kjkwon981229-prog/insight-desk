# Phase 8 — Human / Source / Render / PWA Acceptance

Status: **COMPLETE**

Scope: final acceptance of the already-approved Phase 7 fresh production artifact. This phase does not change production code, provider routing, discovery, event understanding, generation, verification, publication, deploy, or push behavior.

## Accepted artifact

Fresh production run: `33257069687`

Preflight head: `3532deb0a3ab93844a94e9899625ea9b62cf4945`

Artifact:

```text
artifact_id = 9716250930
zip_sha256 = ce94961982142e98ae060ee936a156f95e9a73d83f9ee71f9ff655f785c0f750
html_sha256 = 768967f608d2db880542a9fc35275f23a52211b34a76a30ddd90b4b4bce68485
publication_digest = 0e9ec14f4d36d9a90d677ea9d77fe9dc91dbc92c3a9c579424e97f4c810b5733
publications = 3
```

Phase 7 already established:

```text
P0 = 0
P1 = 0
```

for the three visible publications and their source grounding.

## Browser render method

The execution environment blocks URL navigation with `ERR_BLOCKED_BY_ADMINISTRATOR` for both localhost and `file://` navigation. That environment limitation is not an application failure.

To preserve a real Chromium render check without substituting a hand-built mock, the exact artifact bytes were loaded as follows:

- exact `index.html` from artifact;
- exact `assets/css/style.css` injected into the document as a `<style>` block;
- exact `assets/js/push.js` injected into the document as a `<script>` block;
- Chromium headless browser used for layout and screenshot rendering;
- no production HTML text, CSS declarations, card content, or JS logic rewritten;
- only external-resource transport was replaced with in-memory injection because URL navigation is administratively blocked.

The service-worker installation event itself could therefore not be re-executed in this environment. PWA binding was separately verified against the artifact bytes as documented below.

## Desktop render acceptance

Viewport: `1440 × 1000`

Measured layout:

```text
viewport_width = 1440
shell_width = 1120
shell_left = 160
shell_right = 1280
document_scroll_width = 1440
horizontal_overflow = 0
overflowing_elements = 0
```

Visible rendering:

- header and timestamp fully visible;
- navigation fully visible;
- briefing headline and lede fully visible;
- 3 lead signals visible;
- push-settings panel fits inside the shell;
- three news rows fully visible;
- headline, summary, metadata, and source CTA do not overlap;
- no clipped text or source links;
- no raw article-body projection.

Typography observed in Chromium:

```text
briefing H1 = 64px
section H2 = 36px
story H3 = 24.8px
story summary = 16px
source CTA = 13.76px
```

## Mobile render acceptance

Viewport: `390 × 844`

Measured layout:

```text
viewport_width = 390
shell_width = 366
shell_left = 12
shell_right = 378
document_scroll_width = 390
horizontal_overflow = 0
overflowing_elements = 0
```

Visible rendering:

- brand, timestamp, and navigation remain readable;
- briefing headline fits without horizontal clipping;
- 3 lead signals stack vertically and remain legible;
- push-settings panel stacks correctly;
- both push controls remain inside the viewport;
- all three news rows flow vertically without overlap;
- long K-POP headline wraps naturally rather than clipping;
- KBO and PSAT summaries remain readable;
- all three `원문 보기` links remain visible and separated from adjacent content;
- footer is visible at the end of the document.

Typography observed in Chromium:

```text
briefing H1 = 42.9px
section H2 = 23.2px
story H3 = 19.2px
story summary = 16px
source CTA = 13.76px
```

The three source links render with a 44px interaction-box height in both Desktop and Mobile measurements.

## Visible publication contract

Artifact HTML contains exactly three `<article class="story-row">` publication rows.

Visible source links:

1. `http://www.joynews24.com/view/1999673`
2. `https://www.newspim.com/news/view/20260829000121`
3. `https://www.ppss.kr/news/articleView.html?idxno=307623`

Visible prose bound:

```text
max_visible_paragraph_chars = 137
paragraphs_over_420_chars = 0
```

This independently confirms that the historical multi-paragraph/raw-body failure class is absent from the accepted artifact.

## PWA artifact contract

`manifest.webmanifest` parses successfully and declares:

```text
name = Insight Desk
short_name = Insight Desk
display = standalone
start_url = .
scope = .
theme_color = #c35b78
background_color = #f5f1ef
```

Manifest icons:

```text
assets/icons/icon-192.png
  declared = 192x192
  actual = 192x192

assets/icons/icon-512.png
  declared = 512x512
  actual = 512x512
```

HTML bindings:

```text
manifest href = manifest.webmanifest
push script = assets/js/push.js
push service-worker URL = push-sw.js
```

`assets/js/push.js` contains the active client-side paths for:

- `serviceWorker.register(...)`;
- `data-push-service-worker-url` lookup;
- Notification permission handling;
- PushManager subscription handling.

`push-sw.js` exists in the publication root and contains handlers for:

- `push`;
- `notificationclick`.

The workflow-produced Phase 7 artifact also passed the production site contract before upload.

## Environment limitation

The following is explicitly **not** claimed:

- a fresh HTTPS service-worker install/activate lifecycle executed inside the current assistant runtime;
- a real push subscription or notification delivery from this PR preflight.

Those operations require an allowed secure-origin navigation/runtime and are intentionally not emulated. PR production safety also keeps deploy and push skipped.

This limitation does not invalidate the Desktop/Mobile render acceptance or the byte-level PWA binding checks above.

## Phase 8 decision

Acceptance result:

```text
human/source acceptance = PASS
Desktop render = PASS
Mobile render = PASS
horizontal overflow = 0
clipping/overlap = 0
visible publication contract = PASS
manifest/icon binding = PASS
push client/service-worker binding = PASS
P0 = 0
P1 = 0
```

No code changes are required by Phase 8.

**PHASE 8 COMPLETE. Phase 9 may now independently evaluate MERGE_READY conditions.**

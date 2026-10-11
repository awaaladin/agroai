# Design, Motion and Flow Guide (a reusable setup)

This file describes a design setup: what the interface should feel like, how motion is built and where it is allowed, how the user moves through the product, and the traps that cost time. It describes a way of designing, not a particular product. Read it fully before changing anything visual. It contains **no colour palette**: colours are semantic tokens defined once in the Tailwind config and the base stylesheet. Reuse the tokens and never hard-code a colour.

Each section says what the rule is and why it exists. Where an example is needed it uses a generic "signature moment" or "main object" so the rules carry over to any product.

---

## 1. The feeling to protect

Decide the product's feeling in one sentence before touching code, then test every decision against it. A good default for anything people rely on: **calm, mature, precise**. Not a demo, not a template.

Principles, in priority order:

1. **Every animation communicates state.** If a motion does not tell the user something (something landed, a level changed, a document was issued, something is loading), delete it.
2. **Motion is physical, not robotic.** Things overshoot slightly and settle, like a spring or a liquid. Never use plain `linear` or default `ease` for meaningful movement. The only linear motion is a continuous drift such as a wave or a marquee.
3. **Reveal in reading order.** Content arrives top to bottom, left to right, with small staggers, so the eye is led and never surprised.
4. **Quiet by default, expressive at moments of trust.** Page transitions, hovers and menus are subtle and fast (120 to 300 ms). Save the big motion for two or three signature moments per product (a main object filling, an action confirmed, a record issued).
5. **Information survives without motion.** Reduced-motion users and no-script users must still get every fact (section 9).
6. **No toys.** No emoji, no icon fonts, no mascots, no stock animation presets, no generic spinners. Icons come from one outline set at one uniform stroke weight, drawn inline.
7. **Typography carries hierarchy.** One family. Distinct steps for page title, section title, body, small metadata, and tabular figures for any number people compare.

Dark mode is class based, toggled in the navigation, remembered in local storage, and follows the system on the first visit. Any band that must always be dark re-scopes the same tokens on that one section.

---

## 2. Stack and file map (pattern)

A server-rendered or static-first stack with a utility CSS framework and a small amount of script. No heavy framework. Motion is reproduced with CSS transitions, keyframes and small vanilla scripts.

| Concern | Where it lives |
|---|---|
| Tokens, components, **all animation CSS** | one source stylesheet, compiled by a build step; commit the compiled output if the deploy does not build |
| Design tokens and type scale | the framework config file |
| Shared behaviour: theme, boot screen, busy overlay, signature fills, count-ups, live-update hooks | one shared script |
| Marketing and public-page motion: reveals, word split, spotlight, magnetic buttons, sticky story stage, scroll-spy | one landing script |
| Layout shell, header, footer, confirm dialog, toasts | the base template |
| Icons, number filters, badges, logo mark | one helper module so every use is identical |

After any change to a template class or the source stylesheet, **rebuild the CSS**. The framework only emits classes it finds in the files it is told to scan.

---

## 3. The motion language (reuse these, do not invent new curves)

**Easing**
- *Spring overshoot* (liquids, level changes, tab pills, chips): `cubic-bezier(.34, 1.3, .5, 1)` or `cubic-bezier(.3, 1.25, .4, 1)`. The curve goes past 1, so the element overshoots and settles.
- *Soft spring entrance* (reveals, panels, stage layers): `cubic-bezier(.2, .9, .25, 1.1)`.
- *Calm ease-out* (draws, simple fades): `ease-out`.
- Continuous drift only: `linear`, infinite.

**Durations**
- Hover, press, menu, modal: 120 to 200 ms.
- Page entry: 280 ms with a 6 px rise.
- Scroll reveals: 700 to 900 ms.
- Level change of a main object: about 1.7 s. Count-up numbers: 1.3 to 1.4 s.
- Stagger step: 70 ms per item (`calc(var(--i) * 70ms)`).

**Reveal primitive (`.reveal`).** Starts at `opacity: 0`, `translateY(22px)`, `blur(8px)`. When `.in` is added it resolves to its place with the soft spring. An `IntersectionObserver` adds `.in` once. Delay is set per element with a custom property (`style="--d:150ms"`). Headlines use `.words`: script splits the text into `<span class="w" style="--i:n">` and each word un-blurs 70 ms after the previous.

Both must have a no-script fallback. A `<noscript><style>` block forces `.reveal` visible, and `.words .w` only exists after script runs, so plain text shows without it.

**Performance rule.** Animate `transform` and `opacity` only (blur is acceptable on small elements). Never animate width, height, top or left. Test on a mid-range phone.

---

## 4. The signature animations, one by one

These are patterns. Replace "the main object" with whatever the product's central object is.

### 4.1 A main object that fills (the most important animation)

The metaphor: a vessel fills toward a target. It must feel like liquid, not a progress bar.

Structure:
```
.vessel (rounded, overflow hidden)
   > .liquid          <- this moves
        > two svg waves (drifting surface)
        > .body       (the fill block)
   > .ticks           (25/50/75% marks; a tick lightens once the liquid passes it)
   > .sheen           (soft highlight)
```
How it works:
- `.liquid` is `position: absolute; inset: 0` and is moved with `transform: translateY(N%)`, where `N = 100 - percent`. Percent is relative to the element's own height, which equals the vessel, so `translateY(0%)` is full and `translateY(100%)` is empty.
- It has `transition: transform 1.7s cubic-bezier(.34, 1.28, .5, 1)`. The overshoot makes it rise slightly past the target and settle.
- The wave is an SVG path with two periods. The SVG is `width: 200%` and animates `translateX(-50%)` forever, which loops seamlessly because the path repeats every half width. Two waves at different speeds, opacities and directions (for example 7 s and 11 s reversed) give a calm surface.
- When the level **increases**, script adds a `rising` class for about 2.4 s. While it is present the waves shorten their duration so the surface "stirs" faster, then calms.
- First page load: the markup renders **empty** and script fills it on a ready event (after any boot screen leaves), using two nested `requestAnimationFrame` calls so the empty state paints first. Without this the animation plays invisibly behind the loader.
- Numbers count up in step: script tweens from the last known value (stored per key) to the new one with a cubic ease-out.

### 4.2 Live updates without a page reload

A page that must stay current polls a small endpoint every few seconds (only while the tab is visible) and swaps several panels out of band. Each panel has a stable `id`.

Critical details:
- **The same `id` on the old and new element is what makes CSS transitions survive a swap.** The library copies the old element's attributes onto the new one, then applies the new attributes after a short settle delay, so the level transitions from old to new instead of restarting. Never swap a parent without ids.
- In swapped markup, the animated element's style must carry the **final** value. Only the first full-page render uses the empty-then-fill trick.
- Do not put open forms or modals inside swapped panels (typing would be wiped). Dialogs live outside, and panel buttons open them by dispatching an event.
- New list rows get an `.is-new` class (slide in from above, background flash that fades) by comparing row ids against a set already seen. An item whose state flips gets a small scale settle.

### 4.3 Confirmation: a tick that draws itself

An SVG circle and a check path both use `pathLength="1"`, `stroke-dasharray: 1`, `stroke-dashoffset: 1`, then animate `stroke-dashoffset` to 0:
- ring: 0.65 s starting at 0.1 s; tick: 0.42 s starting at 0.7 s; a soft glow ring expands and fades at 0.95 s.
- Everything below the tick fades up in sequence from 1.0 s using `nth-child` delays. **Gotcha:** the last child (usually the button) needs its own delay entry or it appears before the tick finishes. Keep the delay list at least as long as the number of children.
- Tone: brief and confident, no confetti, no bounce. It is not a game.
- While the result is still pending, show the logo mark in a looping "breathing" state and poll; when the status flips, swap in the tick card. Failure shows a plain explanation and a way back.

### 4.4 A document resolving into view

For anything that should feel like a real document being issued (a receipt, a certificate, a summary):
- The paper animates `clip-path: inset(0 0 100% 0)` to `inset(0)` over about 1.15 s, so it "prints" top to bottom.
- Each line has class `line` and `style="--i:N"`, fading up at `0.25s + N * 70ms`.
- A torn or perforated edge can be made with a CSS mask: `conic-gradient(from -45deg at bottom, #0000, #000 1deg 89deg, #0000 90deg) 50% / 16px 100%`. **Gotcha:** an inverted gradient hides the whole document. Always check visually.
- A rounded-square seal draws itself with the stroke-dash trick at about 1.35 s, followed by a short status word.
- Numbers use tabular figures; fees or costs are their own line.
- `@media print` removes navigation, footer, animation and the mask so it prints as a clean page.

### 4.5 Loading screen and busy state (logo mark)

The logo mark is a simple shape holding the product's central metaphor, rendered inline with a unique id per instance (because of `clipPath`). It is **static everywhere** (navigation, footer, documents) and animated only inside loaders. A past bug: the navigation logo replayed its intro on every page.
- **Boot screen**: outline draws (about 0.7 s), the fill rises with overshoot (starts about 0.45 s), the wordmark fades in while its letter-spacing settles. Minimum visible time about 0.95 s, then it fades out and fires a ready event, which starts the signature fills, count-ups and reveals.
- It plays on the **first visit of a session and on every browser reload**, and is skipped on in-app navigation. A tiny inline script in `<head>` decides before first paint, using the navigation type (`reload`) and a `sessionStorage` flag, and adds a `booted` class to `<html>` to hide it.
- **Busy overlay**: same mark, gently breathing (`alternate`, infinite). It appears only if a request takes longer than about 550 ms, so fast actions never flash it. Background polling is exempt.
- Never use a generic spinner.

### 4.6 Landing and public-page motion

All in one landing script plus a labelled block of the stylesheet.

- **Hero live demo**: a framed card that plays a loop of about 16 s using the real components: items change state one after another, the main object rises, totals count up, a final state announces completion, then it resets. It pauses on tab hide, starts after the ready event, and shows the final state statically under reduced motion.
- **Hero atmosphere**: a faint grid that fades out with a mask, and a soft glow that follows the cursor (custom properties `--hx/--hy` set on `pointermove`).
- **Marquee**: a duplicated list translating `-50%` forever, edge-faded with a mask, pausing on hover.
- **Sticky-scroll story (three chapters)**: text chapters scroll normally while a stage stays `position: sticky`. An `IntersectionObserver` with `rootMargin: -42% 0 -42%` marks the chapter in the middle as active, sets `data-active` on the stage, and layers cross-fade with a soft spring (opacity, small scale, blur). A thin rail fills by thirds. On mobile the stage is hidden and each chapter shows its own inline image.
- **Photographs**: tint into the palette with a CSS duotone (`grayscale` plus a multiply gradient). Keep them honest and licensed: only use images that genuinely show what the caption claims, and credit them. Verify the place and the licence of every photo.
- **Spotlight cards**: a radial highlight follows the pointer inside the card, and the card lifts 3 px on hover with a spring.
- **Magnetic buttons**: the button drifts toward the cursor by a few pixels and springs back on leave. Disabled under reduced motion.
- **Feature micro-scenes**: each card demonstrates its claim with a tiny live scene instead of an illustration (bars that grow when revealed, a dashed line that flows, a pulsing dot, a ring that fills and empties).
- **Tabs**: equal tabs with one **sliding pill** whose `transform: translateX(tab * 100%)` uses the spring curve; panels enter with rise and un-blur; a progress bar advances in steps.
- **Facts row**: numbers count up when scrolled into view.
- **Table-of-contents scroll-spy** on long pages: the entry for the section in view gets a coloured left border and nudges 4 px right.
- **FAQ**: native `<details>`; the chevron rotates with the spring curve and the answer fades in.

### 4.7 Small, constant micro-interactions

Buttons and rows: colour transitions of 150 ms. Menus and modals: 120 to 150 ms fade and rise. Toasts: slide down, auto-dismiss after about 7 s. Inputs: the focus ring grows with a short transition. Nothing else moves.

---

## 5. The user flow (define it once, then keep it intact)

Write the main journey as numbered steps with their URLs before building, and do not reorder it later. A typical shape:

1. **Entry** page: story and live demo, one clear call to action. Signed-in visitors skip to the dashboard.
2. **Sign up** or **sign in**.
3. **Dashboard**: a few stats, things waiting on the user with direct action buttons, cards with thin progress bars that grow on load, recent activity.
4. **Create** flow: purpose cards, details, options, and a sticky **summary** panel that updates as the user types.
5. **Detail page** for the main object: its signature animation, "your part", who did what, a ledger, where things go. Updates live (section 4.2).
6. **Act**: submit, redirect to any external provider, return to a confirmation page (section 4.3).
7. **Outcome**: automatic or manual completion, status shown in context, a link to the issued document (section 4.4).
8. **Supporting pages**, each on its own URL and not crammed into the landing page: a detailed beginner guide, about, fees, contact, privacy, terms, plus a footer linking them all and a header navigation for visitors.

State the product's invariants in the flow document and never break them (for example: people only act on their own part; locked fields stay locked; costs are always an explicit line; totals are always summed from confirmed records rather than stored; everyone involved can read the ledger).

---

## 6. Interaction architecture (how pieces talk)

- **One confirmation dialog for everything destructive**, in the base template. Any button opens it by dispatching an event with an action, title, body, label and a danger flag. It submits a protected form.
- **Small state library** (Alpine or similar) holds UI state only: menus, modals, tabs, a form's live preview. **A fragment-swap library** (HTMX or similar) replaces fragments: live panels, notification badges, confirmation polling, field checks, document polling. **Vanilla script** is used only where timing control is needed: boot screen, signature fill, count-up, story stage, hero loop.
- Send the anti-forgery token as a header on every swapped request.
- A notification bell refreshes by out-of-band swap every 30 s; opening one marks it read and goes to the related page.

---

## 7. Mobile is a first-class screen

Test at **320, 375, 414 and 768 px**. Rules that fixed real bugs:
- Grid and flex children that contain wide content need `min-w-0` (for example `[&>*]:min-w-0` on grids). Without it a grid column refuses to shrink and the whole page scrolls sideways.
- Wrap tables in `overflow-x-auto`, tighten cell padding on small screens, and use `whitespace-nowrap` for numbers.
- Big figures shrink on phones; the main object narrows below 400 px and its stats stack to one column.
- Header right cluster: smaller gaps and no chevron below the small breakpoint, so nothing spills at 320 px.
- Sticky and side-by-side stages collapse: the story stage is desktop only; secondary columns move below the main one.
- Touch targets stay at least about 44 px for any product used outdoors or by people with limited reading (the minimum anywhere is 36 px).

**How to verify (do not skip).** Run the app, then use a headless browser (Playwright) to load every page at each width and assert `document.documentElement.scrollWidth <= clientWidth`, listing offenders by bounding box (ignore elements clipped by an `overflow: hidden` ancestor, fixed overlays and marquees). Also take screenshots of long pages and **look at them**. Automated tests cannot see an invisible document or a misplaced element.

---

## 8. Landing and content design

- The headline is a human sentence, not a feature list. Copy is plain, specific and written for the real audience's context (their places, their money, their words).
- Dark bands (hero, features, final call to action) alternate with light bands (story, how it works, facts) for rhythm.
- Every claim has a demonstration next to it (a small live scene) instead of an illustration.
- Statistics must be true statements about the product. Never invent user counts or testimonials.
- The beginner guide uses the exact button labels from the product, numbered steps, tip callouts and a glossary, so a first-time user can follow it.
- Legal pages are drafts until a lawyer has reviewed them.

---

## 9. Accessibility, reduced motion, no script

- `@media (prefers-reduced-motion: reduce)` shortens animations to nothing, sets stroke draws to their final state, shows all reveal content, hides extra story layers and shows the hero demo in its final state. Offer the same switch inside the product. The information is always present.
- Skip link, visible `:focus-visible` rings, `aria-live` on status text and toasts, `role="alertdialog"` on confirmation, labels on every icon-only button, `aria-current` on the active navigation link, `aria-selected` on tabs.
- Never carry information by colour alone: pair colour with an icon and words.
- No script: reveals are forced visible by `<noscript>`, forms work as plain submissions, and pages render on the server.
- Check text contrast in both themes and in any high-contrast theme.

---

## 10. Pitfalls already hit (save yourself the time)

1. **Name collision in the framework:** a font-size token and a colour token with the same name both produce the same utility class. Give the colour a different name (for example `fg`).
2. **Template caching:** a dev server run without reload caches templates. Restart it after editing templates.
3. **CSS rebuild:** new utility classes do nothing until the stylesheet is rebuilt. Commit the compiled file.
4. **The swap transition trick** needs matching ids and final-state markup (section 4.2). Replacing the main object's parent breaks the animation.
5. **Deferred tasks in tests:** background jobs scheduled "after commit" only run inside the test helper that executes commit callbacks.
6. **Do not animate the navigation logo** on every page; only loaders animate the mark.
7. **Delay lists must cover every child** (a confirmation button once appeared early).
8. **Inverted masks hide content silently.** Look at screenshots.
9. **Never cover the signature animation with the loader.** Start it on the ready event, not on `DOMContentLoaded`.
10. **Photo honesty:** a "city at night" image turned out to be a different city entirely. Verify location and licence before using any photo, and credit it.
11. **Fixed-position, hidden overlays** (modals waiting to open) can look like overflow in audits. Exclude them when measuring.

---

## 11. Recommended build order for a fresh agent

1. Tokens, type scale, base layout, theme toggle and boot/busy loaders.
2. Core components (buttons, cards, inputs, badges, alerts, menus) and the icon helper.
3. Sign-in pages and the dashboard.
4. The create form with its live summary.
5. **The detail page and the main object** (build the object and its live panels first; it sets the quality bar).
6. Confirmation and document animations.
7. The landing page (hero demo loop, story stage, features), then the guide, the other public pages and the footer.
8. Mobile audit at four widths, dark-mode pass, reduced-motion pass, print check.
9. Run the full test suite, then look at real screenshots before declaring done.

## 12. Definition of done for any visual change

- Looks right in light and dark mode, at 320 to 1280 px, with no horizontal scroll.
- The motion has a reason, uses the shared curves and durations, and degrades under reduced motion.
- No new colours or icon styles outside the tokens and the chosen icon set.
- CSS rebuilt and committed; templates restarted; tests pass; screenshots reviewed by eye.

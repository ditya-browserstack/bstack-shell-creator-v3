# Capturing STATE-GATED screens (modals, drawers, loaders, selected states, the recorder setup)

Some of a product's most important surfaces aren't a route you can navigate to — they only exist
*after an interaction*: a modal, a slide-over, a loading overlay, a selected-row detail panel, the
recorder's setup step. A plain snapshot of the route misses them entirely (that's why the recorder
"didn't show up"). This flow captures them: **reach the state → FREEZE it → snapshot the overlay.**

Mark such a screen in `screens.json` with `"type": "state-gated"` (so the assembler and self-check
treat it correctly — a modal legitimately covers the chrome, so self-check skips the topbar/sidebar
checks for it):
```json
{ "slug": "recorder-setup", "label": "Recorder — setup", "type": "state-gated",
  "reach": { "from": "tests", "do": "click Start Recording", "transient": true } }
```
`reach` is a note-to-self for how you drove there (you perform it live in the browser); `transient:true`
flags an overlay that auto-closes, so you must freeze *before* triggering it.

## 1. FREEZE first (only for transient overlays — loaders that auto-close)
Run this in the page **before** you trigger the state. It stops the two things that close an overlay
on you — a pending `setTimeout`/`rAF` and the exit animation — so the state holds long enough to grab.
Stable overlays (a modal that stays open until you close it) don't need this; skip to step 2.
```js
window.__freeze = (() => {
  const style = document.createElement('style');
  style.id = '__freeze';
  style.textContent = '*,*::before,*::after{animation:none!important;transition:none!important;animation-play-state:paused!important}';
  document.head.appendChild(style);
  const _st = window.setTimeout, _raf = window.requestAnimationFrame;
  window.setTimeout = () => 0; window.requestAnimationFrame = () => 0;   // no auto-close fires
  return () => { window.setTimeout = _st; window.requestAnimationFrame = _raf; style.remove(); }; // restore
})();
```
Then **trigger the state** (click "Start Recording", open the modal, select the row) via the live
browser. The overlay opens and, because its close-timer now calls a no-op, it stays put.

## 2. Snapshot the overlay (content region + the portal on top)
Modals/drawers render in a **portal at `<body>` level**, *outside* `#app-main-content` — so capture
both: the content region for context, plus every top-level fixed overlay. Their `position:fixed`
makes them cover the shell correctly when shown.
```js
const src = document.querySelector('#app-main-content') || document.querySelector('#webapp-content');
const overlays = [...document.body.children].filter(el => {
  if (el.closest('#app-main-content,#webapp-content')) return false;
  const cs = getComputedStyle(el);
  return (cs.position === 'fixed' || el.matches('[role=dialog],[data-headlessui-portal],[class*=drawer],[class*=modal],[class*=slideover],[class*=Overlay]'))
    && el.getBoundingClientRect().width > 0 && el.id !== 'screen-mount';
}).map(el => el.outerHTML).join('\n');
download('<slug>.html', src.outerHTML + overlays);   // RAW — scrub runs at share-time
if (window.__freeze) window.__freeze();               // restore timers/animations
```
Take the `<slug>.sig.json` too (same as `capture-multiscreen.md` step 4). For a modal, also write a
**prod reference screenshot** while it's still frozen — self-check pairs it.

## 3. Assemble + self-check (no special flags)
Add the screen to `screens.json` with `"type":"state-gated"`, then run the normal
`assemble-multiscreen.mjs` → `self-check.mjs` → `scrub-for-share.mjs`. The fixed overlay renders on
top of the shell when that panel is shown; self-check skips chrome checks for state-gated screens (a
modal covers the sidebar on purpose) but still gates BLANK/SPINNER/BROKEN_ASSETS and the signature.

## The recorder, concretely
- **Setup slide-over** (transient, auto-closes ~1–2s): FREEZE (step 1) → click Start Recording →
  snapshot (step 2). This is the surface you actually design.
- **Live recording session** (a real browser driving a target site) and the **desktop app**: NOT a
  static overlay — capture a **screenshot/short clip** as a reference (`type:"media"`, out of scope
  for a mountable HTML shell), or design it fresh. See `capture-sources.md`.

## Gotchas
- **Freeze BEFORE triggering.** If the close-timer is scheduled before you stub `setTimeout`, stubbing
  won't cancel it. Stub first, then trigger.
- **Portals live at `<body>`, not in the content wrapper** — the overlay-grab above walks
  `document.body.children`, not the wrapper, or you'll capture the base page without the modal.
- **Backdrops/scrims** are usually their own fixed sibling — the grab picks them up (fixed position),
  so the dimmed background comes along and it looks real.
- **Restore after capture** (`window.__freeze()`) so the live app keeps working for the next screen.

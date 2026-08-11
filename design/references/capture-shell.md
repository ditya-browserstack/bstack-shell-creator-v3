# Capturing the real app shell (the primary SETUP method)

The **shell is the product's identity** — the real chrome (top bar · sidebar · page/surface header · the surface's own composed rows, e.g. LCA's recorder row). Capturing it live from the running product is **the method that works and the one this skill is built on.** Everything a feature design needs beyond the shell comes from the shared DesignStack core (primitives); you do **not** rebuild the product's chrome from primitives.

> Fallback only: if you genuinely cannot reach a running instance of the product, see `capture-app.md` for the lower-fidelity "assemble from primitives" path. Prefer live capture every time.

## Why live capture (not reconstruction)
Reading repo source gives you `<Sidebar/>`, not the compiled class names the product actually ships. Reconstructing chrome from primitives produces something *shaped like* the product, not the product. Live-DOM capture gives you the real compiled markup + the app's own stylesheet — pixel-real, and the genuine existing flow to diff a design against.

## Prerequisites (state these to the operator up front)
- The product running somewhere you can log into (staging or prod), e.g. LCA = `https://low-code.browserstack.com/`.
- **Claude in Chrome** connected to the operator's real, logged-in Chrome. **Never enter credentials** — the operator is already logged in; you drive their session.
- The product's `product.config.json` filled (`liveUrl`, `chrome.topbar`, `chrome.sidebar`, `chrome.activeNav`, `chrome.contentSlot`).

## Steps
1. **Open the product** in the logged-in Chrome (Claude-in-Chrome), navigate to the anchored surface (the screen the feature lives on). Close any promo/modal overlays.
2. **Run the capture snippet** (below) in the page via the browser's JS tool. It collects the top bar, sidebar, and the surface's content/recorder row + the app's compiled CSS, **scrubs** obvious customer data, and **blob-downloads** one self-contained file — so the large markup never has to pass back through the conversation.
3. **Finalize:** run the scrub gate and slot-injection on the downloaded file:
   ```bash
   node scripts/scrub-gate.mjs ~/Downloads/<product>-shell-capture.html   # MUST exit 0
   # then move into the product + insert the SOLUTION BODY slot (see setup.md)
   ```
   The scrub gate is a hard stop — do not commit a capture that fails it.
4. **Verify by eye** in Chrome — the chrome must read as the real product; icons/fonts render; no real names/emails/URLs remain.

## The capture snippet (run in the logged-in page)
Set `APP_ROOT` = `chrome.appRoot` (the app's outermost container) and `DATA_REGION` = `chrome.dataRegion`
(the record-bearing area to remove). **Clone the whole app root and prune the data region** — do NOT
reassemble from a topbar+sidebar grab. Cloning keeps *all* chrome (every rail/bar) with the app's own
layout, so nothing is dropped and nothing is offset by a guessed margin.

```js
(() => {
  const APP_ROOT    = '<chrome.appRoot>';    // e.g. #lcnc-dashboard  (the whole app container)
  const DATA_REGION = '<chrome.dataRegion>'; // e.g. the test-list table  (record-bearing → pruned)
  const SLOT_CLASS  = '<chrome.contentSlot>'.replace(/^\./,''); // e.g. lca-main-slot

  // (1) Reflect form STATE into attributes so it serializes — without this every input is blank,
  //     AND real values stay invisible to the scrub (a silent privacy hole).
  document.querySelectorAll('input, textarea, select').forEach(el => {
    if (el.type === 'checkbox' || el.type === 'radio') { if (el.checked) el.setAttribute('checked',''); }
    else if (el.value) el.setAttribute('value', el.value);
    if (el.tagName === 'TEXTAREA' && el.value) el.textContent = el.value;
  });

  // (2) Compiled CSS, once.
  let css = ''; for (const s of document.styleSheets) { try { css += [...s.cssRules].map(r=>r.cssText).join('\n')+'\n'; } catch(e){} }

  // (3) Clone the real app root; prune the data region and drop an empty slot in its place.
  const root = document.querySelector(APP_ROOT)?.cloneNode(true);
  if (!root) return { ok:false, error:'APP_ROOT not found — check chrome.appRoot' };
  const slot = document.createElement('main'); slot.className = SLOT_CLASS; slot.innerHTML = '<!-- SOLUTION BODY -->';
  const data = root.querySelector(DATA_REGION);
  if (data) data.replaceWith(slot); else root.appendChild(slot); // if no data region, just add a slot

  // (4) Scrub the rendered string. Because values are now reflected (step 1), the scrub + scrub-gate
  //     can actually SEE them. Extend per product; scrub-gate.mjs is the enforced backstop.
  let html = root.outerHTML
    .replace(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g, 'user@example.com')
    .replace(/https?:\/\/(www\.)?(flipkart|airbnb|calendly|bstackdemo)\.com/gi, 'https://example.com')
    .replace(/Default(\+|%20|\s)Project(\+|%20|\s)-(\+|%20|\s)LCNC/g, 'sample-project')
    .replace(/Default Project - LCNC/g, 'Sample Project');

  const doc = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>shell capture</title><style>${css}</style></head><body>${html}</body></html>`;
  const a=document.createElement('a'); a.href=URL.createObjectURL(new Blob([doc],{type:'text/html'})); a.download='shell-capture.html'; a.click(); a.remove();
  return { cssBytes: css.length, ok: true };
})();
```

**Driving via Playwright/MCP instead of Claude-in-Chrome?** The blob-download won't reach your disk —
return the `doc` string instead and write it to a file yourself; it arrives JSON-string-encoded, so
`JSON.parse` it first. And `file://` may be blocked for the eyeball check — serve the folder with
`python3 -m http.server` and open `localhost`.

## Customer data — the hard rule (now mostly mechanical)
Pruning `DATA_REGION` removes the record-bearing area **by construction** — that is the real
protection, not the operator remembering. Then reflect (step 1) so values are visible, scrub, and the
**`scrub-gate.mjs` must exit 0 before commit** (it now also flags "updated by <Name>" attributions).
Still never capture a data-heavy surface without setting `DATA_REGION`.

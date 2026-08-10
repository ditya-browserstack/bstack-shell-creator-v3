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
Adjust the three selectors to the product's config (`chrome.topbar`, `chrome.sidebar`, and the content/surface section). This is the exact shape proven on LCA.

```js
(() => {
  let css = '';
  for (const s of document.styleSheets) { try { css += [...s.cssRules].map(r=>r.cssText).join('\n')+'\n'; } catch(e){} }
  const grab = sel => document.querySelector(sel)?.outerHTML || '';
  const topbar  = grab('<chrome.topbar>');          // e.g. #lcnc-bstack-header
  const sidebar = grab('<chrome.sidebar>');          // e.g. nav.fixed.inset-y-0
  const content = grab('<surface content section>'); // the recorder/page row to diff against
  // scrub: replace real data with fakes. EXTEND this per product; the scrub-gate is the safety net.
  const scrub = h => h
    .replace(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g, 'user@example.com')
    .replace(/https?:\/\/(www\.)?(flipkart|airbnb|calendly|bstackdemo)\.com/gi, 'https://example.com')
    .replace(/Default(\+|%20|\s)Project(\+|%20|\s)-(\+|%20|\s)LCNC/g, 'sample-project')
    .replace(/Default Project - LCNC/g, 'Sample Project');
  const doc = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>shell capture</title><style>${css}</style></head><body>
${scrub(topbar)}
<div style="display:flex">${scrub(sidebar)}<div style="flex:1;min-width:0;margin-left:256px">${scrub(content)}
<main class="lca-main-slot"><!-- SOLUTION BODY --></main></div></div>
</body></html>`;
  const a=document.createElement('a'); a.href=URL.createObjectURL(new Blob([doc],{type:'text/html'})); a.download='shell-capture.html'; a.click(); a.remove();
  return { cssBytes: css.length, ok: !!(topbar&&sidebar&&content) };
})();
```

Rename `lca-main-slot` to the product's `chrome.contentSlot`. The `SOLUTION BODY` slot is where USE mounts explorations (`mount-switcher.md`).

## Customer data — the hard rule
Live captures come from a logged-in product and **will** contain real data (names, emails, test/project names, ids). Scrub in the snippet, and the **`scrub-gate.mjs` must pass before commit** — it is the enforced backstop. Do not capture list/table content full of real records; capture chrome + the surface row only.

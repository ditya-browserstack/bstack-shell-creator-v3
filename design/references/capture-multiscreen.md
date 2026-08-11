# Capturing a MULTI-SCREEN shell (all the major pages, not just the landing screen)

A single-surface shell only covers the home screen. This flow captures the product's **major
screens** (Tests, Test suites, Builds, Modules, Settings…) and stitches them into **one file** where
the sidebar switches between them. Proven live on LCA (2026-08-11).

Same discipline as single capture (`capture-shell.md`): live-DOM, reflect form state, prune records,
scrub, gate. The difference is you capture the **chrome once** and each screen's **content region**.

## 1. Find the two selectors (per product, once)
Probe the live app in the logged-in Chrome:
- **content wrapper** — the region that changes per screen. **Gotcha (real on LCA): its id can vary
  per route** (`#webapp-content` on one screen, `#app-main-content` on another). Use a fallback:
  `document.querySelector('#app-main-content') || document.querySelector('#webapp-content')`, or the
  tall element whose `left` is just past the sidebar.
- **screen routes** — read the sidebar `<a href>`s (LCA: `/tests`, `/suites`, `/builds`, `/modules`,
  `/settings`). You navigate to each `https://<app>/projects/<id>/<route>`.

## 2. Capture the chrome once (any screen)
Run in the page — grabs the whole body with the content region replaced by an empty mount:
```js
// reflect form state first (see capture-shell.md step 1), then:
let css=''; for(const s of document.styleSheets){try{css+=[...s.cssRules].map(r=>r.cssText).join('\n')+'\n';}catch(e){}}
const body=document.body.cloneNode(true);
const cc=body.querySelector('#app-main-content')||body.querySelector('#webapp-content');
const mount=document.createElement('div'); mount.id='screen-mount'; if(cc) cc.replaceWith(mount);
body.querySelectorAll('script,[data-headlessui-portal],#storybook-highlights-root').forEach(n=>n.remove());
const doc=scrub(`<!DOCTYPE html><html><head><meta charset="utf-8"><style>${css}</style></head><body>${body.innerHTML}</body></html>`);
download('chrome.html', doc);
```

## 3. Capture each screen's content (navigate + run)
For each route: navigate, wait ~2s for the SPA, then:
```js
const src=document.querySelector('#app-main-content')||document.querySelector('#webapp-content');
const c=src.cloneNode(true);
c.querySelectorAll('tbody tr, [role="row"]').forEach((r,i)=>{ if(i>0) r.remove(); }); // drop record rows
download('<slug>.html', scrub(c.outerHTML)); // scrub incl. "updated by <Name>" -> "Sample User"
```
Save these into `products/<slug>/app-shell/screens/` plus a `screens.json`:
`[ { "slug":"tests","label":"Tests" }, { "slug":"suites","label":"Test suites" }, ... ]`.

## 4. Assemble + prune + wire the switcher
```bash
node scripts/assemble-multiscreen.mjs --slug <slug>
node scripts/scrub-gate.mjs products/<slug>/app-shell/multiscreen-shell.html   # MUST exit 0
```
The assembler injects each screen as a panel, wires the sidebar to switch, and **prunes any chrome
that leaked into a panel** — the real gotcha: on some routes the content wrapper wrongly includes the
sidebar, which would render it twice. The prune removes nav/rail/topbar from inside panels.

## Gotchas the live run surfaced (don't relearn them)
- **Content-wrapper id varies per route** → always use the fallback selector.
- **Records aren't always a `<table>`** → the `tbody tr` prune can miss a virtualized list; if the
  scrub-gate flags names, prune that list container explicitly, or capture its empty state.
- **Duplicated sidebar** → the assembler prunes leaked chrome; verify only ONE sidebar renders.
- **Active-nav highlight** → the sidebar keeps the app's baked highlight from the chrome-capture
  screen; the assembler adds `ms-nav-active` to the current one. If both show, neutralize the app's
  active class in the chrome capture.
- **Third-party widget URLs** (Beamer, intercom) may trip the gate — allowlist or neutralize; not PII.

# Capturing a MULTI-SCREEN shell (EVERY major page, not just the landing screen)

This is the **primary** shell-capture flow. A single-surface shell only covers the home screen; a
real product is a dozen screens. This flow discovers **every** screen the product exposes and
stitches them into **one file** where the sidebar switches between them. Proven live on LCA
(2026-08-11).

**The mandate: capture every distinct destination — do NOT hand-pick a few.** That means top-level
nav, every item inside collapsible sidebar groups, *and* at least one representative detail page per
list (the page you reach by clicking a row). A shell that only has Tests/Settings is L1; a faithful
shell has the whole left rail plus the drill-ins.

## Step 0 — ASK the user for a source (don't assume one)
Before capturing anything, ask what the user can provide — a live/prod URL, a localhost instance, and/or
the repo — and route each page to the safest source. Full prompt + decision table in
`references/capture-sources.md`. The short version follows.

## Which source per page: LIVE prod vs LOCAL seed (a PII decision, learned the hard way)
Not every page is safe to capture from **live production**. Two classes of page:
- **List/record pages** (Tests, Suites, Builds, Modules, Settings): safe from live prod. Their only PII
  is author names in a *known, patterned* place — the scrub in step 4b handles it.
- **Config/admin pages** (Secrets, Global variables, Databases, Test datasets, Integrations, team/user
  admin): a **PII minefield from live prod.** They are saturated with user-authored strings the gate
  **cannot** catch — teammate usernames in "created by" columns (`firstlast_XXXXXX`), people's names
  baked into secret/connection labels (`Finstack_Password_Nitesh`), environment tabs named after people
  (`manoj_test1`). These are 100–200-row lists, so you cannot eyeball them clean, and the markup is too
  varied to scrub by regex. Capturing these from prod **will** leak names.

**Rule: capture config/admin pages from a LOCAL instance seeded with fake data, not from prod.** Local
seed data has no real people in it, so those pages are safe to capture and share. Use live prod for the
list/record pages, local for the config/admin pages, and stitch both into one shell — "both sources,
per-page." If no local instance is available, either omit the config pages or mark the shell
**internal-only — do not share** and scrub best-effort.

Same discipline as single capture (`capture-shell.md`): live-DOM, reflect form state, **keep the rows
but scrub the data**, gate. The difference is you capture the **chrome once** and each screen's
**content region**, then loop over the full screen list.

## 1. DISCOVER every screen (don't rely on memory or a screenshot)
Screens you can't see (collapsed groups, drill-in routes) are the ones that get missed. Enumerate them
mechanically. In the logged-in app, **first expand every collapsible sidebar group** (click each group
header — e.g. LCA's "Data configuration" hides Folders / Secrets / Test data / Databases / Media
library / Global variables), then dump the full link list:
```js
// run in the page AFTER expanding every collapsible sidebar section
[...document.querySelectorAll('nav a[href], aside a[href], [class*="sidenav"] a[href]')]
  .map(a => ({ label: (a.innerText||a.getAttribute('aria-label')||'').trim().slice(0,40),
               href: a.getAttribute('href') }))
  .filter(x => x.href && x.href.startsWith('/'));
```
Cross-check the dump against the product's route map if you have the repo (LCA: `apps/app-low-code/
src/constants/routes.js`) — it lists routes that may not all be in the sidebar (detail/run routes).
Build the **complete** screen list from this, not from a remembered subset.

**Also list the detail pages.** For each list screen, note the route you land on when you click a row
(Tests → `/tests/:id` editor, Suites → `/suites/:id`, Builds → `/builds/:id`, a run → its report).
Capture at least the highest-value ones — a shell with list pages but no detail pages can't show a
reviewer what "opening a thing" looks like.

## 2. Find the content-wrapper selector (per product, once)
The region that changes per screen. **Gotcha (real on LCA): its id can vary per route**
(`#webapp-content` on one screen, `#app-main-content` on another). Use a fallback:
`document.querySelector('#app-main-content') || document.querySelector('#webapp-content')`, or the
tall element whose `left` is just past the sidebar.

## 3. Capture the chrome once (any screen)
Run in the page — grabs the whole body with the content region replaced by an empty mount:
```js
// reflect form state first (see capture-shell.md step 1), then:
let css=''; const blocked=[];
for(const s of document.styleSheets){try{css+=[...s.cssRules].map(r=>r.cssText).join('\n')+'\n';}catch(e){ if(s.href) blocked.push(s.href); }}
// CORS-blocked stylesheets are silently DROPPED by cssRules (Phase-A audit: 3 on LCA) — fetch their text:
for(const href of blocked){ try{ css += await (await fetch(href)).text() + '\n'; }catch(e){} }
const body=document.body.cloneNode(true);
// ABSOLUTIZE every relative URL so nothing 404s on file:// (the assembler also inlines assets later):
body.querySelectorAll('[src],[href],[srcset]').forEach(el=>{
  for(const a of ['src','href']){ const v=el.getAttribute(a); if(v && !/^(https?:|data:|#|mailto:)/.test(v)) el.setAttribute(a, new URL(v, location.href).href); }
  const ss=el.getAttribute('srcset'); if(ss) el.setAttribute('srcset', ss.split(',').map(c=>{const [u,d]=c.trim().split(/\s+/); return (/^(https?:|data:)/.test(u)?u:new URL(u,location.href).href)+(d?' '+d:'');}).join(', '));
});
const cc=body.querySelector('#app-main-content')||body.querySelector('#webapp-content');
const mount=document.createElement('div'); mount.id='screen-mount'; if(cc) cc.replaceWith(mount);
body.querySelectorAll('script,[data-headlessui-portal],#storybook-highlights-root').forEach(n=>n.remove());
const doc=`<!DOCTYPE html><html><head><meta charset="utf-8"><style>${css}</style></head><body>${body.innerHTML}</body></html>`;
download('chrome.html', doc);   // RAW — real data. Scrubbing happens at share-time (scrub-for-share.mjs).
```

## 4. Capture each screen's content (navigate + WAIT FOR DATA) — RAW
Capture is **raw**: real data, no masking. That's the working shell you design in, and it's kept local
(gitignored) — scrubbing happens once, at **share-time** (`scrub-for-share.mjs`, step 6). Loop over
**every** route from step 1. Two rules that came straight from the live run:

**(a) WAIT for the async list before capturing.** These are SPA pages; capturing too early gives a
blank shell (LCA suites/builds shipped empty for exactly this reason). Navigate, then poll until the
rows actually exist — don't just `sleep`:
```js
// after navigate: wait up to ~10s for real rows, then capture
await new Promise(res=>{const t=Date.now();(function p(){
  const n=document.querySelectorAll('tbody tr, [role="row"], [class*="row"]').length;
  if(n>3||Date.now()-t>10000) return res(); setTimeout(p,300);})();});
```

**(b) KEEP the rows — a blank list is not the product.** Do NOT prune the records; save the region's
outerHTML as-is (raw):
```js
const src=document.querySelector('#app-main-content')||document.querySelector('#webapp-content');
download('<slug>.html', src.outerHTML);   // RAW. All name/email/URL scrubbing runs at share-time.
// SIGNATURE — the ground truth self-check diffs against. MUST be taken at capture time (live data
// drifts within hours, so a later comparison would false-alarm):
const inp=[...src.querySelectorAll('input,select,textarea')];
download('<slug>.sig.json', JSON.stringify({
  at:new Date().toISOString(), url:location.href,
  text:src.innerText.replace(/\s+/g,' ').trim().length,
  imgs:src.querySelectorAll('img').length, svgs:src.querySelectorAll('svg').length,
  buttons:src.querySelectorAll('button').length, links:src.querySelectorAll('a[href]').length,
  inputs:inp.length, inputsWithState:inp.filter(i=>i.value||i.checked||(i.tagName==='SELECT'&&i.selectedIndex>0)).length
}));
```
**While you're on each live screen, also take a full-page screenshot** and save it as
`products/<slug>/app-shell/self-check/prod/<slug>.png`. The self-check (step 6) diffs the assembled
shell against these prod references — no reference, no visual diff.
The scrub rules (author names, emails, `firstlast_XXXXXX` usernames, customer URLs/domains) all live in
one place now — `scripts/scrub-for-share.mjs` — and run in step 6 when you build the shareable copy.
Titles (e.g. "Login flow") are never touched; only names/emails/customer domains get replaced there.

Save each into `products/<slug>/app-shell/screens/` (the **raw working set — gitignored**) plus a
`screens.json` listing **every** screen in sidebar order:
```json
[
  { "slug": "tests",       "label": "Tests" },
  { "slug": "suites",      "label": "Test suites" },
  { "slug": "builds",      "label": "Builds" },
  { "slug": "folders",     "label": "Folders" },
  { "slug": "secrets",     "label": "Secrets" },
  { "slug": "settings",    "label": "Settings" },
  { "slug": "test-editor", "label": "Test editor", "detailFor": "tests" }
]
```
`slug` = the route tail the sidebar links to (matched from `<a href>`). A screen reached by clicking a
**row** (not a nav link) is a detail page: give it `"detailFor": "<section-slug>"`, and the assembler
wires `/<section>/<id>` clicks to open it — no code change per product.

## 5. Assemble the RAW working shell (design in this)
```bash
node scripts/assemble-multiscreen.mjs --slug <slug>     # -> app-shell/multiscreen-shell.html (RAW)
```
The assembler injects each screen as a panel, wires the sidebar to switch (top-level slugs **and**
`detailFor` detail routes, data-driven from `screens.json`), sets the real active-nav classes on the
current screen, and **prunes any chrome that leaked into a panel**. This shell has **real data** — it's
your local working copy. Do not commit/share it (it's gitignored).

## 6. SELF-CHECK the raw shell — the fidelity gate (before any share)
Verify every screen actually rendered like prod **before** you build the shareable copy. This catches
the real failures this skill has hit — a pruned nav bar, a blank panel, a spinner-only page, a
truncated column:
```bash
node scripts/self-check.mjs --slug <slug>          # MUST exit 0
```
It runs automated structural gates per screen (BLANK · SPINNER · NO_TOPBAR · NO_SIDEBAR · TRUNCATED),
screenshots each panel, and — using the `self-check/prod/*.png` references from step 4 — writes
`self-check/compare.html` pairing **PROD ↔ SHELL** per screen.
1. If any screen **FAILS**, fix it and re-assemble until green: re-capture the screen, adjust the
   prune (`assemble-multiscreen.mjs`), strip a stuck loading overlay, or widen the container.
2. Open `compare.html` and eyeball every pair — a DOM gate can't judge layout fidelity; your eyes
   catch subtler drift (wrong spacing, missing section, misaligned columns). Fix those too.
Only when self-check is green **and** the pairs look faithful do you move on.

## 7. Build the SHAREABLE copy at share-time (scrub + GATE)
Now — and only now — build the scrubbed copy. This is the **only** version you commit, bundle, upload,
or share:
```bash
node scripts/scrub-for-share.mjs --slug <slug>          # -> app-shell/share/multiscreen-shell.html
```
It scrubs every screen (author names, emails, `firstlast_XXXXXX` usernames, customer URLs/domains),
re-assembles the shell from the scrubbed screens, and runs `scrub-gate` on the result — a **hard stop**
if any PII remains. If it fails, add the offending markup to `scrub-for-share.mjs` and re-run.

## 8. Final look (mandatory)
Open the **share** build and click through the whole sidebar. Self-check validated the raw shell's
layout; here confirm the scrub didn't break anything and no real name slipped through (config pages are
worst; prefer capturing those from a local seeded instance — see `capture-sources.md`).

## Gotchas the live run surfaced (don't relearn them)
- **Screens hide in collapsed groups** → expand every group before the step-1 dump, or you ship an L1
  shell that looks "done" but is missing half the product.
- **Blank async lists** → always the wait-for-rows poll (step 4a), never a bare sleep.
- **Content-wrapper id varies per route** → always use the fallback selector.
- **Two different author markups** → tests use `<span>… by</span><span>Name</span>`; suites/builds use
  `<div>by Name on <date></div>`. Both scrubs live in `scrub-for-share.mjs`; the gate re-scans
  **tag-stripped text** so a name split across tags can't slip through. If the share gate flags a name,
  add its markup to `scrub-for-share.mjs` and re-run.
- **Detail pages can be partial** → heavily-interactive drill-ins (a step editor, a live run) may not
  hold their full multi-column state in a static snapshot. Capture the most representative state; if a
  detail page renders thin/truncated, note it rather than shipping it as if faithful.
- **Some pages render as a bare spinner** → a page whose content is gated behind a JS-driven loading
  overlay (LCA's Integrations) captures DOM but paints only the spinner statically. Render it after
  stitching; if it's a spinner, remove the frozen loading overlay before capture or omit the page.
- **Duplicated sidebar vs the product-nav** → the product-nav sidebar lives INSIDE the content region and shares `fixed inset-y-0` with the chrome icon-rail. The assembler now prunes only panel elements whose fingerprint (aria-label/id/class) matches something already in the chrome, so the product-nav is kept and real leaked chrome is removed. If the nav vanishes, the fingerprint missed — check the prune in assemble-multiscreen.mjs.
- **Third-party widget URLs** (Beamer, intercom) may trip the gate → allowlist with `--allow` or
  neutralize; not PII.

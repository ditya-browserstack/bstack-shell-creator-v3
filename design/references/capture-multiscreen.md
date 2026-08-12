# Capturing a MULTI-SCREEN shell (EVERY major page, not just the landing screen)

This is the **primary** shell-capture flow. A single-surface shell only covers the home screen; a
real product is a dozen screens. This flow discovers **every** screen the product exposes and
stitches them into **one file** where the sidebar switches between them. Proven live on LCA
(2026-08-11).

**The mandate: capture every distinct destination — do NOT hand-pick a few.** That means top-level
nav, every item inside collapsible sidebar groups, *and* at least one representative detail page per
list (the page you reach by clicking a row). A shell that only has Tests/Settings is L1; a faithful
shell has the whole left rail plus the drill-ins.

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
let css=''; for(const s of document.styleSheets){try{css+=[...s.cssRules].map(r=>r.cssText).join('\n')+'\n';}catch(e){}}
const body=document.body.cloneNode(true);
const cc=body.querySelector('#app-main-content')||body.querySelector('#webapp-content');
const mount=document.createElement('div'); mount.id='screen-mount'; if(cc) cc.replaceWith(mount);
body.querySelectorAll('script,[data-headlessui-portal],#storybook-highlights-root').forEach(n=>n.remove());
const doc=scrub(`<!DOCTYPE html><html><head><meta charset="utf-8"><style>${css}</style></head><body>${body.innerHTML}</body></html>`);
download('chrome.html', doc);
```

## 4. Capture each screen's content (navigate + WAIT FOR DATA + scrub)
Loop over **every** route from step 1. Two rules that came straight from the live run:

**(a) WAIT for the async list before capturing.** These are SPA pages; capturing too early gives a
blank shell (LCA suites/builds shipped empty for exactly this reason). Navigate, then poll until the
rows actually exist — don't just `sleep`:
```js
// after navigate: wait up to ~10s for real rows, then capture
await new Promise(res=>{const t=Date.now();(function p(){
  const n=document.querySelectorAll('tbody tr, [role="row"], [class*="row"]').length;
  if(n>3||Date.now()-t>10000) return res(); setTimeout(p,300);})();});
```

**(b) KEEP the rows — a blank list is not the product.** Do NOT prune the records; **scrub the data
inside them** so the page stays full but carries no real people or customers:
```js
const src=document.querySelector('#app-main-content')||document.querySelector('#webapp-content');
let html=src.outerHTML
  // author name is the <span> right after "... by </span>": replace just that span's text
  .replace(/((?:updated|created|modified|shared|added|last edited) by\s*<\/span>\s*<span[^>]*>)[^<]{1,80}(<\/span>)/gi,'$1Sample User$2')
  // second author markup (real on LCA suites/builds): "<div>by Firstname Lastname on Aug 11 …</div>"
  .replace(/\bby\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2}\s+on\b/g,'by Sample User on')
  // customer URLs + bare hostnames (incl. trailing paths) -> example.com; keep browserstack/example/CDNs
  .replace(/https?:\/\/(?!(?:[a-z0-9-]+\.)*(?:browserstack\.com|example\.com))[a-z0-9.-]+[^\s"'<>]*/gi,'https://example.com')
  .replace(/\b(?!(?:www\.)?(?:browserstack|example|w3|gstatic|googleapis|schema)\.)([a-z0-9-]+(?:\.[a-z0-9-]+){1,3}\.(?:com|co|io|net|org|in|dev|app|ai))\b/gi,'example.com')
  // standalone emails (real on config pages as VALUES) -> fake; keep already-safe example.*
  .replace(/[a-zA-Z0-9._%+-]+@(?!example\.(?:com|org|net))[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g,'user@example.com')
  // BrowserStack usernames in "created by" columns (firstlast_XXXXXX) -> fake
  .replace(/\b[a-z][a-z0-9]*_[A-Za-z0-9]{6}\b/g,'teammate_ab12cd');
download('<slug>.html', html);
```
Test/suite/build **titles** (e.g. "Login flow") are not personal data — keep them; they make the page
realistic. Only names, emails, and customer domains get replaced.

Save each into `products/<slug>/app-shell/screens/` plus a `screens.json` listing **every** screen in
sidebar order:
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

## 5. Assemble + prune + wire the switcher + GATE
```bash
node scripts/assemble-multiscreen.mjs --slug <slug>
node scripts/scrub-gate.mjs products/<slug>/app-shell/screens/*.html \
     products/<slug>/app-shell/multiscreen-shell.html    # MUST exit 0 on all of them
```
The assembler injects each screen as a panel, wires the sidebar to switch (top-level slugs **and**
`detailFor` detail routes, data-driven from `screens.json`), sets the real active-nav classes on the
current screen, and **prunes any chrome that leaked into a panel** (some routes' content wrapper
wrongly includes the sidebar, which would render it twice).

## 6. Look at EVERY screen (mandatory)
Open the shell and click through the whole sidebar, including the collapsed-group items and the
detail pages. A green gate is not fidelity — only your eyes catch a blank list, a truncated header,
or a leaked name the regexes missed.

## Gotchas the live run surfaced (don't relearn them)
- **Screens hide in collapsed groups** → expand every group before the step-1 dump, or you ship an L1
  shell that looks "done" but is missing half the product.
- **Blank async lists** → always the wait-for-rows poll (step 4a), never a bare sleep.
- **Content-wrapper id varies per route** → always use the fallback selector.
- **Two different author markups** → tests use `<span>… by</span><span>Name</span>`; suites/builds use
  `<div>by Name on <date></div>`. Both scrubs are in step 4b; the gate re-scans **tag-stripped text**
  so a name split across tags can't slip through. If the gate flags a name, add its markup to 4b.
- **Detail pages can be partial** → heavily-interactive drill-ins (a step editor, a live run) may not
  hold their full multi-column state in a static snapshot. Capture the most representative state; if a
  detail page renders thin/truncated, note it rather than shipping it as if faithful.
- **Some pages render as a bare spinner** → a page whose content is gated behind a JS-driven loading
  overlay (LCA's Integrations) captures DOM but paints only the spinner statically. Render it after
  stitching; if it's a spinner, remove the frozen loading overlay before capture or omit the page.
- **Duplicated sidebar** → the assembler prunes leaked chrome; verify only ONE sidebar renders.
- **Third-party widget URLs** (Beamer, intercom) may trip the gate → allowlist with `--allow` or
  neutralize; not PII.

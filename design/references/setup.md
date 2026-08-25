# SETUP — onboard a product (once)

Produces the two things a product needs: its **component sheet** (= the shared DesignStack core,
reused) and its **real captured shell** (the product's identity). USE mode then reads these every day.

**Never start SETUP silently in the middle of a USE run.** Offer it and wait — it takes real work.

Operator note: SETUP assumes repo access, a reachable logged-in product, and the ability to run
Claude Code. Everyday USE does not.

## Step 1 — Fill and validate the config
Follow `references/config-guide.md`. Create `products/<slug>/product.config.json`, then validate:
```bash
cd ~/.claude/skills/bstack-shell-creator-v2/design   # the installed skill's design/ folder
node -e "import('./lib/config.mjs').then(m=>{m.loadProductConfig('<slug>',{skillRoot:process.cwd()});console.log('config ok')})"
```
Fill `chrome.topbar`/`chrome.sidebar`/`chrome.contentSlot` by inspecting `liveUrl` in the browser.

## Step 2 — Get the component sheet (the shared core)
- `designSystem: "designstack"` → **reuse the shared core.** Mirror it into the product for convenience:
  ```bash
  cp core/designstack-sheet.html products/<slug>/app-shell/component-sheet.html
  cp core/designstack-sheet.css  products/<slug>/app-shell/component-sheet.css
  cp core/core-manifest.json     products/<slug>/app-shell/sheet-manifest.json
  ```
  (This copy is intentional and identical to the core — it is *not* a separately captured product
  sheet. There is no per-product primitive capture.)
- `designSystem: "custom"` → capture the product's own primitives: `capture-storybook.mjs --product <slug>`.

## Step 3 — Capture the real shell (the product's identity) — ALL major screens
**First, ASK the user what source(s) they can provide** — a live/prod URL, a localhost instance, and/or
the repo — and route each page to the safest one (`references/capture-sources.md`). Do not assume a
source: prod is fine for list pages but leaks real names on config/admin pages, which must come from a
local seeded instance. Capture "both sources, per-page" when the user gives more than one.

**This is the important step, and it is multi-screen by default.** A one-screen shell is L1 and reads
as unfinished. Follow `references/capture-multiscreen.md` — live-DOM capture from the running product
via Claude-in-Chrome that **discovers and captures every screen**: top-level nav, every item inside
collapsible sidebar groups, *and* representative detail pages (the page you reach by clicking a row).
It produces `products/<slug>/app-shell/multiscreen-shell.html` — the real chrome (top bar · sidebar)
wrapping a panel per screen, with the sidebar switching between them.

Do **not** hand-pick a handful of screens. The discovery step in capture-multiscreen.md enumerates the
full list mechanically (expand groups → dump every `<a href>` → cross-check the repo route map) so
nothing is missed. `references/capture-shell.md` is the single-screen fallback (a product with no
sidebar, or when you genuinely only need one surface).

There is **no separate "Tier 5–6 composites in the sheet" step** — the product's composed surfaces
live in these captured screens, not as sheet blocks.

## Step 4 — Assemble → self-check → share (in that order)
```bash
node scripts/assemble-multiscreen.mjs --slug <slug>   # RAW working shell (real data, local)
node scripts/self-check.mjs           --slug <slug>   # FIDELITY GATE — must exit 0
node scripts/scrub-for-share.mjs      --slug <slug>   # -> share/ (scrubbed + PII gate) — the only shareable copy
```
The assembler stitches the screens and wires the switcher (nav + `detailFor` routes). **self-check** is
the fidelity gate: it structurally checks every screen (blank / spinner / missing topbar / missing
sidebar / truncated), screenshots each panel, and pairs them against the prod references in
`self-check/compare.html`. Fix any FAIL and re-assemble until green — *then* build the share copy.
Capture stays RAW; scrubbing happens only in `scrub-for-share`. Never share a raw shell.

## Step 5 — Look at EVERY screen (mandatory)
```bash
open -a "Google Chrome" products/<slug>/app-shell/multiscreen-shell.html
```
Click through the whole sidebar — including the collapsed-group items and the detail pages. The
chrome must read as the real product; lists show data, not blanks; icons/fonts render; no real
names/emails/URLs remain. A green gate is not "captured the right thing" — only your eyes catch that.

## Done
The product has a component sheet (core) + a real shell. Everyday USE turns any TB into explorations
mounted in that shell (`references/mount-switcher.md`). To keep the shell fresh over time, hand it to
`shell-sync` (`references/shell-sync-handoff.md`).

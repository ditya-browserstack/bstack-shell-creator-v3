# SETUP — onboard a product (once)

Produces the two things a product needs: its **component sheet** (= the shared DesignStack core,
reused) and its **real captured shell** (the product's identity). USE mode then reads these every day.

**Never start SETUP silently in the middle of a USE run.** Offer it and wait — it takes real work.

Operator note: SETUP assumes repo access, a reachable logged-in product, and the ability to run
Claude Code. Everyday USE does not.

## Step 1 — Fill and validate the config
Follow `references/config-guide.md`. Create `products/<slug>/product.config.json`, then validate:
```bash
cd ~/projects/lcnc-workspace/lcnc-backend/workspace/skills/bs-design-from-tb
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

## Step 3 — Capture the real shell (the product's identity)
**This is the important step.** Follow `references/capture-shell.md` — live-DOM capture from the
running product via Claude-in-Chrome. It produces `products/<slug>/app-shell/shell-scaffold.html`:
the real chrome (top bar · sidebar · the surface's own composed rows) around an empty content slot.

There is **no separate "Tier 5–6 composites in the sheet" step** — the product's composed surfaces
live in this captured shell, not as sheet blocks.

## Step 4 — Finalize + scrub gate (hard stop)
```bash
node scripts/finalize-shell.mjs products/<slug>/app-shell/shell-scaffold.html --slug <slug>
node scripts/scrub-gate.mjs products/<slug>/app-shell/shell-scaffold.html   # MUST exit 0
```
`finalize-shell` inlines the font (self-contained), injects the `chrome.contentSlot` SOLUTION BODY,
and runs the scrub gate. Do **not** commit a shell that fails the gate.

## Step 5 — Look at it (mandatory)
```bash
open -a "Google Chrome" products/<slug>/app-shell/shell-scaffold.html
```
The chrome must read as the real product; icons/fonts render; no real names/emails/URLs remain. A
green "captured" is not "captured the right thing" — only your eyes catch that.

## Done
The product has a component sheet (core) + a real shell. Everyday USE turns any TB into explorations
mounted in that shell (`references/mount-switcher.md`). To keep the shell fresh over time, hand it to
`shell-sync` (`references/shell-sync-handoff.md`).

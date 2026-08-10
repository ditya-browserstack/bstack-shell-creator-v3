# Fallback: reconstructing product UI when you can't capture it live

**Read `references/capture-shell.md` first — live capture is the primary method.** This file is the
*fallback* for the rare case where no running instance of the product is reachable at all (no
staging, no prod, no login). Reconstruction is lower fidelity; use it only when live capture is
genuinely impossible, and say so in the manifest.

## The model (Option A — settled)
- **Component sheet = the shared DesignStack core** (primitives: buttons, tables, switches, alerts,
  modals). One copy, reused by every product. A designstack product does **not** capture its own
  sheet — it reuses `core/`.
- **Product identity = the captured shell** (`shell-scaffold.html`), from `capture-shell.md`.
- There is **no separate "product composites in the sheet" layer.** The product's composed surfaces
  (e.g. LCA's recorder row) live in the captured shell, not as sheet blocks. (This retires the old
  Tier 5–6 idea, which had no consumers and duplicated the shell.)

## If you must reconstruct (fallback only)
When there's no reachable app, build the shell from the shared core primitives + the repo + any
screenshots you can get:

1. Read the repo for how the product composes its chrome/surface (which primitives, what arrangement).
2. Use any available screenshots for layout truth.
3. Assemble the chrome from the core's real compiled primitives into a `shell-scaffold.html` with an
   empty content slot — and **mark it clearly as reconstructed** (`shell: reconstructed`) in the
   manifest, because it is *shaped like* the product, not the product.
4. Never invent a component that isn't in the core — record the gap instead.

A reconstructed shell is a stopgap. Replace it with a live capture as soon as the app is reachable.

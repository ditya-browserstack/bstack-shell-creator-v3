---
name: bs-design-from-tb
description: >-
  Turn a task brief into near-production-quality design explorations for any BrowserStack product.
  Reads a TB, then hands /design a component sheet of real DesignStack markup plus app-shell
  scaffolds so explorations look like the real product, not generic AI wireframes. Works per
  product via a small product.config.json + a shared DesignStack core. Use when a designer says
  "design this TB", "explore designs for X", "wireframe this feature". Starts from an existing TB.
user-invocable: true
argument-hint: "<product-slug> <TB file path, Confluence link, or pasted brief>"
---

# BrowserStack Design from TB

Two modes. USE is the everyday path; SETUP is run once per product.

| Mode | When | Reference |
|---|---|---|
| USE   | a TB exists and the product has an app shell | `references/brief-contract.md` |
| SETUP | a product has no app shell yet, or it is stale | `references/setup.md` |

## Mode router
1. Resolve the product config: read `products/<slug>/product.config.json` (validated by `lib/config.mjs`).
   If the slug has no config, that product isn't onboarded yet → SETUP.
2. If `products/<slug>/app-shell/component-sheet.html` is missing → SETUP (`references/setup.md`).
3. Else run the freshness check (`references/freshness.md`); if stale, offer SETUP, else USE.

Reference files are read **when you reach that step, not upfront.**

| Step | File |
|---|---|
| Read the TB | `references/tb-import.md` |
| USE hand-off | `references/brief-contract.md` |
| Freshness / manifest gaps | `references/freshness.md` |
| SETUP (all steps) | `references/setup.md` |
| SETUP: config fields | `references/config-guide.md` |
| SETUP: capture the real shell (primary) | `references/capture-shell.md` |
| SETUP: capture ALL major pages (multi-screen) | `references/capture-multiscreen.md` |
| SETUP: reconstruct shell if no live app (fallback) | `references/capture-app.md` |
| SETUP: sheet shape + how to check | `references/sheet-structure.md` |
| USE: mount explorations in the real shell (one tab + switcher) | `references/mount-switcher.md` |
| Keep the shell fresh over time (hand to shell-sync) | `references/shell-sync-handoff.md` |

---

## USE — the everyday path

A TB exists and the product already has an app shell. Turn the TB into 1–3 high-fidelity explorations.

1. **Read the TB** (hard gate). File, pasted text, or a Confluence link — nothing else. No TB, stop
   and ask. See `references/tb-import.md`. Pull out: problem, who it's for, use cases, out of scope.
   The use cases become the states every exploration must cover.
2. **Check freshness + gaps.** `references/freshness.md` — report any core/product drift and any
   relevant `missingStoryIds` / `failures` *before* designing.
3. **Pick the blocks** this feature needs from `products/<slug>/app-shell/component-sheet.html`.
   If a needed block isn't in the sheet, **say so — never invent it.**
4. **Write the brief + explorations** per `references/brief-contract.md`. The deliverable is
   **one `explorations.html`** — the real app shell (`app-shell/shell-scaffold.html`) with each
   variation mounted as an isolated, auto-height `panel-N.html` inside the surface-width container,
   switched by a floating bottom-right toggle. Follow `references/mount-switcher.md` exactly (it
   fixes the large-screen crop + chrome-collision traps). Never hand reviewers N separate tabs.
5. **Hand off in the same session:** invoke `/design <feature>` now, while the brief is in context.
   Don't write the files and stop — `/design` looks for brainstorm docs on disk, not briefs.
6. **Review** the output against the checklist in `references/brief-contract.md`.

---

## SETUP — onboard a product (once)

The product has no shell yet, or it's stale. Build it. Full steps in `references/setup.md`:

1. Fill + validate `products/<slug>/product.config.json` (`references/config-guide.md`).
2. **Component sheet = the shared core** — reuse `core/designstack-sheet.html` (mirror it into the
   product). A designstack product does **not** capture its own sheet. (`custom` → capture its own
   primitives with `capture-storybook.mjs --product <slug>`.)
3. **Capture the real shell** — live-DOM from the running product (`references/capture-shell.md`).
   This is the product's identity; there is no separate "Tier 5–6 composites in the sheet" step.
4. **Finalize + scrub gate (hard stop):** `finalize-shell.mjs` (self-contain + slot) then
   `scrub-gate.mjs` must exit 0. **Never commit a shell that fails the gate.**
5. **Look at it in Chrome** — a green "captured" ≠ the right capture.

Never start SETUP silently mid-USE. Offer it and wait.

## Rules
- **No TB, no USE run.** Reading the TB is a hard gate.
- **Never describe a component in prose as a substitute for markup** — prose gets rebuilt from scratch.
- **If a component isn't in the sheet, say so.** Turning silent invention into a question is the
  single most valuable rule here.
- **Never use a stale sheet silently.** Report the version gap.
- **Design system is a per-product input** — `designstack` (shared core) or `custom` (own source).
- **Don't edit `/design` or its files.** Work around them with the brief and scaffolds.

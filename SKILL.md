---
name: bstack-design-studio
description: >-
  End-to-end design studio for any BrowserStack product: capture the real app shell, turn a task
  brief into high-fidelity explorations inside it, and keep that shell honest against production
  over time. Combines shell capture + TB→explorations (design/) with shell-sync's weekly
  production diff, versioning, and Claude Design bridge (sync/). Use for "set up my product",
  "design this TB", "explore designs for X", "is my shell up to date", "sync the shell".
user-invocable: true
argument-hint: "<command> — setup | design <slug> <TB> | sync | check | new | publish | storyboard"
---

# Bstack Design Studio

One skill, two engines that hand off cleanly:

- **`design/`** — *produce.* Capture a product's **real app shell** + turn a **TB into 1–3
  high-fidelity explorations** mounted in that shell (one tab + variation switcher).
- **`sync/`** — *maintain.* Keep the shell honest against what shipped (weekly GitHub diff),
  manage git-backed design versions, publish/share, and bridge into Claude Design.

`ATTRIBUTION.md` — `sync/` is Harsh Kothari's **shell-sync**, forked verbatim; `design/` is
`bs-design-from-tb`. See it before editing `sync/`.

## Step 0 — check for updates (run first, every invocation)
Before routing, run `node design/scripts/check-update.mjs` (git-based, throttled to once/24h, fails
silent — it never blocks you). If it prints an `UPDATE_AVAILABLE` line, tell the designer in one
sentence (version + the changelog headline) and **offer to update**: on yes, run the `UPDATE_CMD` it
printed (`git -C <root> pull --ff-only`) and ask them to re-invoke the skill; on no, continue. Their
captures in `products/` are gitignored, so an update never touches their work.

## Command router

| The designer says | You run | Engine |
|---|---|---|
| set up my product | `design/` SETUP → `references/setup.md` | design |
| design this TB / explore X | `design/` USE → `references/brief-contract.md` + `references/mount-switcher.md` | design |
| hand my shell to sync (once) | the handoff below | bridge |
| is my shell up to date / `check` | `cd sync && python3 lib/doctor.py` | sync |
| sync the shell (weekly) | `cd sync` → the six stages in `sync/SKILL.md` | sync |
| new version / publish / share / storyboard / handover | `cd sync && python3 lib/versions.py …` etc. (`sync/SKILL.md`) | sync |

If a command is unrecognised, show this table — never guess.

## The everyday story

1. **Set up once (`design/`).** Fill `design/products/<slug>/product.config.json`, capture the real
   shell (`design/references/capture-shell.md`), reuse the shared DesignStack core. You now have
   `design/products/<slug>/app-shell/shell-scaffold.html`.
2. **Design any day (`design/`).** Drop a TB → explorations in the real shell, one tab + switcher.
   Nothing in `sync/` is needed for this.
3. **Keep it fresh (`sync/`), optional.** Hand the shell to shell-sync once, then run `sync` weekly.

## The bridge (design → sync), one time per product
```bash
cd design
node scripts/shell-sync-onboard.mjs --slug <slug>     # → app-shell/shell-sync-onboard.json (config)
node scripts/handoff-to-sync.mjs    --slug <slug>     # COMPLETE screen-map + screenshots + @dsCard gallery
cd ../sync
python3 lib/onboard.py write ../design/products/<slug>/app-shell/shell-sync-onboard.json
```
`handoff-to-sync.mjs` removes the old manual step: it derives a **complete** `shell-sync-screens.json`
(nav + verify filled from the multi-screen capture — no paste, no gate/verify TODO), then runs Harsh's
`capture.mjs` **unmodified** against our plain-HTML shell to screenshot every screen and wrap each into
a self-contained `@dsCard` preview the Claude Design pane indexes → `app-shell/cards/`. Top-level
screens verify on their heading; detail pages (`detailFor`) get a panel-unique verify so a missed
row-click is reported, never mislabelled.

## The one real seam (documented, not hidden)
`design/` captures the product as **plain HTML** (now multi-screen). `sync/`'s weekly *brain*
(`index.py`/`match.py`) reads **Claude Design `x-dc` shells** (`<sc-if cond="screen===…">`), so it
can *deep-parse* only a Claude Design export.
- `sync`'s screenshotter (`capture.mjs`) **does** drive the plain-HTML shell — `handoff-to-sync.mjs`
  feeds it and produces the `@dsCard` gallery. Screenshots + cards work end-to-end, no fork edit.
- `sync`'s diff/index **cannot** deep-parse it → for full weekly-sync reasoning the shell must be a
  Claude Design export. This boundary is inherent to forking two different shell formats; it is not
  a bug to fix silently. Prefer: use `design/` for capture + explorations; use `sync/` for freshness
  on Claude-Design-origin shells.

## Rules
- Everyday USE + SETUP live in `design/` (its `SKILL.md` and `references/` are authoritative there).
- Weekly sync + versions live in `sync/` (Harsh's `SKILL.md` is authoritative there; run with `python3`).
- Never edit `sync/` to fit `design/` — it is a verbatim fork; re-sync from upstream `shell-sync.zip` instead.
- Everything else inherits `design/`'s rules (no TB no run · never invent a component · scrub gate before commit).

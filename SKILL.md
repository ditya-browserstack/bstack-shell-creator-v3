---
name: bs-design-studio
description: >-
  End-to-end design studio for any BrowserStack product: capture the real app shell, turn a task
  brief into high-fidelity explorations inside it, and keep that shell honest against production
  over time. Combines shell capture + TB→explorations (design/) with shell-sync's weekly
  production diff, versioning, and Claude Design bridge (sync/). Use for "set up my product",
  "design this TB", "explore designs for X", "is my shell up to date", "sync the shell".
user-invocable: true
argument-hint: "<command> — setup | design <slug> <TB> | sync | check | new | publish | storyboard"
---

# BS Design Studio

One skill, two engines that hand off cleanly:

- **`design/`** — *produce.* Capture a product's **real app shell** + turn a **TB into 1–3
  high-fidelity explorations** mounted in that shell (one tab + variation switcher).
- **`sync/`** — *maintain.* Keep the shell honest against what shipped (weekly GitHub diff),
  manage git-backed design versions, publish/share, and bridge into Claude Design.

`ATTRIBUTION.md` — `sync/` is Harsh Kothari's **shell-sync**, forked verbatim; `design/` is
`bs-design-from-tb`. See it before editing `sync/`.

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
node scripts/finalize-shell.mjs     products/<slug>/app-shell/shell-scaffold.html --slug <slug>
node scripts/shell-sync-onboard.mjs --slug <slug>     # → app-shell/shell-sync-onboard.json
node scripts/screen-map-draft.mjs   products/<slug>/app-shell/shell-scaffold.html --slug <slug>
cd ../sync
python3 lib/onboard.py write ../design/products/<slug>/app-shell/shell-sync-onboard.json
# paste ../design/products/<slug>/app-shell/screen-map.draft.md into lib/storyboard.py SCREENS; confirm gate/verify
```

## The one real seam (documented, not hidden)
`design/` captures a **single high-fidelity surface as plain HTML**. `sync/`'s weekly *brain*
(`index.py`/`match.py`) reads **Claude Design `x-dc` shells** (`<sc-if cond="screen===…">`), so it
can fully reason only about a Claude Design export.
- `sync`'s screenshotter (`capture.mjs`, storyboard) **can** drive the plain-HTML shell (it clicks
  nav labels + checks `verify` text) → screenshots work.
- `sync`'s diff/index **cannot** deep-parse it → for full weekly-sync reasoning the shell must be a
  Claude Design export. This boundary is inherent to forking two different shell formats; it is not
  a bug to fix silently. Prefer: use `design/` for capture + explorations; use `sync/` for freshness
  on Claude-Design-origin shells.

## Rules
- Everyday USE + SETUP live in `design/` (its `SKILL.md` and `references/` are authoritative there).
- Weekly sync + versions live in `sync/` (Harsh's `SKILL.md` is authoritative there; run with `python3`).
- Never edit `sync/` to fit `design/` — it is a verbatim fork; re-sync from upstream `shell-sync.zip` instead.
- Everything else inherits `design/`'s rules (no TB no run · never invent a component · scrub gate before commit).

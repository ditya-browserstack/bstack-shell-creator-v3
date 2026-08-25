# Attribution

`bstack-shell-creator-v2` combines two skills into one self-contained bundle.

## `sync/` — forked from **shell-sync**, by **Harsh Kothari** (vishant/harsh, BrowserStack Design)
- Everything under `sync/` is Harsh Kothari's `shell-sync` skill, **copied verbatim** from
  `shell-sync.zip` (the Python `lib/`, `tests/`, `SKILL.md`, `install.sh`, `adopt.html`). Original
  authorship and structure are preserved unchanged.
- **This is a fork.** It will **not** receive Harsh's future updates automatically. When shell-sync
  ships a new version, `sync/` must be re-synced by hand (drop in the new `shell-sync.zip` contents).
- shell-sync remains Harsh's owned skill. This fork exists for a single combined designer workflow;
  it does not replace or supersede his upstream. **Harsh should be told this fork exists.**
- Do not strip authorship from `sync/` files. Harsh's own `package.py` is allow-list based and
  refuses to ship content that names another team — respect that intent.

## `design/` — **bs-design-from-tb**, by Aditya Singh (BrowserStack, LCNC/LCA Design)
- The TB→explorations + real-shell-capture skill. Owned here.

## Why they're combined
`design/` **produces** a product's real shell + high-fidelity explorations; `sync/` **maintains** that
shell against production, versions it, and bridges to Claude Design. One front door
(`SKILL.md`) drives both so a designer runs a single skill. The seam between them (a live-captured
plain-HTML shell vs shell-sync's Claude Design `x-dc` shell) is documented in `SKILL.md` — it is a
real boundary, not hidden.

# Choosing a capture source — ASK the user first, don't assume

The shell can be built from three kinds of source. **Do not pick one silently.** Before any capture,
**ask the user what they can provide** — they may have one, two, or all three — then route each page to
the safest source they gave. This is a hard gate: a wrong source either fails (a repo you can't run) or
leaks (config pages from prod).

## The prompt to give the user (first thing in SETUP capture)
Ask, in plain words:

> "To build your product's shell I capture its real screens. What can you give me access to? Any one is
> enough, but more is better — I'll use the safest source for each page:
> 1. **A live/prod URL you're logged into** (e.g. `https://app.example.com`) — best fidelity for list
>    pages (Tests, Builds…). ⚠️ *Not* used for config/admin pages (Secrets, Users, Databases): those
>    hold real names I can't fully scrub.
> 2. **A localhost URL of a local instance with test data** (e.g. `http://localhost:5173`) — the safe
>    source for config/admin pages, because local seed data has no real people in it. Fine for
>    everything.
> 3. **The repo path** (e.g. `~/projects/…`) — lets me discover every route and, if it can run locally,
>    stand the app up to capture from.
> You can give more than one. What do you have?"

Then confirm what each is (paste the actual URL / path) before capturing.

## What each source is good and bad for
| Source | Gives you | PII posture | Use for |
|---|---|---|---|
| **Live / prod URL** | Real data, highest fidelity, zero setup | **Real customer PII** — safe only where the scrub patterns cover it | List/record pages (Tests, Suites, Builds, Modules, Settings) |
| **Localhost (seeded)** | Real rendering with *fake* data | **No real PII** — safe to share | **Config/admin pages** (Secrets, Global variables, Databases, Test datasets, Integrations, Users) — and anything else |
| **Repo (offline)** | The full route map; can be *run* to become a localhost source | n/a (source code, not a render) | Route discovery; standing up a local instance when there's no live localhost yet |

Reading the repo alone does **not** render pages (data-driven UI + runtime styles) — it either supplies
the route list, or gets *run* to become source #2.

## Route each page to a source (the "both sources, per-page" rule)
1. **List/record pages** → live prod if given (best fidelity), else localhost.
2. **Config/admin pages** → localhost only. If no localhost is available, **do not capture these from
   prod** — omit them, or (only if the user accepts) capture best-effort and stamp the shell
   **internal-only — do not share**.
3. **Detail pages** (row → editor/report) → same source as their list.
Stitch whatever mix you captured into the one multi-screen shell (`assemble-multiscreen.mjs`).

## Decision table — what the user gave → what you do
| User provides | Do this |
|---|---|
| **Live only** | Capture list pages from live. Tell the user config pages are **held back** (prod-PII); offer to add them once they give a localhost. |
| **Localhost only** | Capture **everything** from localhost — safest, fully shareable. |
| **Repo only** | Discover routes from it. If it runs (`SETUP.md`/compose), help stand up a localhost, then treat as localhost. If it can't run, you have the route map but no render — ask for a live or localhost URL. |
| **Live + localhost** | Ideal. List pages from live, config/admin from localhost. |
| **Live + repo** | Live for list pages; use the repo to run a localhost for config pages. |
| **All three** | Live for fidelity on list pages, localhost (booted from repo) for config pages, repo for the route map. |

## Guardrails
- **Never capture config/admin pages from prod** to ship/share — the scrub-gate cannot catch teammate
  usernames, secret labels, or env names embedded in user-authored text (see `capture-multiscreen.md`).
- **Never enter credentials or tokens** to boot a local stack — that's the user's to do; prompt them
  with the exact steps and wait.
- **Always run the scrub-gate** on every captured page regardless of source; local *should* be clean but
  the gate is still the ship gate.

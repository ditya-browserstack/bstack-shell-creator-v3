---
name: shell-sync
description: "Keep a product's Claude Design HTML shell in step with what shipped to production, fork unreleased design into named versions, and hand either to a developer. Detects releases from drop-branch PRs, checks each against the shell, captures the real UI, and codes missing features in behind an approval gate. Onboards to any product with a profile. Invoke with 'sync the shell', 'is my shell up to date', or /shell-sync."
disable-model-invocation: true
---

# /shell-sync

**Use for:** keeping a standalone Claude Design shell current with what shipped to production.

All paths below are relative to this skill directory. `cd` here first and run scripts
with `python3`.

`explainer.html` beside this file is the designer-facing walkthrough of the same workflow,
published as an artifact. **It restates facts that live here** — the branch patterns, the file
sizes, the test count, the first-run numbers. When you change any of those, update it too, or
say plainly that it is now stale.

## Invocation

Every entry point is an argument to the slash command. **Users should never have to name a
file or a script** — if someone asks how to do one of these, answer with the command, not a
path.

| The user says | You run |
|---|---|
| `/shell-sync check` | `python3 lib/doctor.py` |
| `/shell-sync onboard` | interview, then `python3 lib/onboard.py write …` |
| `/shell-sync` | the six stages below |
| `/shell-sync new <slug> "<label>"` | `python3 lib/versions.py new …` (add an export path to seed it) |
| `/shell-sync versions` | `python3 lib/versions.py list` |
| `/shell-sync share <slug>` | pack that version, hand back the path |
| `/shell-sync refresh [slug]` | `python3 lib/versions.py refresh` — merge prod parity into versions |
| `/shell-sync publish <slug>` | `python3 lib/versions.py publish <slug>` — push it so the team can open it |
| `/shell-sync storyboard [source]` | the storyboard flow |
| `/shell-sync handover <slug>` | pack, then `/design-handover` on the result |
| `/shell-sync package [path]` | `python3 lib/package.py <path>` — build the shareable zip |

Bare `/shell-sync` with no argument means the weekly sync. If the argument is
unrecognised, list this table rather than guessing.

## Giving this skill to someone outside the team

`/shell-sync package` writes a zip of the tool with none of anybody's content in it:
`lib/`, `tests/`, `SKILL.md`, `adopt.html`, plus a generated `README.md` and
`install.sh`. About 90 KB. The recipient unzips it, runs `install.sh`, restarts, and
runs `/shell-sync onboard`.

**Send the zip, not a repository link.** The repository this lives in is private with a
per-person access list, so a clone URL fails with *repository not found* for anyone not
on it — which reads as a typo, not a permissions problem. The zip needs no account and
no access request.

What is deliberately held back: `shell/` (a 5 MB shell of one product), `config.yaml`,
`ledger/`, `profiles/`, `boards.json`, `runs/`, and `explainer.html`. The recipient
supplies their own export and their own answers.

`lib/package.py` works from an **allow-list**, not an exclude-list, and refuses to write
if any shipped file still names the originating team or its repos. If you add a file that
belongs in the package, add it to `INCLUDE_FILES` or `INCLUDE_TREES`; a deny-list would
ship each new content file until somebody noticed.

Two invariants keep this honest, and both have failed before:

- **No test may assert on installed content.** Tests that read the live `config.yaml`,
  ledger or shell pass here and fail on a fresh install. Write a fixture, or skip
  explicitly when the content is absent.
- **No product-specific default in `lib/`.** `harvest.DEFAULT_TICKET_PREFIX` is empty and
  `ticket_re("")` raises, because interpolating an empty prefix silently matches every
  bare number in every PR title — every stage would still report success.

## Onboarding a new product

Nothing here is tied to one product except the answers in `config.yaml`. To point the skill at
another product — anything with a Claude Design shell — run
`/shell-sync onboard` and **conduct the interview yourself**, one question at a time,
in plain language. Do not dump the whole list at them.

Ask these, in this order:

1. **What is the product called, and what is its URL?** The URL is only used for live capture.
2. **How are its tickets written?** You want the Jira project key — `LCAM`, `LT`. Offer to check
   Jira if they are unsure; a wrong prefix fails *silently*, reporting that nothing shipped.
3. **Which repos are dedicated to it?** Every merged PR in these counts.
4. **Does its frontend live in a shared monorepo?** If yes, ask which, and then **what words mark
   its work there** — short product tokens and any nickname it goes by. Without this,
   half the gap report is another team's work.
5. **What branch does production ship from?** Trunk name included — this is the question people
   get wrong. The first product needed both `main` and `master`, because its frontend monorepo
   used `master`; missing it hid an entire shipped feature while the harvest reported no problems.
6. **Where does their Claude Design export live**, and which git repo should hold version
   branches? Both have sensible defaults; offer them. The repo can be any one the team shares —
   versions are branches in it, namespaced by product, so it need not be dedicated to this.

Then write the answers to a JSON file and run:

```bash
python3 lib/onboard.py write /tmp/<slug>.json
```

It validates the shape, **checks every repo is reachable with the current `gh` credentials**,
warns about the silent-failure cases above, and writes `profiles/<slug>.yaml`. Use the profile
by setting `APP_SHELL_PROFILE=<slug>` on any command.

**Two things onboarding cannot do for them**, and you should say so plainly:

- **The product needs a Claude Design shell to exist.** No shell, nothing to sync.
- **`storyboard.SCREENS` still has to be written by hand** for the new product — the click path
  and gate for each screen. That is the real per-product cost, and its own test will catch a
  wrong entry, but nobody can guess it. Say this before they start, not after.

## This skill is shared — read this first

Product and design both use it, and **anyone may run a sync at any time**. Most people
never run one: they pull and consume. Start any session with `check`, which reports what
this checkout has and writes nothing.

It reports the shell's fingerprint, whether you are behind the team, the ledger, which
versions exist, board state, and `gh` auth. It writes nothing. **If it says you are behind,
pull before running anything** — syncing from a stale shell re-detects features a colleague
already added.

What lives where, and why:

| | Where | Shared? |
|---|---|---|
| Prod-parity shell | harness repo, `shell/` | **yes** — a sync lands as a PR, everyone gets it on pull |
| Versions | git branches `shell/<product>/<name>` in `version_repo` | **yes** — push the branch and anyone can read it; never checked out locally |
| Ledger | harness repo, `ledger/` | **yes** — one file per feature and per run, so concurrent runs merge |
| Board state | `boards.json` | **no** — gitignored; every person has their own Claude Design project, and those cannot be shared across Claude teams |

Two rules that follow from anyone being able to run it:

- **Never hand-edit `ledger/`.** Adds are separate files precisely so two people never
  touch the same path. Collapsing them back into one file reintroduces the conflict.
- **Two people editing `shell/template.html` in the same week will conflict** on a 364 KB
  file. Git cannot merge that usefully. Say so and have the second person re-run after the
  first lands, rather than resolving it by hand.

## Critical invariants

- **Never hand back an unverified file.** Stage 6 verification is mandatory.
- **Never type the slash escape literally.** See `lib/bundle.py`; it is built as
  `chr(92) + "u002F"`. Typing it literally blanks the page.
- **Never edit `shell/host.html`.** It is the static manifest. Only
  `shell/template.html` is edited.
- **`shell/` is PROD PARITY.** It holds only what shipped. Unreleased design never goes
  here — it goes in a version. See `## Versions`.
- **Stop at the gate.** Nothing is written to the shell before the user approves.
- **DesignStack components only.** Every affordance you add must correspond to a real
  DesignStack component — `Badge`, `Tooltip`, `Hyperlink`, `Switch`, `Metadata`, and so
  on. Never invent a bespoke widget. See "Building with DesignStack" below.
- **Most shipped work is not a shell feature.** See Stage 1b — this is the single
  biggest source of a bad gap report.

## Stage 1 — Harvest

Work out the window, then query GitHub:

```bash
cd .claude/skills/shell-sync
SINCE=$(python3 -c "import sys; sys.path.insert(0,'lib'); import ledger, paths; from datetime import date; c=paths.load_config(); print(ledger.window_start(ledger.load(), c['default_window_days'], date.today()))")
TODAY=$(date +%F)
python3 -c "import sys; sys.path.insert(0,'lib'); import paths; paths.run_dir('$TODAY')"
python3 lib/harvest.py "$SINCE" > "runs/$TODAY/candidates.json"
```

If `problems` is non-empty, report it. If `gh` is unauthenticated, **abort** — tell the
user to run `gh auth status` and stop.

## Stage 1b — Enrich, then cut what is not user-visible

**Do not skip this.** `harvest.py` filters out obvious noise (version bumps, lockfiles,
unit tests, other products' work in shared monorepos) but it cannot tell a backend auth
fix from a new UI command. A real July 2026 window produced 17 candidates of which only a
handful were shell-visible; the rest were things like `fix(auth): default to v2 when local
group is unresolved` and `pass UiAutomator2 idle-timeout enrolment`. Proposing those as
shell features would waste the user's time and pollute the shell.

For each candidate with an `lcam_id`, use the **Atlassian MCP** (`getJiraIssue`) to get the
real summary, description, and components. Then:

1. Replace the PR-derived `name` with the Jira summary when available. PR titles like
   `Lcam 2582 first event user properties` do not name a user-visible feature.
2. **Drop any candidate with no user-visible UI surface** — infrastructure, telemetry,
   auth internals, worker tuning, runner behaviour, error classifiers. Keep it only if a
   designer would see something new or changed in the product's interface.
3. Note the surface each survivor belongs to: the test editor, the test list, or a surface
   the shell does not model yet.

If the Atlassian MCP is unavailable, continue on PR titles, mark the report **degraded**,
and be conservative — when you cannot tell whether something is user-visible, list it as
uncertain for the user rather than proposing to code it.

## Stage 2 and 3 — Index and verdict

```bash
python3 lib/match.py "runs/$TODAY/candidates.json" > "runs/$TODAY/verdicts.json"
```

`match.py` compares each feature name against the shell's catalog commands, screen names
and visible labels. Adjudicate every `UNCERTAIN` yourself by reading `shell/template.html`
around the cited evidence, and resolve each to `PRESENT` or `MISSING`.

Sanity check: if everything comes back `MISSING`, you probably skipped Stage 1b.

**Note on shell shapes.** Claude Design emits two export shapes and they are structured completely
differently. The Prototype-style export expresses its surface as a `catalog()` array of
labelled DSL commands. The fuller session shell has no catalog at all — its surface is
~376 visible markup labels (Secrets, Modules, Database, Global variables, Service account,
Test dataset, Media Library, …). `index.py` handles both and returns empty lists for
whatever a given shell lacks, so read the index before assuming where a feature would go:

```bash
python3 lib/index.py | python3 -c "import json,sys; d=json.load(sys.stdin); print({k: len(v) for k,v in d.items()})"
```

If `catalog_labels` is 0, insertions are markup edits, not catalog entries.

## Stage 4 — Live capture (Chrome DevTools MCP)

For `MISSING` features only. Use **Chrome DevTools MCP** against the user's already-running,
already-logged-in Chrome. Do not type credentials; do not use Playwright here.

1. `list_pages`, then `new_page` or `select_page` for the product URL (`product_url` in
   `config.yaml`).
2. Navigate to the feature and `take_screenshot` into `runs/<today>/live/`.

**Capture is best-effort. Never block on it, never guess an appearance.** If Chrome is not
running, is not logged in, or the feature cannot be reached, mark that feature
`NEEDS_SCREENSHOT`, add it to the ask-list, and **continue**.

Expect this often, for ordinary reasons: the feature is behind a flag or off-plan, reaching
it needs a real device session that costs test runs, or the path is not discoverable without
product knowledge. Note also that some products cannot run concurrently with a sibling product
in the same account — if a conflicting session is active, say so rather than fighting it.

Do **not** ask the user for screenshots here. Collect the ask-list and raise it once, at the gate.

## Stage 5 — GATE

Present the gap report in three groups:

1. **Ready** — `MISSING` with a captured screenshot. Show feature, LCAM id, verdict,
   evidence, surface, proposed insertion point, screenshot path.
2. **Needs a screenshot from you** — every `NEEDS_SCREENSHOT` feature. For each, give the
   Jira summary, the PRs, the proposed insertion point, and **why capture failed**, then ask
   the user to supply an image. They can paste it into the conversation or drop files into
   `runs/<today>/live/manual/`. **Read any images already in that directory before asking**,
   so a user who pre-dropped files is not asked for them twice.
3. **Out of reach** — reported for information only; no action proposed.

Batch the ask into this one message. Asking per-feature during Stage 4 turns the run into a
stream of interruptions.

For each item in group 2 the user may supply a screenshot, ask you to code it from the
description anyway, or skip it. A skipped feature is still missing from the shell, so the
next run re-detects and re-asks it — nothing is lost, and no ledger bookkeeping is needed to
get that behaviour.

Then **stop and wait** for the user to approve and select. Write nothing until they respond.

## Stage 6 — Code, repack, verify

For each approved feature, edit **`shell/template.html`** only:

- **If the shell has a `catalog()`** and the feature is a DSL command, add an entry there.
  Match the existing shape exactly: `{ icon, label, desc, dsl: [...] }`, with `icon` a
  Material Symbols name. This is the cheapest and safest insertion.
- **If the shell has no catalog** (the session shell does not), the insertion is a markup
  edit. Copy the styling of the nearest equivalent element rather than writing new CSS —
  the shell uses inline styles, `class="icon"` spans for Material Symbols, and
  `style-hover="..."` for hover states.
- For UI beyond a command, follow the existing `x-dc` idiom (`{{ }}`, `<sc-if>`, `<sc-for>`)
  and use DesignStack tokens already in the `<helmet>` block. Do not introduce new colours or
  fonts.
- For a new screen, add a value to the `screen` state key and an `<sc-if>` block, mirroring
  how `editor` and `list` are structured.
- Keep additions lo-fi. The shell mirrors what the product looks like, never what it does: no
  backend calls, no real device sessions.

### Building with DesignStack

**Only DesignStack components.** Before adding anything, name the DesignStack component it
is (`Badge`, `Tooltip` + `TooltipHeader`/`TooltipBody`, `Hyperlink`, `Switch`, `Metadata`,
`SelectMenu`, …). If you cannot name one, you are inventing a widget — stop and ask.

The shell cannot import DesignStack: it is a Claude Design export rendering plain markup in
the `x-dc` DSL. So "use DesignStack" here means **copy the shell's own existing rendering of
that component** rather than writing fresh CSS. The shell already renders most of them, and
those renderings are the source of truth:

| Component | Copy from |
|---|---|
| `Badge` (pill) | the `In use` badge in the service-account table |
| `Badge` (square) | the `Schedule: OFF` badge in the Test Suites list |
| `Tooltip` | the parallels tooltip — `#1F2937`, radius 10, rotated-square arrow, `ttEnter`/`ttLeave` |
| `Hyperlink` | the inline `Learn more` anchors (`#2563EB`, no underline) |
| `Switch` | the local-testing toggle (`#2563EB` on, `#E5E7EB` off, 24px knob) |

Read the real component source before mirroring it — `gh api
"repos/browserstack/frontend/pulls/<n>/files"` gives you the exact copy, the variant
modifiers, and which sub-elements are conditional. That is grounding, not guessing: the
Service Accounts tag's tooltip hides its header *and* its `Learn more` in the disconnected
state, which no screenshot alone would have told you.

Take colours from tokens already present in the `<helmet>` block. Never introduce a new
colour or font.

Then pack and verify:

```bash
python3 lib/bundle.py pack shell "runs/$TODAY/Shell.html"
```

Verify with **Playwright MCP** (not Chrome — this needs no auth and must not disturb the
user's browsing).

**Playwright MCP blocks the `file:` protocol**, so serve the packed file over loopback
first. Do not try `file://` — it fails with "Access to file: protocol is blocked".

```bash
cd "runs/$TODAY"
nohup python3 -m http.server 8899 --bind 127.0.0.1 > server.log 2>&1 &
sleep 2 && curl -s -o /dev/null -w "HTTP %{http_code}\n" http://127.0.0.1:8899/Shell.html
```

Then:

1. `browser_navigate` to `http://127.0.0.1:8899/Shell.html`
2. `browser_console_messages` at level `error` — there must be **no errors**. Ignore a
   404 for `/favicon.ico`; that is an artifact of the static server, not a page fault.
3. `browser_snapshot` — the new affordance must be in the DOM, and the page must not be
   blank. A blank page means the slash escaping broke; re-read the invariants.
4. `browser_take_screenshot` — pass an explicit `filename`, then move the file into
   `runs/<today>/shell/`. The MCP server resolves relative names against its own output
   directory, not the cwd, so the image may land in the home directory.

Stop the server when done: `pkill -f "http.server 8899"`.

**If Playwright reports "Browser is already in use":** a stale Chrome profile lock. Confirm
no process is running (`ps aux | grep ms-playwright`), then delete `SingletonLock`,
`SingletonSocket` and `SingletonCookie` from the profile directory named in the error.

**If Playwright MCP's tools are not reachable** (it can show Connected in `claude mcp list`
while its tools are absent from the session), do not skip verification and do not hand back
the file. Drive the same engine from Node instead — `playwright-core` is on disk and the
system Chrome binary works even when the bundled `chrome-headless-shell` build is missing:

```js
import { chromium } from '/Users/<you>/.npm/_npx/<hash>/node_modules/playwright-core/index.mjs';
const b = await chromium.launch({
  executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
});
```

Locate it with `find ~/.npm/_npx -maxdepth 6 -type d -name playwright-core`. `launch()` uses a
throwaway profile, so this does not disturb the user's browsing. Collect `console` +
`pageerror` events, assert the new affordance's text is in `document.body.innerText`, and
screenshot into `runs/<today>/shell/` — the same four checks as the MCP path.

**Most surfaces are behind an `<sc-if>` and are absent from the DOM until you navigate to
them.** Click through to the surface before asserting. Buttons that wrap a Material Symbols
span have the icon name glued to their label (`addCreate test suite`), so exact-text matching
fails — use `button:has-text("...")`.

**A passing `el.click()` proves nothing about whether a person can click it.** Programmatic
clicks bypass hit-testing entirely: they fire on covered elements, zero-size elements and
elements under an overlay. An affordance verified that way was reported as working and then
failed for the user. When the claim is *"the user can interact with this"*, use a real mouse
click (`locator.click()`) and confirm the target with `elementFromPoint`. Reserve `el.click()`
for merely *reaching* a screen you then assert on.

**And check the interaction the user will actually try, not the one you built.** The `@` picker
opened from a decorative affordance and was called done; the first thing the user did was click
into a step and *type* `@`, which was never wired. Ask what the product's real trigger is.

Place that screenshot beside the Stage 4 live capture as a **fidelity** check.

**If verification fails:** `git checkout -- shell/template.html`, report the failure, and
stop. Do not hand back the file.

**On success:** record each feature in the ledger, set `last_run`, commit
`shell/template.html` and `ledger.json`, and give the user the path to
`runs/<today>/Shell.html`.

Then **report version staleness** — `python3 lib/versions.py list`. Prod parity just moved, so
any version forked before this run is now behind. Surface it here, while the features are still
in front of the user, rather than letting them discover the drift weeks later:

```
Prod parity synced — 2 features added.

Versions behind prod parity:
  v1   secrets redesign    behind by 2
         Service accounts — Builds list "Ran with" column
         Service accounts — test-suite service account tag
```

Report only. Do not offer to replay, and never edit a version as part of a sync.

Then **report board staleness** — `python3 lib/storyboard.py status`. Prod parity just changed, so
anything pushed to Claude Design before this run no longer matches. This is the step that keeps
Claude Design honest; without it the cards drift silently and nobody notices for weeks.

```
Claude Design:
  prod-parity   stale     pushed 2026-08-05, 11 cards
  v1            current   pushed 2026-08-05, 11 cards

  needs re-pushing: prod-parity
```

Offer to re-push the stale sources — that is the `## Storyboard` flow, and re-pushing overwrites
in place. Unlike versions, a board **is** safe to refresh automatically once the user says yes:
it holds no design work, only a rendering of one.

Recording a feature:

```bash
python3 -c "
import sys; sys.path.insert(0,'lib')
import ledger
d = ledger.load()
ledger.record(d, {'lcam_id':'LCAM-2580','name':'Service accounts','surface':'list','insertion':'catalog:Device','run_date':'$TODAY'})
d['last_run'] = '$TODAY'
ledger.save(d)
"
```

## Versions

`shell/` is prod parity: only what shipped. A **version** is a fork of its template holding
design that has *not* shipped, so a specific variation can be handed to a developer without
exposing every in-progress idea.

**Versions are git branches.** `shell/<product_slug>/<name>` in the repo named by
`version_repo`. Prod parity is a *build* — the plain file at `shell/template.html` — mirrored
to `shell/<product_slug>/prod-parity` after each sync so versions can fork from it and measure
against it. The file is the source of truth; the ref is its git handle.

```bash
python3 lib/versions.py list                      # every version + how far behind it is
python3 lib/versions.py new v2 "secrets redesign" # fork prod parity
python3 lib/versions.py new v2 "redesign" ~/Downloads/Shell.html   # ...or from a Claude Design export
python3 lib/versions.py import v2 ~/Downloads/Shell.html           # bring later edits back in
python3 lib/versions.py share v2 "runs/$TODAY/share/Shell-v2.html"
python3 lib/versions.py refresh [v2]              # merge prod parity in; all versions if omitted
python3 lib/versions.py publish v2                # push it — until this, only you have it
python3 lib/versions.py publish-parity            # mirror the build to its ref
```

Invoked as `/shell-sync versions | new <name> [label] | share [name] | refresh [name]`. **On
`share` with no name, list the versions and ask which one** — do not guess, and do not default
to the newest.

Rules that are not negotiable:

- **Never check out a version branch.** The skill, the ledger and the shell can live in one
  repo, so a checkout swaps the skill's own code and its history mid-run, and fails outright
  whenever the designer has unsaved work. Every read and write goes through `gitstore`, which
  uses `git show`, a throwaway index, and `merge-tree`. If you find yourself typing
  `git checkout`, stop.
- **A merge that conflicts changes nothing.** `refresh` merges prod parity into a version. Clean
  → applied, and the version keeps its own edits. Conflict → the ref does not move and the paths
  are reported. This is the only reason refreshing every version after a sync is safe.
- **Staleness must be path-scoped.** `git rev-list --count <version>..<parity> -- <shell_path>`.
  Measured unscoped in a shared docs repo an untouched version read as **58 commits behind**,
  all of it other people's unrelated work, while the shell had not moved at all.
- **Only `template.html` is versioned.** `host.html` is 4.8 MB of fonts and identical across
  versions, so `pack_version` reuses prod parity's host.
- **Shared files carry a corner badge** (`v2 · secrets redesign — not shipped · 2 prod changes
  not in this`). Prod-parity exports carry none. Pass `badge=False` only if the user asks —
  without it, a developer opening the file months later cannot tell an idea from what is live,
  nor how stale it is.
- **Design done in Claude Design comes back as an export.** Claude Design will not return a
  file this large through the API — `get_file` caps at 256 KiB and the shell is ~373 KB, so a
  read-back returns silently truncated HTML. The path is: the user exports the prototype, then
  `new <name> <export>` or `import <name> <export>`. Always pass the export to `new` rather than
  forking and importing separately; the two-step form leaves prod parity sitting under a name
  that promises the designer's work.
- **A version is local until it is published.** `new` and every edit write to a local branch
  only. Unpublished, it is invisible to the team and backed up nowhere, and it looks *identical*
  to a shared one — so `list` states `shared` or `ONLY ON THIS MACHINE` for every version, and
  you should say which when you report one. After any change a designer wants others to see,
  offer `publish`.
- **`product_slug` namespaces the branches.** Several products share one repo; without it the
  second product to create a `v2` collides with the first.

Nothing is stored *about* a version any more — no `version.json`. Label comes from the fork
commit's subject, created date from the ref, fork point from `git merge-base`, drift from
`rev-list`. A manifest could disagree with what actually happened; git cannot.

**After a successful sync**, publish parity and then refresh every version, and report the
result per version — merged, already current, or conflicted with the files named. A conflicted
version is not an error; it means the designer and production changed the same region, and they
decide.

## Storyboard — push the shell into Claude Design

The shell is one page with every screen behind an `<sc-if>`, so a developer handed the file has
to know where to click. A **storyboard** flattens it into artboard-style cards — one per screen,
each carrying the real screenshot plus notes a developer needs — pushed into a Claude Design
project where they appear in the Design System pane.

`/shell-sync storyboard [prod-parity|<version slug>]`.

**This board is personal.** It lands in the *running user's own* Claude Design account and cannot
be shared outside their Claude team — see the handover section. Do not describe it to anyone as a
way of giving a shell to someone else.

**Prod parity and every version share ONE project**, sectioned by source, so a variation can be read against what shipped
without opening two things. Paths are namespaced by source slug and the pane group is the
source, e.g. `Prod parity` and `v2 — secrets redesign`.

Capture is agent-driven, exactly like Stage 4; `storyboard.py` never drives a browser.

```bash
TODAY=$(date +%F); D="runs/$TODAY/push"
mkdir -p "$D/shots-prod" "$D/shots-v2"
python3 lib/storyboard.py screens > "$D/screens.json"
python3 lib/bundle.py pack shell "$D/prod-parity.html"   # prod parity
python3 lib/versions.py share v2 "$D/v2.html"            # and/or a version
```

Serve over loopback, then run the tracked capture script — do not rewrite it inline:

```bash
node lib/capture.mjs http://127.0.0.1:8899 prod-parity.html "$D/screens.json" "$D/shots-prod"
```

It walks each screen's `nav` labels, **asserts the `verify` string is on the page**, and skips any
screen that fails rather than shooting whatever happened to be showing. It tries two click
strategies per screen and reports which won:

```
OK   test-editor                ancestor
OK   editor-import-picker       leaf
```

**Both strategies are necessary.** Sidebar rows carry their click handler on the row div, so
clicking the leaf span does nothing; inline affordances like the editor's `@` carry it on the leaf
span, and clicking an ancestor never reaches a child's listener. A single strategy silently drops
one whole group — that is how the import-picker screen went missing on its first board.

Then build one bundle per source:

```bash
python3 lib/storyboard.py build "$D/shots-prod" "$D/cards-prod" prod-parity
python3 lib/storyboard.py build "$D/shots-v2"   "$D/cards-v2"   v2
```

The source slug is all `build` needs — it resolves the right template (prod parity's, or the
version's), the label, and the pane group by itself. **Never hand a version's shots the
prod-parity template**: the notes would then describe what shipped while the screenshots show
the variation. Passing an explicit template path as the 5th argument overrides this; only do it
when boarding something that is neither.

Delete the 5 MB packed shells from `runs/` when done — they regenerate in seconds.

`build` records the source's template fingerprint in `boards.json`, which is what makes
`storyboard.py status` able to say a board has gone stale. It records at **build** time, not
upload time, so a failed upload still leaves an accurate description of the cards sitting on
disk — a resumed push is then correct, and a re-run is not wrongly reported as current.

### Also upload the clickable shell

The cards are screenshots. Ship the real packed shell too, so the prototype is reachable from
Claude Design rather than only from the user's disk:

```bash
python3 lib/storyboard.py interactive "$D/prod-parity.html" "$D/cards-prod" prod-parity
```

It writes `<source>-interactive.html` **into the cards directory on purpose** — `finalize_plan`
takes a single `localDir`, so keeping it there lets one plan cover both. Upload it to
`interactive/<source>-interactive.html` by adding `"interactive/*.html"` to that plan's `writes`.

**This works — the prototype opens live in Claude Design.** Confirmed by the user driving it: it
appears as its own tab (`prod-parity-interactive`), renders the real shell, and is fully
clickable.

- ✅ 5 MB uploads fine.
- ✅ The `@dsCard` marker does **not** break the shell. A comment before `<!DOCTYPE html>` leaves
  Chrome in standards mode (`compatMode === "CSS1Compat"`) with layout identical to the pixel.

**Do not read `_ds_manifest.json` as the authority on what surfaced.** It lists only the
screenshot cards and never picked up the interactive file, which led to reporting twice that the
prototype had not surfaced — while it was in fact rendering. The manifest is generated app-side
on its own schedule; absence from it proves nothing. When you need to know whether something
appears, ask the user to look.

**Use `playwright-core` from Node, not Playwright MCP, for this step.** Eleven full-page
screenshots through the MCP would pour eleven images into context for no benefit; the Node path
writes straight to disk. See the Stage 6 fallback for the launch snippet.

Then push with **DesignSync**. It needs design-system scopes on the session: if `list_projects`
comes back unauthorized or the tool is absent, **stop and tell the user to run `/login`** rather
than abandoning the run — the cards are already built on disk, so the push can be resumed from
`storyboard.json` afterwards with nothing recaptured.

1. `list_projects` → reuse a project **named** "<product_name> Shell Storyboard" if one is listed;
   otherwise `create_project`. Match on the name, never a remembered id — `list_projects` only
   returns projects the *current* user can write to, so an id from another machine or teammate
   will not be there. Never push into the user's real "Design System" project: product screens are
   not design-system components and mixing them pollutes the pane.
2. `finalize_plan` per source, with `writes: ["<source>/*.html"]`, `deletes: []` (**required,
   even when empty**) and `localDir` set to that source's cards directory. One plan per source,
   because `localDir` is single-valued.
3. `write_files` with a `localPath` per card, so the base64 never enters context. `localPath` is
   relative to `localDir` — a bare filename, not the full path.
4. `list_files` to confirm.

Re-pushing a source overwrites its cards in place, so refreshing prod parity after a sync is just
the same command again. Only `delete_files` when a source is being **renamed or retired** — and
`deletes` must be declared in `finalize_plan` up front.

**A version whose template still equals prod parity produces 11 identical cards.** Say so rather
than pushing near-duplicates that imply a difference exists.

`register_assets` is not needed — each card's first line is a `<!-- @dsCard group="..." -->`
marker and the pane builds its index from that. **If a card never appears, check that marker is
still line 1.**

### What the notes contain

Exact, and worth trusting: the nav path, the button labels, the `sc-if` gate name, and any
ledger features recorded against that surface. **Approximate:** the DesignStack component list
is signature-matched, which is why the card labels it "detected". `expand_region` also scans the
logic-block definitions of any `{{ key }}` the screen interpolates — without that, the two
screens that most obviously have a Badge and a Switch report neither, because those styles are
computed in camelCase JS rather than written as inline CSS.

## Handover — giving a shell to a developer or a PM

Someone receiving a shell has neither this skill nor the repos, so never hand them a
command. Two channels, and they answer different questions:

**1. `/design-handover` for the component-level spec.** Pack the source, then run that skill
on the packed file:

```bash
python3 lib/bundle.py pack shell "runs/$TODAY/Shell.html"      # prod parity
python3 lib/versions.py share v2 "runs/$TODAY/Shell-v2.html"   # or a version
```

It produces the developer-ready handover HTML — component inventory with live specimens,
DesignStack component names, tokens, behaviour notes, Storybook deep links. That is the
artefact a developer implements from.

**2. The storyboard project — only for people inside the user's own Claude team.**

**Never offer the storyboard as a way to hand something to someone outside the team.** Claude
Design sharing is team-scoped, and `list_projects` only returns projects the *current* user can
write to. So a storyboard is per-account: if a teammate runs `storyboard` they create *their own*
project, visible only to them, and the user's project is invisible to them. Ten people means ten
duplicate projects.

That makes the storyboard a **personal browsing surface**, not a distribution channel. It is
genuinely useful for the person who pushed it and worthless to anyone who cannot see it.

**A file is the only thing that crosses accounts.** The packed shell needs no login, no account
and no repo, and works for anyone, indefinitely. When someone asks how to get a shell to a PM, a
developer, or anyone outside the team, the answer is the file — plus the `/design-handover` output
if they need component-level detail.

Use `/design-handover` for *what to build it from*, and the packed file for *what it looks like*.
Mention the storyboard only when the recipient shares the user's Claude team.

**Say which source it came from.** A version's packed file carries the `— not shipped` badge,
but the handover HTML does not, so name the source in the message. Handing over an unreleased
variation as though it were production is the one failure that actually costs somebody work.

## If the user supplies a fresh Claude Design export

```bash
python3 lib/bundle.py unpack "<path to new export>" shell
```

That prints `identity verified` on success. Then read `ledger.json` and replay each recorded
feature onto the new `shell/template.html`, reporting any that no longer apply (for example,
the feature now ships in the export itself). Verify as in Stage 6 before handing anything back.

## Error handling summary

| Failure | Behaviour |
|---|---|
| `gh` not authenticated | Abort; nothing written |
| Atlassian MCP unavailable | Continue on PR titles; mark report degraded; be conservative about user-visibility |
| Chrome not running / not logged in | Skip all captures; mark every `MISSING` feature `NEEDS_SCREENSHOT`; still produce the gap report and ask for images at the gate |
| Feature unreachable in UI | Mark `NEEDS_SCREENSHOT`; ask the user for an image at the gate; never guess appearance |
| User supplies no screenshot | Offer to code from the Jira description, or skip. A skipped feature stays missing, so the next run re-asks it |
| No qualifying PRs in window | Report "nothing shipped"; update `last_run`; exit clean |
| Packed page renders blank | Slash escaping broke; `git checkout -- shell/template.html`; abort |
| Post-edit verification fails | Restore from git; abort; do not hand back the file |
| `version_repo` unset or not a repo | `list` returns empty rather than erroring; `new`, `share` and `refresh` fail loudly, naming the key |
| Version slug collides | Refuse; never overwrite an existing version's template |
| Version is behind prod parity | Report it; never replay into it as part of a sync |
| Storyboard screen fails to verify | Skip that screen; never screenshot whichever screen happened to be showing |
| Storyboard card never appears in the pane | The `@dsCard` marker slipped off line 1 |
| DesignSync unauthorized or absent | Cards are already built; ask the user to `/login`, then push. Never recapture |
| No writable storyboard project listed | `create_project`; an id from another machine will not be visible to this user |

## The `lib/` modules

2,180 lines across ten Python modules plus `capture.mjs`, **stdlib only** for the Python — Python 3.9.6, no pyyaml, no requests, no pytest. That
constraint is why `paths.py` hand-rolls a config reader, and it is what lets the skill run from a
plain unzip with no `pip install`.

The dividing line: **these modules hold what must give the same answer every week; you hold what
needs judgment.** Do not re-implement their work inline — a filter that drifts run to run makes it
impossible to tell a real change from a different opinion on Tuesday. Equally, do not expect them to
be right: in the 2026-08-04 run `harvest.py` reported `problems: []` while missing 39 files, because
the defect was in `config.yaml`. These buy repeatability, not correctness.

| Module | Entry point | Owns |
|---|---|---|
| `bundle.py` | `pack` / `unpack` CLI | splitting and rejoining the export |
| `harvest.py` | `harvest.py <since>` | asking GitHub what shipped |
| `index.py` | `index.py` (stdout JSON) | reading the shell's surface |
| `match.py` | `match.py <candidates.json>` | first-pass verdicts |
| `gitstore.py` | imported | git refs read and written without a checkout |
| `versions.py` | `versions.py list\|new\|share\|refresh` | design variations, as git branches |
| `storyboard.py` | `storyboard.py screens\|status\|build\|interactive` | artboard cards + clickable shell for Claude Design |
| `capture.mjs` | `node lib/capture.mjs …` | walking the shell and screenshotting each screen |
| `ledger.py` | imported | run window and what was already added |
| `paths.py` | imported | config, run directories, workspace-relative shared paths |
| `doctor.py` | `doctor.py` | what this checkout has and is missing |
| `onboard.py` | `onboard.py write …` | validating and writing a profile for another product |

**`bundle.py` — never hand-roll this.** `unpack(html)` splits the export into `host.html` (the fonts
and a placeholder) and `template.html` (the app); `pack(host, template)` rejoins them. It owns the
slash-escape invariant: the template lives inside a `<script>` tag, so every closing tag's slash must
stay escaped. Get that wrong and the packed page renders blank **with no console error at all**. The
unpack path verifies the round-trip is byte-identical and prints `identity verified`; trust that
output over your own reading of the file.

**`harvest.py` — the regexes encode losses, not taste.** `fetch_prs` shells out to `gh pr list` per
repo; `filter_prs` keeps release-branch PRs that are not noise; `to_candidates` groups them by LCAM
id. Two filters carry scars worth preserving: noise words are **word-bounded** because a bare `uts`
substring also matches "outputs", and a lone version token (`Lcam 2653 mysql2 0.5.7`) is treated as a
version bump because no keyword catches those titles. PRs from `shared_repos` additionally need an
a product signal, or half of every gap list is another team's work. It deliberately does **no** Jira
enrichment — Python has no access to the Atlassian MCP, which is why Stage 1b is yours.

**`index.py` — the label list is easy to poison.** `build(template)` returns `catalog_groups`,
`catalog_labels`, `screens`, `state_keys`, `methods` and `markup_labels`, empty-listing whatever a
given shell lacks. Two corrections are load-bearing: `<script>` blocks are stripped before parsing,
and Material Symbols names are excluded by **exact match** rather than substitution — an earlier
substitution pass corrupted labels that merely contained an icon name. Without both, `refresh` and
`close` read as product features. `_state_block` is brace-balanced because the session shell writes
its whole state object on one line.

**Name features the way the shell labels them.** `classify` scores the feature *name* against
shell labels, so a verbose name scores worse than an accurate one — `Ran with` matches exactly
while `Builds list Ran with column` scored 0.40 and came back `MISSING`. `_contained` now
escalates that case to `UNCERTAIN`, but prefer the Jira summary trimmed to what the UI actually
says over a descriptive sentence.

**`match.py` — its job is to refuse to guess.** `classify` scores a feature name against the index
with Jaccard overlap over union, plus plural folding, and returns `PRESENT`, `MISSING` or
`UNCERTAIN` with the evidence that decided it. The union denominator matters: an earlier
intersection-over-shorter-side version scored almost everything as a partial hit and produced ten
false `UNCERTAIN`s. Never treat its verdict as final — every `UNCERTAIN` is yours to adjudicate
against `shell/template.html`, and that is exactly the mechanism that caught Service Accounts being
already present.

**`versions.py` — the slug is a directory name, so validate it.** `create` forks
`shell/template.html` and writes `version.json`; `staleness` diffs ledger keys; `pack_version`
combines prod parity's host with a version's template via `bundle.pack`. `SLUG_RE` refuses
anything that could escape the branch namespace — `..`, absolute paths, leading dots — and the check
runs before any directory is made, so a bad name creates nothing. `_inject_badge` appends before
the template's last `</body>`, which sits outside `<x-dc>` and so cannot disturb the DSL; if that
anchor is ever missing it skips silently, because a missing badge is a far smaller problem than
an unpackable shell.

**`storyboard.py` — the screen map is the fragile part, so a test pins it.** `SCREENS` records,
per screen, the labels to click, the `sc-if` gate it renders under, and a `verify` string that
must be on the page once you arrive. `gate_region` is tag-balanced because these blocks nest
several deep — a regex to the first `</sc-if>` truncates most screens. `test_storyboard.py`
asserts every gate exists and every `verify` string really is inside its own region; that check
caught two wrong entries when the map was written (`configOpen` instead of `suiteCreating`, and
`Test dataset` where the shell says `Test Dataset`), either of which would have produced
confidently mislabelled cards.

**`ledger.py` — thin, but `window_start` is the load-bearing part.** `load` / `save` / `record` are
JSON plumbing over `ledger.json`, deduping on LCAM id plus lowercased name. `window_start(data,
window_days, today)` derives the harvest window from `last_run`, falling back to `default_window_days`
on a first run — this is what makes a missed week catch up instead of silently skipping. A `last_run`
in the future (clock skew, or a hand-edited ledger) clamps to today rather than producing a window
that harvests nothing. `record` is also what survives a re-export: `added_feature_keys` drives the
replay described above.

**`paths.py` — glue, and deliberately dumb.** `load_config()` parses `config.yaml` with a minimal
reader that understands flat `key: value` lines and `- item` lists **and nothing else** — do not add
nesting to the config, it will be silently mis-parsed. `run_dir(date_str)` creates
`runs/<date>/{live/manual,shell}` and returns the path.

If you are tempted to slim this down: `ledger.py` and `paths.py` are glue and would merge cleanly
into one module. `bundle.py` and `index.py` are the two where a freehand reimplementation quietly
produces a broken shell.

## Tests

```bash
cd .claude/skills/shell-sync && python3 -m unittest discover -s tests
```

209 tests, stdlib `unittest` only (no pytest, no playwright module — Python 3.9.6). One test file
per module plus `tests/fixtures/mini-bundle.html`, a tiny stand-in export so the pack/unpack
round-trip is tested without touching the real 4.8 MB shell. `test_versions.py` also swaps
`paths.SHELL_DIR` to a temp directory — without that it would read the real shell and write into
the docs-repo checkout.

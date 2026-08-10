# The sheet, and how to check it

## Shape

```
<style>  ... the whole compiled stylesheet, once ...  </style>
<style>  ... sheet furniture: block borders and labels. Not part of any component.  </style>

TIER 1 — CHROME AND LAYOUT
  [ sidebar / default        ]  ← each block boxed and labelled
  [ page-header / default    ]
  [ help-banner / default    ]

TIER 2 — THE TABLE STACK
  [ table-condensed / default     ]
  [ table-condensed / row-hovered ]
  ...

TIER 3 — CONTROLS · TIER 4 — SURFACES
  [ switch · checkbox · alert · modal · ... ]
```

One file. One stylesheet at the top, never inline styles per block — inline styles produce brittle
one-offs that don't compose when a new screen gets assembled from them.

Each block carries an HTML comment above it saying what it is and when to use it. That comment is an
instruction to whoever reads the sheet next, not documentation.

## Tiers

- **1–4** are the whole sheet: the shared DesignStack core (`core/designstack-sheet.html`) — chrome,
  tables, controls, surfaces. **The same for every product; products reuse it, they do not capture
  their own.**
- There is **no Tier 5–6 "product composites in the sheet."** A product's own composed surfaces
  (e.g. LCA's recorder row) live in the **captured shell** (`shell-scaffold.html`,
  `references/capture-shell.md`), not as sheet blocks. The sheet is primitives; the shell is product
  identity.

## The furniture is not part of the components

`.sheet-block`, `.sheet-label` and `.sheet-tier` exist so a human can read the sheet. They are not
design-stack classes. The block comments say so, and so should you if anyone asks. Don't copy them
into a wireframe.

## Scrub before you trust it

- **Real customer data** — names, emails, URLs, test/session/build names, account ids. Replace with
  realistic fake equivalents and note the swap in the manifest. Storybook fixtures are usually
  already fake (`lindsay.walton@example.com`); app captures from Tier 5–6 are not.
- **Analytics and tracking attributes** — strip them.
- **`data-*` attributes that drive styling** — leave alone. Removing them breaks the render.
- **JavaScript, event handlers, API calls** — not wanted. The sheet is about appearance.

## Then look at it

Open it and actually look:

```bash
open -a "Google Chrome" products/<slug>/app-shell/component-sheet.html
```

Go block by block:

| Symptom | What it means |
|---|---|
| Block renders unstyled | the captured `root` was too deep and lost a styling ancestor. Go up the tree |
| Block is empty | the story doesn't survive a static capture. Use a different story — a taller box won't help |
| Block shows the wrong state | the story's default isn't what you assumed |
| Menu is clipped | portal needs height. The script does this automatically; check it didn't regress |
| Blocks overlap | the containing-block `transform` on `.sheet-block` got removed |

A green `ok` from the script means "captured something". It does not mean "captured the right
thing". Only looking catches that, which is why this step is not optional.

## Size

It'll be a few hundred KB — around 160 KB of that is the stylesheet. That's fine and expected. One
big file gets read as one thing; several small ones get read unevenly.

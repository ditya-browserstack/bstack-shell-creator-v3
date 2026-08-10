# What USE mode hands to /design

This is the whole point of the skill, so get it right. Two things go out: a brief, and scaffold
files. The scaffolds matter more than the brief.

Paths below use `<slug>` = the product slug (the `products/<slug>/` folder).

## Why the scaffolds matter more

`/design`'s `solutions-wireframes.md` §4 tells it to write "simple HTML + inline CSS" using four
brand hex colours. You cannot delete that instruction, and arguing with it in a brief is unreliable —
the model may follow either one.

So don't compete with it. **Make it irrelevant.** If the wireframe file already exists, already
links the real stylesheet, and already contains the product chrome, then when `/design` reaches
"write the wireframe", the only thing left is filling in a `<main>`. An instruction about how to
author CSS has nothing to attach to.

Write the scaffolds to the same paths `/design` expects, so it opens them instead of creating new
ones: `docs/designs/wireframe-{N}-{feature-slug}.html`.

## brief.md

Keep it short. Long briefs get skimmed.

```markdown
# Design brief — <feature name>

## From the TB
- **Problem:** one or two sentences, in user terms
- **Who for:** the persona named in the TB
- **Use cases:** the list from the TB — every exploration must handle all of these
- **Out of scope:** what the TB excludes

## Components to use
Copy these from the component sheet at
`products/<slug>/app-shell/component-sheet.html`.

| Block | Use it for | Notes |
|---|---|---|
| `table-condensed` | the main list | dense rows, not the roomy Primary table |
| `tag-pill` | tags on each row | keep clickable; do not wrap in a Tooltip, it eats the click |
| `row-action-menu` | per-row actions | captured open — use that markup for the open state |

## Not in the sheet
- <anything from the manifest's missingStoryIds / failures relevant to this feature>

If you need one of these, or anything else missing, **say so — do not invent it.**

## How to build the wireframes
Scaffolds already exist at `docs/designs/wireframe-{1,2,3}-<slug>.html`. Each one already has the
stylesheet linked and the product chrome in place.

Fill in the `<!-- SOLUTION BODY -->` block. Nothing else.

- Copy markup and class names from the sheet verbatim. Do not restyle, rename or rebuild.
- No inline CSS. No new colours. No new fonts.
- This overrides the "simple HTML + inline CSS" guidance in `solutions-wireframes.md` §4.
```

That last line is worth including even though the scaffolds do the real work — it costs one line
and removes the ambiguity if someone reads both documents.

## The scaffold files

One per solution. All three identical apart from the comment naming the solution. Set the sidebar's
active item to the product's `chrome.activeNav` from `product.config.json`.

```html
<!-- WIREFRAME <N> — <solution name>
     Chrome is already here. Fill in the SOLUTION BODY block below and nothing else.
     Copy components from component-sheet.html verbatim — markup and class names.
     No inline CSS. No new colours. If a component is missing, say so; don't invent it. -->
<link rel="stylesheet" href="<abs path>/products/<slug>/app-shell/component-sheet.css">

<div class="<real wrapper classes from the sheet>">
  <!-- TOP BAR — from the sheet, tier 1. Do not modify. -->
  ...captured markup...

  <div class="<real layout classes>">
    <!-- SIDEBAR — from the sheet, tier 1. Set the active item to chrome.activeNav. -->
    ...captured markup...

    <div class="<real content classes>">
      <!-- PAGE HEADER — from the sheet, tier 1. Change only the title text and actions. -->
      ...captured markup...

      <main>
        <!-- SOLUTION BODY -->
      </main>
    </div>
  </div>
</div>
```

The stylesheet is a **separate `.css` file** (`component-sheet.css`), not the `<style>` block inlined
in the sheet, so three scaffolds share one file instead of carrying three copies of a large
stylesheet.

## Then hand over, in the same session

Invoke `/design <feature>` now, while the brief is still in context.

Do not write the files and stop. `/design`'s first step looks for brainstorm documents on disk — it
does not look for briefs. A brief left on disk for a later session would never be read, and you'd
get the generic wireframes you were trying to avoid.

## Checking it worked

After `/design` finishes, open a wireframe. Ask:

- Does it use real design-stack class names, or invented ones?
- Is there any inline `style="..."` on layout or colour? There shouldn't be.
- Do the tables use the density the product actually uses?
- Did `/design` flag anything as missing rather than quietly inventing it?

If you see invented markup, the scaffolds probably weren't found at the paths `/design` uses. Check
the slug in the filenames matches.

## Final assembly — one shell, panels, bottom-right switcher

Don't leave the reviewer with N separate wireframe tabs. Assemble the variations into **one
`explorations.html`**: the real app shell with each variation mounted as an isolated, auto-height
`panel-N.html` inside the surface-width container, switched by a floating bottom-right toggle.
Follow `references/mount-switcher.md` exactly — it carries the copy-paste slot + switcher + resize
snippets and the large-screen verification step (no crop, no chrome collision). This is the shape
every product's USE output takes.

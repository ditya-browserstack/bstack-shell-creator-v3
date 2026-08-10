# bs-design-from-tb — quickstart for designers

Turn a task brief (TB) into 1–3 high-fidelity design explorations that look like **your** product —
built from real DesignStack components, not generic AI wireframes.

There are two moments: **onboard your product once**, then **feed it TBs every day**.

---

## Install (one time)

Unzip into your Claude Code skills folder:

```bash
unzip bs-design-from-tb.skill -d ~/.claude/skills/
```

You now have `~/.claude/skills/bs-design-from-tb/`. The skill is available in Claude Code.

The shared DesignStack component library is already included (30 components) — you don't rebuild it.

---

## Step 1 — Onboard your product (once, ~30–60 min)

This teaches the skill what your product looks like. You do it once, then never again (unless your
design system changes).

You'll need: your product's **local repo**, a **live URL** of the running app, and someone
comfortable running Claude Code (pair with an engineer if that's not you — this is a v1 limitation).

1. Copy the template to your product's short name (slug):
   ```bash
   cd ~/.claude/skills/bs-design-from-tb
   cp -R products/_example products/my-product
   rm products/my-product/README.md
   ```
2. Open `products/my-product/product.config.json` and fill in the 5 `REPLACE-…` fields
   (product name, repo path, live URL, active nav label, vocabulary). See `references/config-guide.md`.
3. In Claude Code, run the skill in SETUP mode for your product. It will:
   - reuse the shared DesignStack components,
   - read your repo to learn your product's own blocks,
   - open your live app and screenshot it,
   - build your **app shell** (your component sheet + your empty screen frame).
4. Open the generated sheet in Chrome and confirm it looks like your product.

Full steps: `references/setup.md`.

---

## Step 2 — Design from a TB (every day, quick)

1. In Claude Code, invoke the skill with your product slug + a TB (a file, pasted text, or a
   Confluence link).
2. It reads the TB, picks the right components, builds wireframes, and hands to `/design`.
3. You get **1–3 explorations** that look like your product. Review and iterate.

If a component your feature needs isn't captured yet, the skill **says so and captures it** — it
never invents one. Anything it captures is added to the shared library for everyone.

---

## What's in the box

| Path | What it is |
|---|---|
| `SKILL.md` | the workflow (SETUP + USE) |
| `references/` | step-by-step guides — start with `setup.md` and `config-guide.md` |
| `core/` | the shared DesignStack component sheet (30 components) |
| `products/_example/` | template to copy for your product |
| `products/lca/` | a working example (LCA) |
| `scripts/`, `lib/` | the capture engine + config loader |

---

## Good to know

- **Onboarding is one-time; everyday use is trivial.** The expensive part (learning your product)
  happens once.
- **The component library grows for everyone.** When one product's feature needs a new component,
  capturing it once makes it available to every product.
- **v1 is for Claude Code.** Using the output inside Claude Design (paste it in) works too; deeper
  Claude Design support is planned.

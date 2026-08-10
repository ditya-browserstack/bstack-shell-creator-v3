# Is the sheet still current?

Two things can be stale: the **shared core** (DesignStack moved) and a **product sheet** (built
against an old core). Check both.

## The check

Compare the product sheet's manifest against the shared core, and the core against the live
design-stack package.

```bash
SKILL=~/projects/lcnc-workspace/lcnc-backend/workspace/skills/bs-design-from-tb
python3 -c "
import json,os
core=json.load(open(os.path.expanduser('$SKILL/core/core-manifest.json')))
prod=json.load(open(os.path.expanduser('$SKILL/products/<slug>/app-shell/sheet-manifest.json')))
p=json.load(open(os.path.expanduser('~/projects/lcnc-workspace/frontend/packages/design-stack/package.json')))
print('product sheet built against:', prod['designStackVersion'])
print('shared core built against:  ', core['designStackVersion'])
print('design-stack now:           ', p['version'])
print('CORE DRIFT'    if core['designStackVersion']!=p['version'] else 'core current')
print('PRODUCT DRIFT' if prod['designStackVersion']!=core['designStackVersion'] else 'product current')
"
```

## What to do about drift

| Situation | Do |
|---|---|
| Versions match | carry on |
| Patch bump (9.8.0 → 9.8.1) | say so in one line, carry on. Patches rarely change markup |
| Minor bump (9.8.0 → 9.9.0) | say so and offer to rebuild. New components may exist; classes may have moved |
| Major bump (9.x → 10.x) | recommend rebuilding. Assume markup changed |
| No manifest at all | offer SETUP. Do not proceed |

Core drift is fixed once for the whole org: re-run `capture-storybook.mjs --core`. Product drift is
fixed by re-running that product's SETUP against the refreshed core.

Always **say** what you found. Never silently use a stale sheet.

## Cheap partial check

A version match doesn't prove every story still exists. With Storybook running:

```bash
cd ~/projects/lcnc-workspace/frontend/packages/design-stack
node <skill>/scripts/capture-storybook.mjs --core --dry-run
```

Seconds, and it tells you whether the tier map still resolves. Exits non-zero if anything is missing.

## Also read the manifest's gaps

Even a current sheet has holes. Before designing, check the product's `sheet-manifest.json`:

- `missingStoryIds` — tier-map entries whose story is gone
- `failures` — blocks that errored during capture
- `notCapturedTiers` — tiers never attempted

Surface anything relevant to the feature **before** design starts. A gap named up front is a
decision; the same gap discovered mid-design becomes an invented component.

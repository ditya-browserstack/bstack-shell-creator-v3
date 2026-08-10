# Onboard a new product (Task 6 quickstart)

This `_example` folder is a template, not a real product. To onboard a product:

1. Copy this folder to a real slug:

   ```bash
   cd ~/projects/lcnc-workspace/lcnc-backend/workspace/skills/bs-design-from-tb
   cp -R products/_example products/appauto      # pick your slug
   rm products/appauto/README.md
   ```

2. Edit `products/appauto/product.config.json` — fill the `REPLACE-…` fields
   (`repoPath`, `liveUrl`, `chrome.activeNav`, `vocabulary`). See `references/config-guide.md`.

3. Validate:

   ```bash
   node -e "import('./lib/config.mjs').then(m=>{m.loadProductConfig('appauto',{skillRoot:process.cwd()});console.log('config ok')})"
   ```

4. Run SETUP: follow `references/setup.md` end to end. It produces
   `products/appauto/app-shell/{component-sheet.html,component-sheet.css,shell-scaffold.html,sheet-manifest.json}`.

5. Open the sheet + scaffold in Chrome and verify (a green "captured" ≠ the right capture).

6. Run USE: give the skill a real TB for that product → 1–3 explorations via `/design`.

Requirements you must have on hand: the product's **local repo path** and a **reachable, logged-in
live URL**. Those are the only things this template can't fill for you.

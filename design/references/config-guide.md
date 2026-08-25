# Filling a product.config.json

One file per product, at `products/<slug>/product.config.json`. Validated by `lib/config.mjs`
against `references/product-config.schema.json`.

```json
{
  "product": "App Automate",
  "designSystem": "designstack",
  "repoPath": "~/projects/app-automate",
  "storybookUrl": "http://localhost:6006",
  "liveUrl": "https://app-automate.browserstack.com/dashboard",
  "chrome": { "topbar": ".topbar", "sidebar": "nav.sidebar", "activeNav": "Automate" },
  "vocabulary": ["build", "session", "capability"]
}
```

## Fields

| Field | Required | What it is |
|---|---|---|
| `product` | yes | Human name, shown in the sheet header and briefs. |
| `designSystem` | yes | `"designstack"` → uses the shared `core/`. `"custom"` → uses `customSource`. |
| `repoPath` | yes | Local path to the product's repo. SETUP reads it to learn how the product composes blocks. |
| `storybookUrl` | no | DesignStack Storybook (default `http://localhost:6006`). For `custom`, the product's own Storybook. |
| `liveUrl` | no | A reachable URL of the running product. SETUP screenshots it for layout truth. |
| `customSource` | only if `custom` | Path to the product's own tier map (used instead of the shared core). |
| `chrome.activeNav` | yes | The sidebar item to mark active in scaffolds (e.g. `"Automate"`, `"Tests"`). |
| `chrome.topbar` / `chrome.sidebar` | no | CSS selectors for the top bar / sidebar on the live app, if you capture chrome from there. |
| `vocabulary` | no | The product's nouns (`build`, `session`…). Keeps briefs and copy in the product's language. |

## Finding the chrome selectors

Don't read code for these. Point the browser tools at `liveUrl`, open the page, and inspect the
top bar and sidebar to get their selectors. Fill `chrome.topbar` / `chrome.sidebar` from what you see.

## Validate before continuing

```bash
cd ~/.claude/skills/bstack-shell-creator-v3/design   # the installed skill's design/ folder
node -e "import('./lib/config.mjs').then(m=>{m.loadProductConfig('<slug>',{skillRoot:process.cwd()});console.log('config ok')})"
```

A validation error prints exactly which field is wrong. Fix it before running SETUP.

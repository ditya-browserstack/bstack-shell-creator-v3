# Changelog — bstack-shell-creator-v2

Newest first. The first line under each version is shown in the update prompt, so keep it a clear one-liner.

## 3.1.0
Product-agnostic: no LCA hardcoded in the scripts. The assembler's chrome-prune now reads THIS product's `chrome.topbar`/`chrome.sidebar` from its `product.config.json` (plus DesignStack-generic patterns), and Playwright resolves via `PLAYWRIGHT_CORE` env / npx cache / cwd instead of an LCA path. Any designer's own BrowserStack product works from their own config. Verified: LCA reference stays fully green under the config-driven prune.

## 3.0.0
v3 milestone. The complete pipeline: ask-for-source multi-screen capture (live/localhost/repo) + state-gated capture (modals/loaders/recorder), self-check fidelity gate (offline render, broken-asset + signature-diff), raw-work/scrub-at-share PII gating, scalable responsive normalization, asset self-containment, sync + Claude Design handoff, and git-based auto-update.

## 1.1.0
State-gated capture (modals/drawers/loaders/the recorder setup, via freeze-then-snapshot) + a shell-fidelity pass: offline self-containment (inline images/fonts), broken-asset + capture-signature gap detection in self-check, and scrub/gate consistency fixes. Passed a full pre-release audit (17/17 unit tests, all references present, reference example self-contained + gate-clean).

## 1.0.0
First versioned release. Multi-source capture (ask live/localhost/repo), raw-work + scrub-at-share, self-check fidelity gate (offline render, broken-asset + signature-diff gap detection), scalable responsive normalization, asset self-containment (inline images/fonts), sync handoff, and git-based auto-update.

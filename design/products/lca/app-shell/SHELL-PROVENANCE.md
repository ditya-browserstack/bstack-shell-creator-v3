# LCA app shell — provenance

`shell-scaffold.html` is the **real LCA app shell**, captured from the live product.

- **Source:** `https://low-code.browserstack.com/` (Tests surface), logged-in session, captured 2026-08-10.
- **Method:** live DOM capture via browser automation — real compiled markup + the app's own compiled stylesheet (284 KB), assembled into one self-contained file that opens via `file://`.
- **Parts:** top bar (`#lcnc-bstack-header`) · left sidebar nav · the recorder start row (URL · device · resolution · Advanced options) · an empty `<main class="lca-main-slot">` marked `SOLUTION BODY`.
- **Scrub:** customer data replaced with fakes — test URL `flipkart.com` → `example.com`; the test-list table (real names/emails) was deliberately **not** captured (chrome + recorder row only). Emails → `user@example.com`, project name → `Sample Project`.
- **Fidelity:** this is the genuine EXISTING FLOW to diff a design against — real chrome, not reconstructed. The "Block all permissions" feature does not exist in the app yet (it is this TB's future work), so Advanced options shows today's state.

To refresh: re-capture from the live app when the shell changes (design-stack bump or nav change).
`shell-preview.png` is a render check of this file.

# `_example` — placeholder product

This folder shows the **shape** of a product entry. A real product lives at
`design/products/<your-slug>/` and is created during SETUP:

1. Fill `product.config.json` for your product (name, `liveUrl`, and the `chrome.*` selectors you find
   by inspecting your own live app). The values here are generic examples, not a real product.
2. Run SETUP (`references/setup.md`) — it asks your source (live / localhost / repo), captures your
   screens into `app-shell/`, self-checks fidelity, and scrubs before sharing.

> **Note:** the fully-worked internal reference (a real BrowserStack product's captured shell) is **not
> shipped in this public repo** — it would expose internal product UI. Ask the maintainer for the
> `.skill` bundle if you want to see a complete, populated example.

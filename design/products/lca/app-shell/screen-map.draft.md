# LCA (Low Code Automation) — storyboard.SCREENS draft (for shell-sync)

Auto-drafted from the captured shell's sidebar (11 nav items).
Paste into `lib/storyboard.py` `SCREENS` in your shell-sync install, then **confirm each**:
`nav` (click labels) is pre-filled; you must set `gate` (the `<sc-if>` state key the screen
shows behind) and `verify` (text that proves you landed). shell-sync's own check catches wrong ones.

> NOTE: shell-sync boards MULTIPLE screens gated by `<sc-if>`. This skill's capture is currently a
> SINGLE surface, so only the active screen truly exists in the shell today; the rest are nav stubs.
> Capture the other screens (re-run capture-shell.md per screen) to make them real boards.

```python
SCREENS = [
    {
        "slug": "tests",  # ← the captured surface (real today)
        "title": "Tests",
        "group": "Screens",
        "nav": ["Tests"],
        "gate": "<TODO: sc-if state key>",
        "verify": "<TODO: text on this screen>",
    },
    {
        "slug": "test-suites",
        "title": "Test suites",
        "group": "Screens",
        "nav": ["Test suites"],
        "gate": "<TODO: sc-if state key>",
        "verify": "<TODO: text on this screen>",
    },
    {
        "slug": "builds",
        "title": "Builds",
        "group": "Screens",
        "nav": ["Builds"],
        "gate": "<TODO: sc-if state key>",
        "verify": "<TODO: text on this screen>",
    },
    {
        "slug": "testing-trendsbeta",
        "title": "Testing trendsBeta",
        "group": "Screens",
        "nav": ["Testing trendsBeta"],
        "gate": "<TODO: sc-if state key>",
        "verify": "<TODO: text on this screen>",
    },
    {
        "slug": "modules",
        "title": "Modules",
        "group": "Screens",
        "nav": ["Modules"],
        "gate": "<TODO: sc-if state key>",
        "verify": "<TODO: text on this screen>",
    },
    {
        "slug": "data-configuration",
        "title": "Data configuration",
        "group": "Screens",
        "nav": ["Data configuration"],
        "gate": "<TODO: sc-if state key>",
        "verify": "<TODO: text on this screen>",
    },
    {
        "slug": "settings",
        "title": "Settings",
        "group": "Screens",
        "nav": ["Settings"],
        "gate": "<TODO: sc-if state key>",
        "verify": "<TODO: text on this screen>",
    },
    {
        "slug": "integrations",
        "title": "Integrations",
        "group": "Screens",
        "nav": ["Integrations"],
        "gate": "<TODO: sc-if state key>",
        "verify": "<TODO: text on this screen>",
    },
    {
        "slug": "give-feedback",
        "title": "Give feedback",
        "group": "Screens",
        "nav": ["Give feedback"],
        "gate": "<TODO: sc-if state key>",
        "verify": "<TODO: text on this screen>",
    },
    {
        "slug": "view-documentation",
        "title": "View documentation",
        "group": "Screens",
        "nav": ["View documentation"],
        "gate": "<TODO: sc-if state key>",
        "verify": "<TODO: text on this screen>",
    },
    {
        "slug": "download-desktop-app",
        "title": "Download Desktop App",
        "group": "Screens",
        "nav": ["Download Desktop App"],
        "gate": "<TODO: sc-if state key>",
        "verify": "<TODO: text on this screen>",
    },
]
```

#!/usr/bin/env python3
"""Turn a shell into an artboard-style storyboard for Claude Design.

The shell is a single page whose screens are hidden behind `<sc-if>` gates, so a
developer handed the file has to know where to click. A storyboard flattens it:
one card per screen, each carrying the real screenshot plus notes about what a
developer needs to know for that screen.

Cards are preview HTML files. The Design System pane indexes them by a first-line
`<!-- @dsCard group="..." -->` marker, so that comment must stay on line 1.

Division of labour, matching how Stage 4 already works: **this module never drives
a browser.** It publishes the screen map for the agent to walk with Playwright, and
turns the resulting PNGs into cards. Python here is stdlib-only.

Screenshots are embedded as data URIs rather than uploaded as sibling files. A card
is then self-contained, with no dependence on how the pane resolves relative paths.
"""
import base64
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

# Every screen worth boarding, in the order a designer would walk the product.
#
# `nav` is the sequence of visible labels to click from a freshly loaded shell.
# `gate` is the sc-if state key that must be showing once you arrive -- the agent
# asserts on it so a mis-click is caught rather than silently screenshotting the
# wrong screen. `verify` is text that must appear on the rendered screen.
SCREENS = [
    {
        "slug": "tests",
        "title": "Tests",
        "group": "Screens",
        "nav": ["Tests"],
        "gate": "homeList",
        "verify": "Tests",
    },
    {
        # The most-used screen in the product, and the one carrying the newest
        # work (secret lock chip, import picker). It was missing from this map
        # until 2026-08-05, which meant a board could not show either.
        "slug": "test-editor",
        "title": "Test editor",
        "group": "Screens",
        "nav": ["Start test"],
        "gate": "onEditor",
        "verify": "Complete test",
    },
    {
        "slug": "editor-import-picker",
        "title": "Editor — import picker (Secrets)",
        "group": "Screens",
        "nav": ["Start test", "@"],
        "gate": "atPickerVis",
        "verify": "Create new secret",
    },
    {
        "slug": "test-suites",
        "title": "Test suites",
        "group": "Screens",
        "nav": ["Test suites"],
        "gate": "suitesOpen",
        "verify": "Create test suite",
    },
    {
        "slug": "suite-config",
        "title": "Create / edit test suite",
        "group": "Screens",
        "nav": ["Test suites", "Create test suite"],
        "gate": "suiteCreating",
        "verify": "Enable local testing",
    },
    {
        "slug": "builds",
        "title": "Builds",
        "group": "Screens",
        "nav": ["Builds"],
        "gate": "buildsListOpen",
        "verify": "Search by build name",
    },
    {
        "slug": "modules",
        "title": "Modules",
        "group": "Screens",
        "nav": ["Modules"],
        "gate": "modulesOpen",
        "verify": "Modules",
    },
    {
        "slug": "media-library",
        "title": "Media Library",
        "group": "Screens",
        "nav": ["Media Library"],
        "gate": "mediaOpen",
        "verify": "Media Library",
    },
    {
        "slug": "global-variables",
        "title": "Global variables",
        "group": "Data configuration",
        "nav": ["Global variables"],
        "gate": "gvarsOpen",
        "verify": "Global variables",
    },
    {
        "slug": "secrets",
        "title": "Secrets",
        "group": "Data configuration",
        "nav": ["Secrets"],
        "gate": "secretsOpen",
        "verify": "Secrets",
    },
    {
        "slug": "test-dataset",
        "title": "Test dataset",
        "group": "Data configuration",
        "nav": ["Test dataset"],
        "gate": "dsListOpen",
        "verify": "Test Dataset",
    },
    {
        "slug": "database",
        "title": "Database",
        "group": "Data configuration",
        "nav": ["Database"],
        "gate": "dbPageOpen",
        "verify": "Database",
    },
    {
        "slug": "settings-service-account",
        "title": "Settings — Service account",
        "group": "Screens",
        "nav": ["Settings"],
        "gate": "settingsOpen",
        "verify": "Service account",
    },
]

# Heuristic component signatures. Deliberately conservative: a false "present" in a
# dev note is worse than a missing one, because a developer may go looking for a
# component that is not there. Each pattern is a shape the shell only uses for that
# DesignStack component.
COMPONENT_SIGNATURES = (
    ("Table", re.compile(r"letter-spacing:0\.06em")),
    # Pills appear with the properties in any order, and half of them are computed
    # in the logic block in camelCase, so match the radius plus a pill-ish
    # neighbouring property rather than one fixed declaration order.
    ("Badge", re.compile(
        r"border-radius:9999px;(?:padding|background|font)|"
        r"(?:padding|background):[^;\"]*;border-radius:9999px|"
        r"borderRadius: 9999, padding"
    )),
    ("Switch", re.compile(
        r"width:5[02]px;height:(?:28|30)px;border-radius:9999px|"
        r"width: 4[48], height: 2[48], borderRadius: 9999"
    )),
    ("Tooltip", re.compile(r"background:#1F2937")),
    ("Hyperlink", re.compile(r"color:#2563EB;text-decoration")),
    ("Modal / drawer", re.compile(r"position:fixed;inset:0")),
    ("SelectMenu", re.compile(r"unfold_more")),
    ("Empty state", re.compile(r"No .{3,40} yet|empty", re.I)),
)

HEADING_RE = re.compile(r"<h1[^>]*>([^<{]{2,44})</h1>")
BUTTON_RE = re.compile(r">([A-Z][A-Za-z ]{3,26})</button>")

# The bundler writes <title>Bundled Page</title> into the host. Left alone, that
# becomes the card's name in the Design System pane, so every clickable prototype
# would be called "Bundled Page".
TITLE_RE = re.compile(r"<title>[^<]*</title>", re.I)

INTERACTIVE_NAME = "%s-interactive.html"

SC_IF_OPEN_FMT = '<sc-if value="{{ %s }}"'


def gate_region(template, gate):
    """Return the markup inside the `<sc-if>` for one state key, or ''.

    Tag-balanced rather than regex-to-first-close: sc-if blocks nest several deep in
    this shell, so a naive match ends the region at the first inner close and the
    component scan then misses most of the screen.
    """
    start = template.find(SC_IF_OPEN_FMT % gate)
    if start == -1:
        return ""
    depth = 0
    index = start
    while index < len(template):
        next_open = template.find("<sc-if", index + 1)
        next_close = template.find("</sc-if>", index + 1)
        if next_close == -1:
            return template[start:]
        if next_open != -1 and next_open < next_close:
            depth += 1
            index = next_open
            continue
        if depth == 0:
            return template[start:next_close]
        depth -= 1
        index = next_close
    return template[start:]


INTERP_RE = re.compile(r"\{\{ ([a-zA-Z][a-zA-Z0-9_.]*) \}\}")


def expand_region(template, region):
    """Append the logic-block definitions of any keys the region interpolates.

    Half of this shell's styling is computed, not inline: the service-account badge
    is `style="{{ saTagStyle }}"` with the colours in a JS object. Scanning only the
    markup therefore reports no Badge and no Switch on the two screens that most
    obviously have both -- a dev note that actively misleads. Pulling in each
    referenced key's definition closes that gap.
    """
    chunks = [region]
    for key in sorted(set(INTERP_RE.findall(region))):
        leaf = key.split(".")[-1]
        for match in re.finditer(r"\b%s: " % re.escape(leaf), template):
            chunks.append(template[match.start():match.start() + 400])
    return "\n".join(chunks)


def components_in(region):
    """DesignStack components detectable in a region, in signature order."""
    return [name for name, pattern in COMPONENT_SIGNATURES if pattern.search(region)]


def features_for(screen, ledger_data):
    """Ledger features recorded against this screen's surface.

    Matches the ledger's free-text `surface` against the screen slug from either
    direction, because surfaces were recorded by hand ("builds", "suite-config")
    and will not always equal a slug exactly.
    """
    slug = screen["slug"]
    found = []
    for feature in ledger_data.get("features", []):
        surface = (feature.get("surface") or "").strip().lower()
        if not surface:
            continue
        if surface in slug or slug in surface:
            found.append(feature)
    return found


def actions_in(region):
    """Button labels on this screen, deduped in document order.

    Exact, unlike the component signatures -- these are literal strings a developer
    can search the template for.
    """
    seen = []
    for label in BUTTON_RE.findall(region):
        cleaned = label.strip()
        if cleaned and cleaned not in seen:
            seen.append(cleaned)
    return seen


def heading_in(region):
    found = HEADING_RE.findall(region)
    return found[0].strip() if found else ""


def notes_for(screen, template, ledger_data):
    """Everything the card should tell a developer about this screen."""
    region = gate_region(template, screen["gate"])
    return {
        "components": components_in(expand_region(template, region)),
        "actions": actions_in(region),
        "heading": heading_in(region),
        "features": [f.get("name", "") for f in features_for(screen, ledger_data)],
        "gate": screen["gate"],
        "nav": " → ".join(screen["nav"]),
        "measured": bool(region),
    }


def _esc(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _data_uri(png_path):
    encoded = base64.b64encode(Path(png_path).read_bytes()).decode("ascii")
    return "data:image/png;base64," + encoded


def card_html(screen, png_path, notes, source_label, group=None):
    """One preview card: the screenshot, then the dev notes beneath it.

    The `@dsCard` comment MUST be the first line -- the pane builds its index from
    it, and a card whose marker has slipped to line 2 simply never appears.
    """
    chips = "".join(
        '<span class="chip">%s</span>' % _esc(name) for name in notes["components"]
    ) or '<span class="chip chip-none">none detected</span>'

    if notes["features"]:
        shipped = "".join("<li>%s</li>" % _esc(name) for name in notes["features"])
        shipped_block = (
            '<div class="block"><h3>Shipped features on this screen</h3>'
            "<ul>%s</ul></div>" % shipped
        )
    else:
        shipped_block = ""

    if notes["actions"]:
        actions_block = (
            '<div class="block"><h3>Primary actions</h3><div class="chips">%s</div></div>'
            % "".join('<span class="chip">%s</span>' % _esc(a) for a in notes["actions"])
        )
    else:
        actions_block = ""

    return """<!-- @dsCard group="%(group)s" -->
<!doctype html>
<meta charset="utf-8">
<title>%(title)s</title>
<style>
  :root { color-scheme: light dark; }
  body {
    margin: 0; padding: 20px;
    font: 14px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif;
    background: #F5F7F9; color: #131A21;
  }
  @media (prefers-color-scheme: dark) {
    body { background: #0E1216; color: #E7ECF1; }
    .shot, .notes { background: #161C22; border-color: #2A333D; }
    .chip { background: #1E262E; border-color: #3D4954; color: #AEBAC5; }
    .meta { color: #8794A0; }
    h3 { color: #AEBAC5; }
  }
  header { display: flex; flex-wrap: wrap; align-items: baseline; gap: 10px; margin-bottom: 14px; }
  h1 { margin: 0; font-size: 20px; letter-spacing: -.01em; }
  .meta { font: 12px ui-monospace, SFMono-Regular, Menlo, monospace; color: #6B7885; }
  .shot {
    background: #FFFFFF; border: 1px solid #D8DEE5; border-radius: 8px;
    overflow: hidden; box-shadow: 0 1px 2px rgba(19,26,33,.06), 0 6px 18px rgba(19,26,33,.05);
  }
  .shot img { display: block; width: 100%%; height: auto; }
  .notes {
    margin-top: 16px; background: #FFFFFF; border: 1px solid #D8DEE5;
    border-radius: 8px; padding: 16px 18px;
    display: flex; flex-direction: column; gap: 14px;
  }
  h3 {
    margin: 0 0 6px; font: 600 11px ui-monospace, SFMono-Regular, Menlo, monospace;
    letter-spacing: .1em; text-transform: uppercase; color: #48545F;
  }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; }
  .chip {
    font: 500 12px system-ui, sans-serif; background: #EAEFF3;
    border: 1px solid #D8DEE5; border-radius: 9999px; padding: 3px 10px; color: #48545F;
  }
  .chip-none { font-style: italic; }
  ul { margin: 0; padding-left: 18px; }
  li { margin: 2px 0; }
  code {
    font: 12px ui-monospace, SFMono-Regular, Menlo, monospace;
    background: #EAEFF3; border-radius: 3px; padding: .1em .35em;
  }
  @media (prefers-color-scheme: dark) { code { background: #1E262E; } }
</style>
<header>
  <h1>%(title)s</h1>
  <span class="meta">%(source)s</span>
</header>
<div class="shot"><img src="%(uri)s" alt="%(title)s"></div>
<div class="notes">
  <div class="block"><h3>How to reach it</h3><div>%(nav)s</div></div>
  %(actions)s
  <div class="block"><h3>DesignStack components &mdash; detected</h3><div class="chips">%(chips)s</div></div>
  %(shipped)s
  <div class="block"><h3>In the shell source</h3>
    <div>Rendered under <code>&lt;sc-if value="{{ %(gate)s }}"&gt;</code> in
    <code>template.html</code>.</div></div>
</div>
""" % {
        "group": _esc(group or screen["group"]),
        "title": _esc(screen["title"]),
        "source": _esc(source_label),
        "uri": _data_uri(png_path),
        "nav": _esc(notes["nav"]),
        "chips": chips,
        "actions": actions_block,
        "shipped": shipped_block,
        "gate": _esc(notes["gate"]),
    }


def interactive_html(packed, group, title):
    """Turn a packed shell into a card the Design System pane will index.

    Two edits, both to the packed artifact only -- never to shell/host.html:

    1. Prepend the `@dsCard` marker. Verified safe: a comment before
       `<!DOCTYPE html>` does NOT trigger quirks mode in Chrome (compatMode stays
       CSS1Compat) and the rendered layout is identical to the pixel. The HTML5
       parser skips comments before the doctype.
    2. Rewrite the title, so the card is not called "Bundled Page".
    """
    marked = '<!-- @dsCard group="%s" -->\n' % _esc(group) + packed
    return TITLE_RE.sub("<title>%s</title>" % _esc(title), marked, count=1)


def write_interactive(packed_path, out_dir, source, group, title):
    """Write the marked interactive shell *into the cards directory*.

    Deliberately alongside the cards rather than in its own tree: `finalize_plan`
    takes a single `localDir`, so keeping both here lets one plan cover the cards
    and the prototype instead of needing two round trips.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    target = out / (INTERACTIVE_NAME % source)
    target.write_text(
        interactive_html(
            Path(packed_path).read_text(encoding="utf-8"), group, title
        ),
        encoding="utf-8",
    )
    return target


def build_bundle(
    out_dir, shots, template, ledger_data, source_label, prefix="shell", group=None
):
    """Write one card per captured screen. Returns the upload plan.

    Screens with no screenshot are skipped rather than carded with a placeholder --
    an empty artboard reads as "this screen looks blank", which is worse than the
    screen being absent.

    `prefix` namespaces the project paths and `group` overrides the pane section, so
    prod parity and every version can live in ONE project without colliding. Grouping
    by source rather than by screen kind is deliberate: the reason to open this
    project is to compare a variation against what shipped, so the sections that
    matter are "Prod parity" and "v2", not "Screens" and "Data configuration".
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for screen in SCREENS:
        png = shots.get(screen["slug"])
        if not png or not Path(png).is_file():
            continue
        notes = notes_for(screen, template, ledger_data)
        target = out / ("%s-%s.html" % (prefix, screen["slug"]))
        target.write_text(
            card_html(screen, png, notes, source_label, group=group), encoding="utf-8"
        )
        written.append(
            {
                "path": "%s/%s" % (prefix, target.name),
                "local": target.name,
                "name": screen["title"],
                "group": group or screen["group"],
                "components": notes["components"],
                "features": notes["features"],
            }
        )
    (out / "storyboard.json").write_text(
        json.dumps(
            {"source": source_label, "prefix": prefix, "cards": written},
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return written


# ---------------------------------------------------------------------------
# Board state: what has been pushed to Claude Design, and whether it is current.
#
# Without this, a weekly sync edits the shell and the cards in Claude Design go
# quietly stale -- the same silent-drift problem the version staleness report
# exists to prevent. Fingerprinting the template at push time catches ANY edit,
# including hand edits to a version that never went through a sync.
# ---------------------------------------------------------------------------

BOARDS_NAME = "boards.json"


def _boards_path():
    import paths
    return paths.SKILL_DIR / BOARDS_NAME


def fingerprint(template_text):
    """Short content hash of a template. Content, not mtime: a fork is
    byte-identical to its source, and touching a file is not a design change."""
    return hashlib.sha256(template_text.encode("utf-8")).hexdigest()[:16]


def template_for(source, config=None):
    """Resolve the template a source slug refers to.

    Prod parity is a file on disk. A version lives on a git ref and is never
    checked out, so it is materialised into a temp file here rather than having a
    path of its own -- callers only ever read it.
    """
    import paths
    if source == "prod-parity":
        return paths.SHELL_DIR / "template.html"
    import tempfile

    import versions
    content = versions.read_template(source, config)
    target = Path(tempfile.mkdtemp(prefix="shell-sync-%s-" % source)) / "template.html"
    target.write_text(content, encoding="utf-8")
    return target


def load_boards(path=None):
    target = Path(path) if path is not None else _boards_path()
    if not target.is_file():
        return {"version": 1, "boards": {}}
    data = json.loads(target.read_text(encoding="utf-8"))
    data.setdefault("boards", {})
    return data


def save_boards(data, path=None):
    target = Path(path) if path is not None else _boards_path()
    target.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def record_board(data, source, template_text, cards, today=None):
    """Note that `source` was pushed, and what it looked like at the time."""
    data.setdefault("boards", {})[source] = {
        "pushed": (today or date.today()).isoformat(),
        "fingerprint": fingerprint(template_text),
        "cards": cards,
    }
    return data["boards"][source]


def board_status(data, config=None):
    """Per boarded source: whether Claude Design still matches the template.

    `state` is one of current / stale / missing -- missing meaning the source was
    boarded once and its template has since been deleted, which is worth saying
    out loud rather than silently reporting 'stale'.
    """
    rows = []
    for source, entry in sorted(data.get("boards", {}).items()):
        try:
            path = template_for(source, config)
        except Exception:
            rows.append({"source": source, "state": "missing", **entry})
            continue
        if not path.is_file():
            rows.append({"source": source, "state": "missing", **entry})
            continue
        now = fingerprint(path.read_text(encoding="utf-8"))
        rows.append({
            "source": source,
            "state": "current" if now == entry.get("fingerprint") else "stale",
            **entry,
        })
    return rows


def _cmd_status():
    rows = board_status(load_boards())
    if not rows:
        print("nothing boarded to Claude Design yet")
        return
    for row in rows:
        print("%-14s %-8s pushed %s  %d cards" % (
            row["source"], row["state"], row.get("pushed", "?"), row.get("cards", 0)
        ))
    stale = [r["source"] for r in rows if r["state"] != "current"]
    if stale:
        print("\nneeds re-pushing: %s" % ", ".join(stale))


def _product_name():
    """What to call the product on a board card. Falls back if config is absent."""
    import paths

    try:
        return paths.load_config().get("product_name") or "Product"
    except (OSError, ValueError):
        return "Product"


def source_labels(source):
    """(card label, pane group, interactive card title) for one source slug.

    Shared by build and interactive so a source can never end up with cards in one
    group and its prototype in another.
    """
    product = _product_name()
    if source == "prod-parity":
        return (
            "prod parity",
            "Prod parity",
            "%s shell — prod parity (clickable)" % product,
        )
    import versions

    manifest = versions.read_manifest(source)
    suffix = (" — %s" % manifest["label"]) if manifest.get("label") else ""
    return (
        "%s%s — not shipped" % (source, suffix),
        "%s%s" % (source, suffix),
        "%s shell — %s%s (clickable, not shipped)" % (product, source, suffix),
    )


def _cmd_screens():
    """Emit the screen map for the capture step to walk."""
    print(json.dumps(SCREENS, indent=2))


def main(argv):
    usage = (
        "usage: storyboard.py screens\n"
        "       storyboard.py status\n"
        "       storyboard.py build <shots_dir> <out_dir> <source_slug> [template]\n"
        "       storyboard.py interactive <packed.html> <cards_dir> <source_slug>\n"
        "\n"
        "  source_slug  'prod-parity' or a version slug. Namespaces the project\n"
        "               paths and names the section in the Design System pane, so\n"
        "               several shells can share one project."
    )
    if len(argv) < 2:
        print(usage, file=sys.stderr)
        return 2
    if argv[1] == "screens" and len(argv) == 2:
        _cmd_screens()
        return 0
    if argv[1] == "status" and len(argv) == 2:
        _cmd_status()
        return 0
    if argv[1] == "build" and len(argv) in (5, 6):
        import ledger

        shots_dir = Path(argv[2])
        shots = {
            screen["slug"]: shots_dir / ("%s.png" % screen["slug"])
            for screen in SCREENS
            if (shots_dir / ("%s.png" % screen["slug"])).is_file()
        }
        source = argv[4]
        label, group, _ = source_labels(source)
        template_path = Path(argv[5]) if len(argv) == 6 else template_for(source)
        template_text = template_path.read_text(encoding="utf-8")
        written = build_bundle(
            argv[3], shots, template_text, ledger.load(), label,
            prefix=source, group=group,
        )
        print("built %d cards in %s  (group %r)" % (len(written), argv[3], group))
        for card in written:
            print("  %-34s %s" % (card["name"], ", ".join(card["components"]) or "-"))
        # Recorded at build time, not upload time: if the upload fails the cards on
        # disk are still what this fingerprint describes, so a resumed push is
        # correct and a re-run is not silently marked current.
        boards = load_boards()
        record_board(boards, source, template_text, len(written))
        save_boards(boards)
        print("recorded board state for %r" % source)
        return 0
    if argv[1] == "interactive" and len(argv) == 5:
        source = argv[4]
        _, group, title = source_labels(source)
        target = write_interactive(argv[2], argv[3], source, group, title)
        size = target.stat().st_size / 1e6
        print("wrote %s (%.1f MB, group %r)" % (target.name, size, group))
        print("  upload to: interactive/%s" % target.name)
        return 0
    print(usage, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))

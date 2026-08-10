#!/usr/bin/env python3
"""Build the shareable copy of this skill: the tool, without anybody's content.

The skill lives inside a team's harness repo, and that repo is private. Anyone
outside it cannot clone, so "go get it from git" is not a way to share this. A
zip is — it needs no account, no access request, and no argument with an admin.

What makes that safe is that the tool and the content are already separate
things sitting in the same folder. `lib/` and `tests/` know nothing about any
product. `shell/`, `config.yaml`, `ledger/` and `profiles/` are one team's
answers, their 5 MB shell, and their record of what shipped. Shipping the first
group and dropping the second turns a 5 MB team install into a ~300 KB tool that
onboards to whatever product the recipient has.

The allow-list is deliberate. A deny-list would ship each new content file until
somebody noticed, and the thing that leaks is exactly the thing nobody thought to
exclude.
"""
import io
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import paths  # noqa: E402

# Shipped verbatim. Everything not matched here stays behind.
INCLUDE_FILES = ("SKILL.md", "adopt.html")
INCLUDE_TREES = ("lib", "tests")

# Never shipped, even from an included tree.
EXCLUDE_NAMES = ("__pycache__", ".DS_Store", ".pyc")

# Content, not tooling. Named so the reason survives; the allow-list already
# excludes them.
WITHHELD = {
    "shell/": "the team's production shell — you supply your own export",
    "config.yaml": "one team's profile — `/shell-sync onboard` writes yours",
    "ledger/": "their record of what shipped",
    "profiles/": "any other products they onboarded",
    "explainer.html": "their product-specific onboarding page",
    "runs/": "working files from their runs",
    "boards.json": "their Claude Design board ids",
}

# A last check before writing: no shipped file may name the originating team's
# repos or product. Tests carry fixtures, so this runs over everything.
LEAK_RE = re.compile(r"app-lcnc-claude-(?:harness|docs)|app[-_ ]?lca|low-code\.browserstack", re.I)


class PackageError(Exception):
    """Raised when the package would ship something it should not."""


def _wanted(rel):
    if any(part in EXCLUDE_NAMES for part in rel.parts):
        return False
    if rel.suffix == ".pyc":
        return False
    return True


def collect(skill_dir=None):
    """Return [(arcname, absolute path)] for everything that ships."""
    skill_dir = Path(skill_dir or paths.SKILL_DIR)
    items = []
    for name in INCLUDE_FILES:
        src = skill_dir / name
        if src.is_file():
            items.append((name, src))
    for tree in INCLUDE_TREES:
        base = skill_dir / tree
        if not base.is_dir():
            continue
        for src in sorted(base.rglob("*")):
            if not src.is_file():
                continue
            rel = src.relative_to(skill_dir)
            if _wanted(rel):
                items.append((rel.as_posix(), src))
    return items


def audit(items):
    """Which shipped files still name the originating team. Empty is the goal."""
    hits = []
    for arcname, src in items:
        try:
            text = src.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if LEAK_RE.search(line):
                hits.append((arcname, lineno, line.strip()[:100]))
    return hits


README = """# shell-sync

Keeps a Claude Design HTML shell in step with what actually ships.

## Install

    bash install.sh

That symlinks this folder into ~/.claude/skills/shell-sync. Restart Claude Code,
then run:

    /shell-sync onboard

It interviews you about your product and writes your own profile. Nothing here is
tied to any particular product -- there is no shell and no config in this package,
because those are yours to supply.

## What you need first

  - A Claude Design shell of your product: one bundled HTML export.
  - The GitHub CLI, signed in: `gh auth login`. It reads merged pull requests to
    work out what shipped, so it needs to reach your product's repos.
  - Python 3.9 or newer. Nothing to install -- it is standard library only.

## Then

    /shell-sync check       what your copy has, and what is missing. Writes nothing.
    /shell-sync             bring the shell up to what shipped
    /shell-sync new v2      your own copy to design in
    /shell-sync share v2    one HTML file you can send anyone

Full documentation: SKILL.md, and adopt.html in a browser.
"""

INSTALL_SH = """#!/usr/bin/env bash
# Put shell-sync where Claude Code looks for skills.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="$HOME/.claude/skills/shell-sync"

mkdir -p "$HOME/.claude/skills"

if [ -e "$DEST" ] || [ -L "$DEST" ]; then
  # Re-running the installer is normal. Replacing a symlink we made is fine;
  # deleting a real directory somebody put there by hand is not.
  if [ -L "$DEST" ]; then
    echo "replacing existing symlink at $DEST"
    rm "$DEST"
  else
    echo "error: $DEST already exists and is not a symlink." >&2
    echo "Move it aside and re-run, so nothing of yours is lost." >&2
    exit 1
  fi
fi

ln -s "$HERE" "$DEST"
echo "linked $DEST -> $HERE"

python3 - <<'PY'
import sys
if sys.version_info < (3, 9):
    sys.exit("error: Python 3.9+ required, found %s" % sys.version.split()[0])
print("python %s ok" % sys.version.split()[0])
PY

command -v gh >/dev/null 2>&1 \\
  && echo "gh found" \\
  || echo "note: GitHub CLI not found. Install it and run 'gh auth login' before your first sync."

echo
echo "Restart Claude Code, then run:  /shell-sync onboard"
"""


def build(out_path, skill_dir=None, strict=True):
    """Write the zip. With strict=True, refuse to write if anything leaks."""
    items = collect(skill_dir)
    if not items:
        raise PackageError("nothing collected — wrong skill directory?")
    hits = audit(items)
    if hits and strict:
        detail = "\n".join("  %s:%s  %s" % h for h in hits[:20])
        raise PackageError(
            "%d line(s) in the package still name the originating team:\n%s"
            % (len(hits), detail)
        )
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for arcname, src in items:
            zf.write(src, "shell-sync/" + arcname)
        zf.writestr("shell-sync/README.md", README)
        info = zipfile.ZipInfo("shell-sync/install.sh")
        info.external_attr = 0o755 << 16
        zf.writestr(info, INSTALL_SH)
    out_path.write_bytes(buf.getvalue())
    return out_path, items, hits


def main(argv):
    out = argv[1] if len(argv) > 1 else "shell-sync.zip"
    strict = "--force" not in argv
    try:
        path, items, hits = build(out, strict=strict)
    except PackageError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    print("wrote %s  (%d files, %.0f KB)" % (path, len(items) + 2, path.stat().st_size / 1024))
    print("\nheld back:")
    for name, why in sorted(WITHHELD.items()):
        print("  %-16s %s" % (name, why))
    if hits:
        print("\nWARNING: shipped anyway with %d leaking line(s) (--force)" % len(hits))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

#!/usr/bin/env bash
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

command -v gh >/dev/null 2>&1 \
  && echo "gh found" \
  || echo "note: GitHub CLI not found. Install it and run 'gh auth login' before your first sync."

echo
echo "Restart Claude Code, then run:  /shell-sync onboard"

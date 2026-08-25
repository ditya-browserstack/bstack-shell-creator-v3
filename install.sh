#!/usr/bin/env bash
# Install or UPDATE bstack-design-studio into ~/.claude/skills/.
# Prefers git (so future updates are a fast git pull); falls back to unzipping a .skill bundle.
set -euo pipefail
DEST="$HOME/.claude/skills/bstack-design-studio"
REPO="${BSTACK_SKILL_REPO:-}"   # set to the git URL, or run from an unpacked bundle

mkdir -p "$HOME/.claude/skills"
if [ -d "$DEST/.git" ]; then
  echo "updating existing install (git pull) — your captures in products/ are untouched…"
  git -C "$DEST" pull --ff-only
elif [ -n "$REPO" ]; then
  echo "cloning $REPO -> $DEST"
  git clone "$REPO" "$DEST"
else
  # bundle mode: copy this unpacked dir into place, preserving any existing products/ captures
  SRC="$(cd "$(dirname "$0")" && pwd)"
  echo "installing from bundle $SRC -> $DEST (preserving your products/ captures)"
  rsync -a --exclude '.git' --exclude 'products/*/app-shell/screens' --exclude 'products/*/app-shell/share' \
        --exclude 'products/*/app-shell/self-check' "$SRC/" "$DEST/"
fi

# one-time deps for the weekly-sync half
[ -f "$DEST/sync/install.sh" ] && bash "$DEST/sync/install.sh" || true
echo "done. Restart Claude Code; the skill is 'bstack-design-studio'. Updates are offered automatically on use."

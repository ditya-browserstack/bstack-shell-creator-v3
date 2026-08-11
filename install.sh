#!/usr/bin/env bash
# Install bstack-design-studio into ~/.claude/skills and set up the sync engine.
#
#   unzip bstack-design-studio.skill -d ~/.claude/skills/     # or anywhere
#   bash ~/.claude/skills/bstack-design-studio/install.sh
#
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "bstack-design-studio — install"
echo "  skill dir: $HERE"

# 1. sanity: node + python present
command -v node   >/dev/null || { echo "  ! node not found — the design engine needs Node 18+"; }
command -v python3>/dev/null || { echo "  ! python3 not found — the sync engine needs Python 3.9+"; }
command -v gh     >/dev/null || echo "  ! gh (GitHub CLI) not found — the sync engine needs it; install + 'gh auth login'"

# 2. run design engine's tests (fast, no network)
if command -v node >/dev/null; then
  ( cd "$HERE/design" && node --test lib/ >/dev/null 2>&1 && echo "  design engine: tests pass" ) || echo "  ! design tests failed — check Node version"
fi

# 3. set up the sync engine (Harsh's shell-sync installer, run from its own dir)
if [ -f "$HERE/sync/install.sh" ]; then
  echo "  setting up sync engine..."
  ( cd "$HERE/sync" && bash install.sh ) || echo "  ! sync install.sh failed — see sync/README.md"
fi

cat <<EOF

Done. In Claude Code:
  • "set up my product"   → capture your real app shell   (design engine)
  • "design this TB"       → brief → explorations           (design engine)
  • "sync the shell"       → keep it fresh vs production     (sync engine)

First-time SETUP needs: your product's repo, a logged-in live URL, and browser access.
Everyday design use does not. See SKILL.md.
EOF

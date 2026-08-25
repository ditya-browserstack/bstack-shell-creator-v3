#!/usr/bin/env bash
# Ship a skill update: bump version, tag, push to origin, and build the .skill bundle.
#   ./release.sh [patch|minor|major]   (default: patch)
set -euo pipefail
cd "$(dirname "$0")"
BUMP="${1:-patch}"
[ -z "$(git remote 2>/dev/null)" ] && { echo "release: no git remote — set one first (see install/README)"; exit 1; }
[ -n "$(git status --porcelain | grep -v '^??')" ] && { echo "release: commit your changes first"; exit 1; }

NEW=$(node -e "const v=require('./version.json').version.split('.').map(Number);const b='$BUMP';if(b==='major'){v[0]++;v[1]=0;v[2]=0}else if(b==='minor'){v[1]++;v[2]=0}else{v[2]++};console.log(v.join('.'))")
node -e "const fs=require('fs');const j=require('./version.json');j.version='$NEW';fs.writeFileSync('./version.json',JSON.stringify(j,null,2)+'\n')"
echo "  version -> $NEW  (add a CHANGELOG entry for $NEW before pushing if you haven't)"

git add version.json CHANGELOG.md
git commit -q -m "release v$NEW"
git tag "v$NEW"
git push origin "$(git branch --show-current)" --tags
echo "  pushed v$NEW — colleagues' next skill run will offer the update."

# build the shareable bundle (excludes .git, user captures, and regenerable artifacts)
BUNDLE=~/Desktop/bstack-shell-creator-v3.skill
( cd .. && rm -f "$BUNDLE" && zip -r -0 -q "$BUNDLE" bstack-shell-creator-v3 \
  -x '*/.git/*' -x '*.png' -x '*/shots/*' -x '*/cards/*' -x '*cards-gallery.html' \
  -x '*/self-check/*' -x '*/share/*' -x '*/node_modules/*' -x '*.DS_Store' -x '*/.last-update-check' )
echo "  bundle -> $BUNDLE ($(du -h "$BUNDLE" | cut -f1))"

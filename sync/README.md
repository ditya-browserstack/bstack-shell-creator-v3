# shell-sync

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

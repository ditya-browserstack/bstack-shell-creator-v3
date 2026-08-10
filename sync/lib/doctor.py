#!/usr/bin/env python3
"""One-shot readiness check: what this checkout has, and what it is missing.

The skill is shared, so most people using it never run a sync -- they pull and
consume. This answers their actual questions in one command: is my shell current,
which versions exist, and is anything about my setup going to fail.

Read-only. It never writes, so it is safe to run at any point in a run.
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gitstore  # noqa: E402
import ledger  # noqa: E402
import paths  # noqa: E402
import storyboard  # noqa: E402
import versions  # noqa: E402

OK, WARN, BAD = "ok", "warn", "problem"


def _git(*args, cwd=None):
    try:
        out = subprocess.run(
            ["git"] + list(args), cwd=str(cwd or paths.SKILL_DIR),
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
        )
        return out.stdout.decode("utf-8").strip()
    except OSError:
        return ""


def checks():
    rows = []
    config = paths.load_config()

    # --- the shell itself -------------------------------------------------
    template = paths.SHELL_DIR / "template.html"
    host = paths.SHELL_DIR / "host.html"
    if template.is_file() and host.is_file():
        text = template.read_text(encoding="utf-8")
        rows.append((OK, "prod-parity shell", "%d KB, fingerprint %s" % (
            len(text) // 1024, storyboard.fingerprint(text))))
    else:
        rows.append((BAD, "prod-parity shell", "missing — re-pull the harness repo"))

    # --- am I behind the team? -------------------------------------------
    # Unpushed or unpulled commits are the single most likely reason someone's
    # shell disagrees with a colleague's.
    behind = _git("rev-list", "--count", "HEAD..@{u}")
    ahead = _git("rev-list", "--count", "@{u}..HEAD")
    if behind == "" and ahead == "":
        rows.append((WARN, "git tracking", "no upstream set — cannot tell if you are current"))
    elif behind not in ("0", ""):
        rows.append((BAD, "git tracking", "%s commit(s) behind — git pull before running" % behind))
    elif ahead not in ("0", ""):
        rows.append((WARN, "git tracking", "%s commit(s) unpushed — the team cannot see your shell yet" % ahead))
    else:
        rows.append((OK, "git tracking", "up to date with the team"))

    dirty = _git("status", "--porcelain", str(paths.SHELL_DIR))
    if dirty:
        rows.append((WARN, "shell working tree", "uncommitted shell edits — commit or discard before a sync"))

    # --- ledger -----------------------------------------------------------
    data = ledger.load()
    if data.get("legacy"):
        rows.append((WARN, "ledger", "still the legacy single file — run: python3 -c \"import sys;sys.path.insert(0,'lib');import ledger;ledger.migrate()\""))
    else:
        rows.append((OK, "ledger", "%d features, last run %s" % (
            len(data["features"]), data["last_run"] or "never")))

    # --- versions ---------------------------------------------------------
    # Versions are git refs now, so "is it set up?" is one question: can we open
    # the repo? Everything else -- what exists, how far behind -- comes from git
    # and cannot disagree with reality the way a stored manifest could.
    try:
        repo = versions.repo_path(config)
    except versions.VersionError as exc:
        rows.append((BAD, "versions", str(exc)))
        repo = None

    if repo is not None:
        found = versions.list_versions(config)
        parity = versions.parity_ref(config)
        if not gitstore.ref_exists(repo, parity):
            rows.append((WARN, "versions",
                         "prod parity not published yet — run: "
                         "python3 lib/versions.py publish-parity"))
        elif not found:
            rows.append((OK, "versions",
                         'none yet (create with: versions.py new <name> "<label>")'))
        else:
            stale = ["%s (behind %d)" % (m["slug"], m["behind"])
                     for m in found if m["behind"]]
            note = "%d version(s): %s" % (
                len(found), ", ".join(m["slug"] for m in found))
            rows.append((WARN if stale else OK, "versions",
                         note + ("  " + ", ".join(stale) if stale else "")))

    # --- boards (machine-local) ------------------------------------------
    boards = storyboard.board_status(storyboard.load_boards(), config)
    if not boards:
        rows.append((OK, "Claude Design", "nothing boarded from this machine yet"))
    else:
        for row in boards:
            state = row["state"]
            rows.append((OK if state == "current" else WARN, "Claude Design",
                         "%s is %s (pushed %s)" % (row["source"], state, row.get("pushed", "?"))))

    # --- tooling ----------------------------------------------------------
    gh = _git("--version") and subprocess.run(
        ["gh", "auth", "status"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False
    ).returncode == 0
    rows.append((OK if gh else BAD, "gh auth",
                 "authenticated" if gh else "not authenticated — a sync will abort at Stage 1"))
    return rows


def main():
    rows = checks()
    mark = {OK: "  ok  ", WARN: " warn ", BAD: "PROBLEM"}
    for state, name, detail in rows:
        print("%s  %-20s %s" % (mark[state], name, detail))
    problems = [r for r in rows if r[0] == BAD]
    print()
    if problems:
        print("%d problem(s) to fix before running a sync." % len(problems))
        return 1
    print("Ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

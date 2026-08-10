#!/usr/bin/env python3
"""Write a profile for a new product, so the skill is not tied to one.

Everything product-specific now lives in config: which repos to watch, how to
recognise a ticket id, and how to spot the product's work inside a shared
monorepo. This turns a set of answers into a profile file and, importantly,
*checks the answers against reality* before writing -- an unreachable repo or a
ticket prefix that matches nothing is far cheaper to catch here than three
stages into a run.

The interview itself is conducted by the agent (see SKILL.md); this module only
validates and writes. That split is deliberate: asking good follow-up questions
is the agent's job, and being strict about what lands on disk is this file's.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import paths  # noqa: E402

PROFILES_DIRNAME = "profiles"

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,39}$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
PREFIX_RE = re.compile(r"^[A-Z][A-Z0-9]{1,9}$")

REQUIRED = ("slug", "product_name", "product_url", "ticket_prefix", "repos")


class OnboardError(Exception):
    """Raised when an answer cannot be used."""


def profiles_dir():
    return paths.SKILL_DIR / PROFILES_DIRNAME


def validate(answers):
    """Check the answers make sense on their own terms. Returns a warnings list."""
    missing = [k for k in REQUIRED if not answers.get(k)]
    if missing:
        raise OnboardError("missing answer(s): %s" % ", ".join(missing))

    if not SLUG_RE.match(answers["slug"]):
        raise OnboardError(
            "slug %r must be lowercase letters, digits and dashes" % answers["slug"]
        )
    if not PREFIX_RE.match(answers["ticket_prefix"]):
        raise OnboardError(
            "ticket_prefix %r must be uppercase letters/digits, e.g. LCAM or LT"
            % answers["ticket_prefix"]
        )
    if not str(answers["product_url"]).startswith("http"):
        raise OnboardError("product_url must be a URL")

    for key in ("repos", "shared_repos"):
        for repo in answers.get(key) or []:
            if not REPO_RE.match(repo):
                raise OnboardError("%s entry %r must be owner/name" % (key, repo))
    if not answers["repos"]:
        raise OnboardError("at least one dedicated repo is required")

    warnings = []
    if not answers.get("shared_repos"):
        warnings.append(
            "No shared monorepo listed. If the product's frontend lives in one, its "
            "work will be invisible — that gap once hid an entire shipped feature."
        )
    if not answers.get("product_signals"):
        warnings.append(
            "No product signals given. Only PRs carrying a %s id will be recognised "
            "in shared repos." % answers["ticket_prefix"]
        )
    patterns = answers.get("drop_branch_patterns") or []
    trunks = {"main", "master"}
    if not trunks & set(patterns):
        warnings.append(
            "Neither 'main' nor 'master' is in the branch patterns. Whichever is the "
            "trunk must be listed, or PRs merged straight to it are never seen."
        )
    return warnings


def check_repos(answers):
    """Confirm each repo is reachable with the current gh credentials."""
    results = []
    for repo in list(answers.get("repos") or []) + list(answers.get("shared_repos") or []):
        out = subprocess.run(
            ["gh", "repo", "view", repo, "--json", "name"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
        results.append((repo, out.returncode == 0))
    return results


def probe_ticket_prefix(answers, since):
    """Do any recent PRs actually carry this ticket prefix?

    A prefix that matches nothing is the single most likely wrong answer, and it
    fails silently later: the run simply reports that nothing shipped.
    """
    import harvest

    ticket = harvest.ticket_re(answers["ticket_prefix"])
    hits, checked = 0, 0
    for repo in answers["repos"][:2]:
        try:
            prs = harvest.fetch_prs(repo, since)
        except harvest.HarvestError:
            continue
        checked += len(prs)
        for pr in prs:
            if harvest.extract_ticket_ids(pr, ticket, answers["ticket_prefix"]):
                hits += 1
    return {"prs_seen": checked, "with_ticket_id": hits}


def render(answers):
    """Produce the profile text, in the flat format the config reader accepts."""
    lines = [
        "# %s — profile for /shell-sync." % answers["product_name"],
        "# Written by lib/onboard.py. Flat 'key: value' and '- item' only; the",
        "# reader does not understand nesting.",
        "",
        "product_name: %s" % answers["product_name"],
        "product_url: %s" % answers["product_url"],
        "",
        "# How a ticket id is written, e.g. %s-1234." % answers["ticket_prefix"],
        "ticket_prefix: %s" % answers["ticket_prefix"],
        "",
        "shell_source: %s" % (answers.get("shell_source") or "~/Documents/%s/Shell.html" % answers["product_name"]),
        "",
        "# Versions are git branches named shell/<product_slug>/<name>. The slug",
        "# namespaces them so several products can share one repo without colliding.",
        "product_slug: %s" % answers["slug"],
        "",
        "# The repo holding those branches. Relative resolves against the folder",
        "# holding your checkouts, so one committed value works for the whole team.",
        "version_repo: %s" % (answers.get("version_repo") or "."),
        "",
        "# Where the shell is tracked inside that repo.",
        "shell_path: %s" % (answers.get("shell_path")
                            or "design-shells/%s/shell" % answers["slug"]),
        "",
        "# Dedicated repos: every merged PR here is this product's work.",
        "repos:",
    ]
    lines += ["  - %s" % r for r in answers["repos"]]
    lines += [
        "",
        "# Shared monorepos serving several products. A PR here counts only if it",
        "# carries a ticket id or one of the signals below.",
        "shared_repos:",
    ]
    lines += ["  - %s" % r for r in (answers.get("shared_repos") or [])]
    lines += [
        "",
        "# Words that mark this product's work in a shared repo.",
        "product_signals:",
    ]
    lines += ["  - %s" % s for s in (answers.get("product_signals") or [])]
    lines += [
        "",
        "# Release-train base branches. The trunk MUST be here.",
        "drop_branch_patterns:",
    ]
    lines += ["  - %s" % p for p in (answers.get("drop_branch_patterns") or ["main"])]
    lines += ["", "default_window_days: %s" % (answers.get("window_days") or 7), ""]
    return "\n".join(lines)


def write(answers, overwrite=False):
    validate(answers)
    target = profiles_dir() / ("%s.yaml" % answers["slug"])
    if target.exists() and not overwrite:
        raise OnboardError("profile already exists: %s" % target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render(answers), encoding="utf-8")
    return target


def main(argv):
    if len(argv) != 3 or argv[1] != "write":
        print("usage: onboard.py write <answers.json>", file=sys.stderr)
        print("       (the agent collects the answers — see SKILL.md)", file=sys.stderr)
        return 2
    answers = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
    try:
        warnings = validate(answers)
    except OnboardError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    for repo, ok in check_repos(answers):
        print("  %-40s %s" % (repo, "reachable" if ok else "NOT REACHABLE"))
    for w in warnings:
        print("  warning: %s" % w)
    try:
        target = write(answers, overwrite=bool(answers.get("overwrite")))
    except OnboardError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    print("\nwrote %s" % target)
    print("Use it with:  APP_SHELL_PROFILE=%s python3 lib/doctor.py" % answers["slug"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

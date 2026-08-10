#!/usr/bin/env python3
"""Harvest a product's production releases from GitHub.

Written for teams whose repos have no GitHub releases, which is the common case:
the production release train is drop branches (drop-28-july, JUL_drop, ...) with
hotfixes going straight to trunk. So the release signal is "merged PRs whose base
branch is a release branch", and which branches count is configuration.

Jira enrichment is deliberately NOT done here: Python has no access to the
Atlassian MCP server. This script emits ticket ids and the agent enriches them
per SKILL.md.
"""
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path

# The two product-specific patterns are BUILT FROM CONFIG, not hardcoded, so a
# second product needs a profile rather than a fork of this file.
#
# There is no default prefix and no default signal on purpose. A wrong-but-plausible
# default here is the worst failure this tool has: every filter still runs, every
# stage still reports success, and the gap list simply comes back empty or full of
# another team's work. Callers pass what config says; config is written by the
# onboarding interview, which checks the prefix against real PRs before saving it.
DEFAULT_TICKET_PREFIX = ""
DEFAULT_PRODUCT_SIGNALS = ()


def ticket_re(prefix):
    """Match "<PREFIX> 1234" in any of its written forms: LT-2580, Lt_2580, lt 2580.

    Refuses an empty prefix rather than defaulting. Interpolating "" would leave
    `\\b[\\s_-]*(\\d{1,5})\\b`, which matches every bare number in every PR title --
    so a missing `ticket_prefix` would not fail, it would quietly classify the
    whole monorepo as this product's work.
    """
    if not prefix:
        raise HarvestError(
            "ticket_prefix is not set. Add it to your profile "
            "(e.g. ticket_prefix: LT) — there is no safe default."
        )
    return re.compile(r"\b%s[\s_-]*(\d{1,5})\b" % re.escape(prefix), re.I)


def signal_re(prefix, signals):
    """Match a product signal, for PRs from monorepos that serve several products.

    A ticket id always counts. Each configured signal is word-bounded and allows
    space, dash or underscore where the config has a space, so "low code" also
    matches "low-code" and "low_code".

    With no prefix and no signals there is nothing that could match, which would
    silently empty every shared-repo gap list; say so instead.
    """
    if not prefix and not signals:
        raise HarvestError(
            "neither ticket_prefix nor product_signals is set, so no shared-repo "
            "PR could ever be recognised as this product's work."
        )
    parts = []
    if prefix:
        parts.append(r"%s[\s_-]*\d+" % re.escape(prefix))
    for signal in signals:
        parts.append(r"\b%s\b" % re.escape(signal).replace(r"\ ", r"[\s_-]?"))
    return re.compile("(%s)" % "|".join(parts), re.I)

NOISE_PATTERNS = (
    "bump", "upgrade", "dependabot", "dependency", "deps",
    "ci_cd", "ci/cd", "pipeline", "workflow",
    "add specs", "add spec", "add tests", "add test",
    "rubocop", "lint", "typo", "revert",
)

# Version-bump PRs in these repos are often titled with just a package name and a
# version, e.g. "Abc 2653 mysql2 0.5.7", which no keyword above catches. A bare
# version token is a reliable tell. Feature titles here do not carry versions,
# and this only feeds a human-reviewed gap report, so a rare false drop is cheap.
VERSION_RE = re.compile(r"\b\d+\.\d+(?:\.\d+)*\b")

# Word-bounded tokens, tuned against a real July 2026 harvest that returned 41
# candidates, most of them not user-visible: "Adding UTs for Email automation",
# "updated the package-lock file for runner", "chore: plock update".
# These MUST be word-bounded, not substring matches: a bare "uts" substring also
# hits "outputs" and "shortcuts".
NOISE_WORD_RE = re.compile(
    r"\b(uts?|specs?|plock|package-lock|chore|rubocop|lint|typo|revert)\b", re.I
)

PR_FIELDS = "number,title,body,headRefName,baseRefName,mergedAt,url"

# browserstack/frontend merges 400+ PRs in a two-week window. At the old limit of
# 100 the harvest silently saw only the newest ones and still reported no
# problems, so candidates vanished between runs as newer merges pushed them out.
# Anything at or above this is reported as truncation rather than passed off as a
# complete answer.
PR_LIMIT = 600




class HarvestError(Exception):
    """Raised when the gh CLI cannot be used."""


def matches_release_branch(base_ref, patterns):
    return any(fnmatch.fnmatch(base_ref, pattern) for pattern in patterns)


def is_product(pr, signal):
    """Whether a PR from a shared monorepo is this product's work.

    browserstack/frontend serves every BrowserStack product, so its release
    branches carry Test Management, accessibility and AI work too. Requiring an
    explicit product signal keeps those out of the gap report.
    """
    haystack = " ".join([pr.get("title", ""), pr.get("headRefName", "")])
    return signal.search(haystack) is not None


def extract_ticket_ids(pr, ticket, prefix):
    """Pull ticket ids from title, branch name and body, normalised to PREFIX-NNNN."""
    haystack = " ".join([
        pr.get("title", ""), pr.get("headRefName", ""), pr.get("body", "") or ""
    ])
    ids = []
    for number in ticket.findall(haystack):
        candidate = "%s-%s" % (prefix, number)
        if candidate not in ids:
            ids.append(candidate)
    return ids


def is_noise(title):
    lowered = title.lower()
    if any(pattern in lowered for pattern in NOISE_PATTERNS):
        return True
    if NOISE_WORD_RE.search(title):
        return True
    return VERSION_RE.search(title) is not None


def filter_prs(prs, patterns, signal):
    """Keep release-branch PRs that are not noise.

    PRs marked shared=True must additionally carry a product signal.
    """
    kept = []
    for pr in prs:
        if not matches_release_branch(pr.get("baseRefName", ""), patterns):
            continue
        if is_noise(pr.get("title", "")):
            continue
        if pr.get("shared") and not is_product(pr, signal):
            continue
        kept.append(pr)
    return kept


def fetch_prs(repo, since, shared=False):
    """Return merged PRs for one repo since `since` (YYYY-MM-DD) via gh."""
    command = [
        "gh", "pr", "list", "-R", repo, "--state", "merged",
        "--search", "merged:>=%s" % since, "--limit", str(PR_LIMIT),
        "--json", PR_FIELDS,
    ]
    try:
        result = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
        )
    except OSError as exc:
        raise HarvestError("cannot run gh: %s" % exc)
    if result.returncode != 0:
        raise HarvestError(
            "gh failed for %s: %s" % (repo, result.stderr.decode("utf-8").strip())
        )
    prs = json.loads(result.stdout.decode("utf-8") or "[]")
    for pr in prs:
        pr["repo"] = repo.split("/")[-1]
        pr["shared"] = shared
    if len(prs) >= PR_LIMIT:
        raise HarvestError(
            "%s returned %d PRs, the maximum requested — older PRs in this window "
            "were not seen. Narrow the window or raise PR_LIMIT." % (repo, len(prs))
        )
    return prs


def to_candidates(prs, ticket, prefix):
    """Group PRs into candidate features, keyed by ticket id where one exists."""
    grouped = {}
    order = []
    for pr in prs:
        ids = extract_ticket_ids(pr, ticket, prefix)
        key = ids[0] if ids else "pr-%s-%s" % (pr.get("repo"), pr.get("number"))
        if key not in grouped:
            grouped[key] = {
                "lcam_id": ids[0] if ids else None,
                "name": pr.get("title", ""),
                "prs": [],
            }
            order.append(key)
        grouped[key]["prs"].append(pr)
    return [grouped[key] for key in order]


def main(argv):
    if len(argv) != 2:
        print("usage: harvest.py <since-YYYY-MM-DD>", file=sys.stderr)
        return 2
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import paths

    config = paths.load_config()
    all_prs = []
    problems = []
    targets = [(repo, False) for repo in config["repos"]]
    targets += [(repo, True) for repo in config.get("shared_repos", [])]
    for repo, shared in targets:
        try:
            all_prs.extend(fetch_prs(repo, argv[1], shared))
        except HarvestError as exc:
            problems.append(str(exc))
    prefix = config.get("ticket_prefix", DEFAULT_TICKET_PREFIX)
    signals = config.get("product_signals") or list(DEFAULT_PRODUCT_SIGNALS)
    ticket = ticket_re(prefix)
    signal = signal_re(prefix, signals)
    candidates = to_candidates(
        filter_prs(all_prs, config["drop_branch_patterns"], signal), ticket, prefix
    )
    print(json.dumps(
        {"since": argv[1], "candidates": candidates, "problems": problems},
        indent=2, ensure_ascii=False,
    ))
    return 1 if problems and not candidates else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

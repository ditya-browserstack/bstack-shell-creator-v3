#!/usr/bin/env python3
"""Read and write git refs without ever touching the working tree.

Versions are branches. That is only safe because nothing here checks one out.

The reason is specific and easy to miss: the skill, its ledger and the shell can
all live in the same repository. `git checkout <version>` would therefore swap the
skill's own code and its record of what shipped -- in the middle of a run that is
reading them. It would also fail outright whenever the designer had unsaved work.

So every operation goes through plumbing instead:

  read      `git show <ref>:<path>`
  write     a throwaway index (GIT_INDEX_FILE) -> write-tree -> commit-tree
  merge     `git merge-tree --write-tree`, which merges two commits and returns a
            tree without an index or a worktree at all
  compare   `git rev-list --count`, scoped to a path

None of these move HEAD, and none of them care whether the worktree is dirty.
"""
import os
import subprocess
import tempfile
from pathlib import Path

# `git merge-tree --write-tree` landed in 2.38. Below that there is no way to
# merge without a worktree, and silently falling back to a checkout is exactly
# the thing this module exists to prevent.
MIN_GIT = (2, 38)


class GitError(Exception):
    """A git command failed, or the repo cannot be used."""


def _run(repo, args, env=None, check=True, stdin=None):
    full = dict(os.environ)
    full.update(env or {})
    # A commit made through plumbing still needs an identity. Supply one only if
    # the user has not configured theirs, so real commits keep real authorship.
    full.setdefault("GIT_AUTHOR_NAME", full.get("GIT_AUTHOR_NAME", "shell-sync"))
    proc = subprocess.run(
        ["git", "-C", str(repo)] + list(args),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        input=stdin.encode("utf-8") if isinstance(stdin, str) else stdin,
        env=full, check=False,
    )
    out = proc.stdout.decode("utf-8", "replace")
    err = proc.stderr.decode("utf-8", "replace").strip()
    if check and proc.returncode != 0:
        raise GitError("git %s failed: %s" % (" ".join(args[:2]), err or "no output"))
    return proc.returncode, out, err


def git_version():
    proc = subprocess.run(["git", "--version"], stdout=subprocess.PIPE, check=False)
    text = proc.stdout.decode("utf-8", "replace")
    parts = text.split()[2].split(".") if len(text.split()) > 2 else []
    nums = []
    for part in parts[:2]:
        digits = "".join(c for c in part if c.isdigit())
        nums.append(int(digits or 0))
    return tuple(nums) or (0, 0)


def require_git():
    have = git_version()
    if have < MIN_GIT:
        raise GitError(
            "git %s is too old for worktree-free merges; %s+ is required. "
            "Versions would otherwise need a checkout, which can overwrite "
            "in-progress work." % (".".join(map(str, have)), ".".join(map(str, MIN_GIT)))
        )
    return have


def is_repo(repo):
    path = Path(repo)
    if not path.is_dir():
        return False
    code, out, _ = _run(path, ["rev-parse", "--is-inside-work-tree"], check=False)
    return code == 0 and out.strip() == "true"


def resolve(repo, ref):
    """The commit a ref points at, or None if it does not exist."""
    code, out, _ = _run(repo, ["rev-parse", "--verify", "--quiet", ref + "^{commit}"],
                        check=False)
    return out.strip() or None if code == 0 else None


def ref_exists(repo, ref):
    return resolve(repo, ref) is not None


def read_file(repo, ref, path):
    """File contents at a ref. Never checks the ref out."""
    code, out, err = _run(repo, ["show", "%s:%s" % (ref, path)], check=False)
    if code != 0:
        raise GitError("cannot read %s at %s: %s" % (path, ref, err))
    return out


def file_exists(repo, ref, path):
    code, _, _ = _run(repo, ["cat-file", "-e", "%s:%s" % (ref, path)], check=False)
    return code == 0


def list_refs(repo, prefix):
    """[(short name, sha, ISO date, subject)] for every branch under `prefix`."""
    fmt = "%(refname:short)%09%(objectname)%09%(committerdate:short)%09%(contents:subject)"
    _, out, _ = _run(repo, ["for-each-ref", "--format=" + fmt,
                            "refs/heads/%s*" % prefix.rstrip("*")])
    rows = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 3:
            rows.append((parts[0], parts[1], parts[2], parts[3] if len(parts) > 3 else ""))
    return rows


def commit_file(repo, ref, path, content, message, base_ref=None):
    """Commit one file onto `ref`, building the tree in a throwaway index.

    `base_ref` seeds the tree for a ref that does not exist yet. The real index is
    untouched, so this is safe to run while the designer has edits in progress.
    """
    parent = resolve(repo, ref)
    seed = parent or (resolve(repo, base_ref) if base_ref else None)
    if seed is None and base_ref:
        raise GitError("base ref %r does not exist" % base_ref)

    handle, index_path = tempfile.mkstemp(prefix="shell-sync-index-")
    os.close(handle)
    os.unlink(index_path)  # git wants to create it itself
    env = {"GIT_INDEX_FILE": index_path}
    try:
        if seed:
            _run(repo, ["read-tree", seed], env=env)
        else:
            _run(repo, ["read-tree", "--empty"], env=env)
        _, blob, _ = _run(repo, ["hash-object", "-w", "--stdin"], stdin=content)
        _run(repo, ["update-index", "--add", "--cacheinfo",
                    "100644,%s,%s" % (blob.strip(), path)], env=env)
        _, tree, _ = _run(repo, ["write-tree"], env=env)
        args = ["commit-tree", tree.strip(), "-m", message]
        if parent:
            args += ["-p", parent]
        elif seed:
            args += ["-p", seed]
        _, commit, _ = _run(repo, args)
        commit = commit.strip()
        _run(repo, ["update-ref", "refs/heads/%s" % ref, commit])
        return commit
    finally:
        if os.path.exists(index_path):
            os.unlink(index_path)


def branch_from(repo, ref, base_ref, message):
    """Create `ref` at `base_ref` with one empty commit recording the fork.

    The empty commit is what makes the fork legible later: it carries the label,
    and it means `git log <ref>` opens with why the version exists rather than with
    whatever prod parity happened to be doing that day.
    """
    if ref_exists(repo, ref):
        raise GitError("version %r already exists" % ref)
    base = resolve(repo, base_ref)
    if base is None:
        raise GitError("cannot fork from %r: it does not exist" % base_ref)
    _, tree, _ = _run(repo, ["rev-parse", "%s^{tree}" % base])
    _, commit, _ = _run(repo, ["commit-tree", tree.strip(), "-p", base, "-m", message])
    commit = commit.strip()
    _run(repo, ["update-ref", "refs/heads/%s" % ref, commit])
    return commit


def delete_ref(repo, ref):
    _run(repo, ["update-ref", "-d", "refs/heads/%s" % ref])


def behind_count(repo, ref, base_ref, path=None):
    """Commits on `base_ref` that `ref` lacks, optionally scoped to a path.

    Scoping is not a refinement, it is the whole point. Measured across a shared
    docs repo, an untouched version read as 58 commits behind -- all of it other
    people's unrelated work -- while the shell itself had not moved at all.
    """
    args = ["rev-list", "--count", "%s..%s" % (ref, base_ref)]
    if path:
        args += ["--", path]
    code, out, _ = _run(repo, args, check=False)
    if code != 0:
        return 0
    return int(out.strip() or 0)


def default_remote(repo):
    code, out, _ = _run(repo, ["remote"], check=False)
    remotes = out.split() if code == 0 else []
    if not remotes:
        return None
    return "origin" if "origin" in remotes else remotes[0]


def is_shared(repo, ref, remote=None):
    """Whether this ref exists on the remote at the same commit.

    A version nobody pushed is invisible to the team and unbacked-up, and looks
    exactly like a shared one locally. Anything that reports versions should say
    which of these it is.
    """
    remote = remote or default_remote(repo)
    if not remote:
        return False
    local = resolve(repo, ref)
    code, out, _ = _run(repo, ["ls-remote", "--heads", remote, ref], check=False)
    if code != 0 or not out.strip():
        return False
    return out.split()[0] == local


def push(repo, ref, remote=None):
    """Publish a ref so teammates can fetch it.

    Deliberately not --force: if the remote has moved, that is a person's work and
    the answer is to look, not to overwrite it.
    """
    remote = remote or default_remote(repo)
    if not remote:
        raise GitError("no git remote configured, so there is nowhere to publish to")
    code, _, err = _run(repo, ["push", remote, "%s:refs/heads/%s" % (ref, ref)],
                        check=False)
    if code != 0:
        raise GitError("could not publish %s: %s" % (ref, err))
    return remote


def merge_base(repo, a, b):
    code, out, _ = _run(repo, ["merge-base", a, b], check=False)
    return out.strip() or None if code == 0 else None


def merge(repo, into_ref, from_ref, message, path_filter=None):
    """Merge `from_ref` into `into_ref` without a worktree or an index.

    Returns ("clean", sha) or ("conflict", [paths]). On conflict **nothing is
    written** -- the version is left exactly as it was. That is what makes running
    this automatically after every sync safe: the worst case is that a version
    stays where it is and gets reported, never that somebody's design work is
    silently mangled.
    """
    require_git()
    into = resolve(repo, into_ref)
    frm = resolve(repo, from_ref)
    if into is None or frm is None:
        raise GitError("cannot merge %s into %s: a ref is missing" % (from_ref, into_ref))

    if merge_base(repo, into, frm) == frm:
        return ("clean", into)  # already contains it; nothing to do

    code, out, err = _run(repo, ["merge-tree", "--write-tree", into, frm], check=False)
    lines = [line for line in out.splitlines()]
    if not lines:
        raise GitError("merge-tree produced no output: %s" % err)
    tree = lines[0].strip()

    if code != 0:
        conflicts = []
        for line in lines[1:]:
            if "\t" in line:
                candidate = line.split("\t", 1)[1].strip()
                if candidate and candidate not in conflicts:
                    conflicts.append(candidate)
        if path_filter:
            scoped = [c for c in conflicts if c.startswith(path_filter)]
            conflicts = scoped or conflicts
        return ("conflict", conflicts)

    _, commit, _ = _run(repo, ["commit-tree", tree, "-p", into, "-p", frm, "-m", message])
    commit = commit.strip()
    _run(repo, ["update-ref", "refs/heads/%s" % into_ref, commit])
    return ("clean", commit)

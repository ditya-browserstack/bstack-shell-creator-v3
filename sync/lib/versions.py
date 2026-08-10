#!/usr/bin/env python3
"""Design variations, stored as git branches.

Prod parity is a **build**, kept deliberately outside all of this: a plain file at
`shell/template.html` that the weekly sync rewrites and that you can open, diff and
read like any other file. It is the baseline, not one of the variations.

A *version* is a branch forked from that baseline, holding design that has not
shipped. Git is doing the versioning, so three things that used to be hand-rolled
now come for free:

  fork point   `git merge-base`, instead of a manifest listing ledger keys that
               could quietly disagree with reality
  staleness    `git rev-list --count`, instead of a set difference
  history      `git log <version>` -- what changed in this design, and when

The one thing git does *not* give you for free is safety, so two rules are
enforced here rather than assumed:

1. **Nothing is ever checked out.** See `gitstore`: the skill, the ledger and the
   shell can share a repository, so a checkout would swap the skill's own code
   mid-run. Every read and write goes through plumbing.

2. **A merge that conflicts changes nothing.** Prod parity is merged into every
   version after a sync. When the same region moved on both sides, the version is
   left exactly as it was and reported instead. Automatic merging is only
   acceptable while that holds.

Namespacing is per product -- `shell/<product>/<name>` -- because several products
are expected to share one repository, and `shell/v2` would collide on the second.
"""
import re
import sys
from pathlib import Path

import bundle
import gitstore
import paths

TEMPLATE_NAME = bundle.TEMPLATE_NAME
HOST_NAME = bundle.HOST_NAME

PARITY_NAME = "prod-parity"

# A name becomes part of a ref, so it must be a legal one and must not be able to
# walk anywhere. Lowercase alnum plus dash/underscore/dot, never leading with a
# dot -- which also rules out "." and ".." without special-casing them.
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,39}$")


class VersionError(Exception):
    """Raised for a bad name, a missing version, or a collision."""


def _check_slug(slug):
    if not SLUG_RE.match(slug or ""):
        raise VersionError(
            "invalid version name %r: use lowercase letters, digits, dash, dot or "
            "underscore, starting with a letter or digit (max 40)" % slug
        )
    if slug == PARITY_NAME:
        raise VersionError(
            "%r is the baseline, not a version -- pick another name" % PARITY_NAME
        )
    return slug


# --- where things live -------------------------------------------------------

def _config(config=None):
    return config if config is not None else paths.load_config()


def repo_path(config=None):
    """The git repository holding version branches."""
    config = _config(config)
    raw = config.get("version_repo")
    if not raw:
        raise VersionError(
            "version_repo is not set. Point it at a git repo your team shares, "
            "e.g. version_repo: our-design-docs"
        )
    repo = Path(raw)
    if not repo.is_absolute():
        repo = paths.resolve_shared(raw)
    if not gitstore.is_repo(repo):
        raise VersionError("version_repo %s is not a git repository" % repo)
    return repo


def namespace(config=None):
    """Ref prefix for this product: `shell/<product>/`."""
    config = _config(config)
    slug = config.get("product_slug") or _slugify(config.get("product_name", "shell"))
    return "shell/%s/" % slug


def _slugify(name):
    out = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return out or "shell"


def shell_path(config=None):
    """Path *inside the repo* where this product's shell template is tracked."""
    config = _config(config)
    return "%s/%s" % (
        (config.get("shell_path") or "design-shells/%s/shell"
         % _slugify(config.get("product_name", "shell"))).rstrip("/"),
        TEMPLATE_NAME,
    )


def parity_ref(config=None):
    return namespace(config) + PARITY_NAME


def version_ref(slug, config=None):
    return namespace(config) + _check_slug(slug)


def prod_template():
    return paths.SHELL_DIR / TEMPLATE_NAME


def prod_host():
    return paths.SHELL_DIR / HOST_NAME


# --- the baseline ------------------------------------------------------------

def publish_parity(config=None, message=None):
    """Mirror the prod-parity build into its ref, so versions can fork and compare.

    Prod parity stays a file; this is only its git handle. Called after a
    successful sync -- without it, every version's staleness is measured against a
    baseline that stopped moving, which reads as "everything is up to date".
    """
    config = _config(config)
    repo = repo_path(config)
    template = prod_template()
    if not template.is_file():
        raise VersionError("no prod-parity build at %s" % template)
    content = template.read_text(encoding="utf-8")
    ref = parity_ref(config)
    if gitstore.ref_exists(repo, ref):
        current = gitstore.read_file(repo, ref, shell_path(config))
        if current == content:
            return None  # nothing shipped that changed the shell
    return gitstore.commit_file(
        repo, ref, shell_path(config), content,
        message or "prod parity: sync", base_ref=_base_for_parity(repo),
    )


def _base_for_parity(repo):
    """Seed a brand-new parity ref from the repo's default branch if there is one.

    Starting from the default branch rather than an empty tree means a version
    branch is a normal branch of the repo -- browsable, diffable against main --
    instead of an orphan nobody can relate to anything.
    """
    for candidate in ("main", "master"):
        if gitstore.ref_exists(repo, candidate):
            return candidate
    return None


# --- versions ----------------------------------------------------------------

def create(slug, label="", config=None, from_export=None):
    """Fork a version from the current prod parity.

    `from_export` is the normal path for work done in Claude Design: point it at an
    exported bundle and the version is created *containing that design*, in one
    step. Forking an empty copy and then remembering to write the export into it is
    two steps with a silent failure in the middle -- a version that looks created
    but still holds prod parity.
    """
    config = _config(config)
    repo = repo_path(config)
    ref = version_ref(slug, config)
    parity = parity_ref(config)
    if not gitstore.ref_exists(repo, parity):
        publish_parity(config, "prod parity: initial")
    if not gitstore.ref_exists(repo, parity):
        raise VersionError("prod parity has not been published yet")
    message = "version %s%s" % (slug, (" — %s" % label) if label else "")
    gitstore.branch_from(repo, ref, parity, message)
    if from_export is not None:
        try:
            template = template_from_export(from_export)
        except Exception:
            # Leave nothing half-made: a branch holding prod parity under a name
            # that promises the designer's work is worse than no branch at all.
            gitstore.delete_ref(repo, ref)
            raise
        write_template(slug, template, "%s: from Claude Design export" % slug, config)
    return read_manifest(slug, config)


def template_from_export(path):
    """Pull the app source out of a Claude Design export.

    The export is a bundled page: fonts plus the app, joined in one file. Only the
    app source is versioned, and `bundle.unpack` verifies the split round-trips
    byte-for-byte before returning -- which is what catches an export that has been
    re-serialised into something that would render blank.
    """
    source = Path(path).expanduser()
    if not source.is_file():
        raise VersionError("no export at %s" % source)
    text = source.read_text(encoding="utf-8")
    try:
        _host, template = bundle.unpack(text)
    except bundle.BundleError as exc:
        raise VersionError(
            "%s does not look like a Claude Design export (%s). Export the "
            "prototype itself, not a screenshot or a page saved from a browser."
            % (source.name, exc)
        )
    return template


def import_into(slug, export_path, config=None):
    """Replace a version's design with a fresh Claude Design export."""
    config = _config(config)
    template = template_from_export(export_path)
    if template == read_template(slug, config):
        return None  # the export matches what is already there
    return write_template(
        slug, template, "%s: from Claude Design export" % slug, config)


def read_manifest(slug, config=None):
    """Describe a version. Everything here is derived from git, nothing stored."""
    config = _config(config)
    repo = repo_path(config)
    ref = version_ref(slug, config)
    if not gitstore.ref_exists(repo, ref):
        raise VersionError("no version %r" % slug)
    rows = {r[0]: r for r in gitstore.list_refs(repo, ref)}
    _, sha, created, _ = rows.get(ref, (ref, "", "", ""))
    return {
        "slug": slug,
        "ref": ref,
        "label": _label_of(repo, ref),
        "created": created,
        "sha": sha,
        "behind": gitstore.behind_count(
            repo, ref, parity_ref(config), shell_path(config)),
        "shared": gitstore.is_shared(repo, ref),
    }


LABEL_RE = re.compile(r"^version\s+\S+\s+—\s+(.*)$")


def _label_of(repo, ref):
    """The label from the fork commit -- the oldest commit unique to this branch."""
    code, out, _ = gitstore._run(
        repo, ["log", "--format=%s", "%s..%s" % (parity_of(ref), ref)], check=False)
    subjects = [s for s in out.splitlines() if s.strip()] if code == 0 else []
    for subject in reversed(subjects):
        match = LABEL_RE.match(subject)
        if match:
            return match.group(1).strip()
    return ""


def parity_of(ref):
    """The baseline ref for a version ref in the same namespace."""
    return ref.rsplit("/", 1)[0] + "/" + PARITY_NAME


def list_versions(config=None):
    """Every version for this product, with how far behind prod parity it is."""
    try:
        config = _config(config)
        repo = repo_path(config)
    except (VersionError, OSError):
        return []
    parity = parity_ref(config)
    path = shell_path(config)
    remote = gitstore.default_remote(repo)
    found = []
    for name, sha, created, _subject in gitstore.list_refs(repo, namespace(config)):
        slug = name.rsplit("/", 1)[-1]
        if slug == PARITY_NAME:
            continue
        found.append({
            "slug": slug,
            "ref": name,
            "label": _label_of(repo, name),
            "created": created,
            "sha": sha,
            "behind": gitstore.behind_count(repo, name, parity, path),
            "shared": gitstore.is_shared(repo, name, remote),
        })
    return sorted(found, key=lambda m: m["slug"])


def staleness(manifest, ledger_data=None):
    """How many prod-parity shell changes this version has not taken.

    `ledger_data` is accepted and ignored: staleness used to be a set difference
    over ledger keys, and callers still pass it. Git answers the question directly
    now, and cannot disagree with what actually happened.
    """
    return manifest.get("behind", 0)


def publish(slug=None, config=None):
    """Push a version (or the baseline) so the rest of the team can open it.

    Until this runs, a version exists only on one laptop. That is the failure this
    whole design is meant to prevent, and it is invisible locally -- an unpushed
    branch looks identical to a shared one.
    """
    config = _config(config)
    repo = repo_path(config)
    ref = parity_ref(config) if slug is None else version_ref(slug, config)
    if not gitstore.ref_exists(repo, ref):
        raise VersionError("nothing to publish: %s does not exist" % ref)
    return gitstore.push(repo, ref)


def read_template(slug, config=None):
    config = _config(config)
    return gitstore.read_file(
        repo_path(config), version_ref(slug, config), shell_path(config))


def write_template(slug, content, message, config=None):
    """Commit an edited template onto a version branch. Nothing is checked out."""
    config = _config(config)
    return gitstore.commit_file(
        repo_path(config), version_ref(slug, config), shell_path(config),
        content, message, base_ref=parity_ref(config),
    )


def refresh(slug, config=None):
    """Merge current prod parity into one version.

    Returns ("clean", sha) or ("conflict", [paths]). On conflict the version is
    untouched -- which is what lets this run automatically after every sync.
    """
    config = _config(config)
    repo = repo_path(config)
    return gitstore.merge(
        repo, version_ref(slug, config), parity_ref(config),
        "merge prod parity into %s" % slug,
        path_filter=shell_path(config).rsplit("/", 1)[0],
    )


def refresh_all(config=None):
    """Try to bring every version up to prod parity. Report what could not move."""
    results = []
    for manifest in list_versions(config):
        if not manifest["behind"]:
            results.append((manifest["slug"], "current", None))
            continue
        try:
            status, detail = refresh(manifest["slug"], config)
        except gitstore.GitError as exc:
            results.append((manifest["slug"], "error", str(exc)))
            continue
        results.append((manifest["slug"],
                        "merged" if status == "clean" else "conflict",
                        None if status == "clean" else detail))
    return results


# --- sharing -----------------------------------------------------------------

def _badge_html(manifest):
    """A fixed corner marker so a shared file cannot be mistaken for production.

    pointer-events:none keeps it from ever swallowing a click on the design
    underneath, and the z-index sits above the shell's own fixed toasts and panels.
    """
    slug = manifest.get("slug", "")
    label = manifest.get("label") or "exploration"
    behind = manifest.get("behind") or 0
    drift = (" &middot; %d prod change%s not in this"
             % (behind, "" if behind == 1 else "s")) if behind else ""
    return (
        '<div style="position:fixed;right:14px;bottom:14px;z-index:2147483647;'
        "font:500 12px/1.4 system-ui,-apple-system,'Segoe UI',sans-serif;"
        "background:#1F2937;color:#F9FAFB;padding:7px 12px;border-radius:9999px;"
        'box-shadow:0 2px 10px rgba(0,0,0,.28);pointer-events:none;">'
        "%s &middot; %s &mdash; not shipped%s</div>" % (slug, label, drift)
    )


def _inject_badge(template, manifest):
    """Insert the badge just before the template's closing body tag.

    The template is a complete HTML document whose app lives inside <x-dc>, so
    appending here is outside the DSL and cannot disturb it. If the anchor is ever
    missing, skip silently rather than corrupt the document -- a missing badge is
    a far smaller problem than an unpackable shell.
    """
    anchor = "</body>"
    index = template.rfind(anchor)
    if index == -1:
        return template
    return template[:index] + _badge_html(manifest) + template[index:]


def pack_version(slug, out_path, config=None, badge=True):
    """Pack one version into a standalone shareable HTML using prod parity's host."""
    config = _config(config)
    manifest = read_manifest(slug, config)
    template = read_template(slug, config)
    host = prod_host().read_text(encoding="utf-8")
    if badge:
        template = _inject_badge(template, manifest)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(bundle.pack(host, template), encoding="utf-8")
    return out


# --- CLI ---------------------------------------------------------------------

def _cmd_list():
    found = list_versions()
    if not found:
        print("no versions yet")
        return
    for manifest in found:
        behind = manifest["behind"]
        state = "up to date" if not behind else "behind by %d" % behind
        where = "shared" if manifest.get("shared") else "ONLY ON THIS MACHINE"
        print("%-16s %-26s %-14s %s" % (
            manifest["slug"], manifest.get("label") or "-", state, where))


def _cmd_refresh(slug=None):
    rows = refresh_all() if slug is None else [
        (slug,) + (lambda r: ("merged", None) if r[0] == "clean" else ("conflict", r[1]))(
            refresh(slug))
    ]
    for name, state, detail in rows:
        if state == "conflict":
            print("%-16s conflict — left untouched (%s)" % (name, ", ".join(detail or [])))
        elif state == "error":
            print("%-16s error — %s" % (name, detail))
        else:
            print("%-16s %s" % (name, state))


def main(argv):
    usage = (
        "usage: versions.py list\n"
        "       versions.py new <name> [label] [export.html]\n"
        "       versions.py import <name> <export.html>\n"
        "       versions.py share <name> <out.html>\n"
        "       versions.py refresh [name]\n"
        "       versions.py publish [name]\n"
        "       versions.py publish-parity"
    )
    if len(argv) < 2:
        print(usage, file=sys.stderr)
        return 2
    try:
        if argv[1] == "list" and len(argv) == 2:
            _cmd_list()
        elif argv[1] == "new" and len(argv) in (3, 4, 5):
            manifest = create(argv[2], argv[3] if len(argv) > 3 else "",
                              from_export=argv[4] if len(argv) == 5 else None)
            print("created %s at %s" % (manifest["slug"], manifest["ref"]))
            print("NOT SHARED YET — publish it with: "
                  "python3 lib/versions.py publish %s" % manifest["slug"])
        elif argv[1] == "import" and len(argv) == 4:
            sha = import_into(argv[2], argv[3])
            print("no change — the export matches %s" % argv[2] if sha is None
                  else "imported into %s (%s)" % (argv[2], sha[:10]))
        elif argv[1] == "share" and len(argv) == 4:
            out = pack_version(argv[2], argv[3])
            print("packed %s -> %s" % (argv[2], out))
        elif argv[1] == "refresh" and len(argv) in (2, 3):
            _cmd_refresh(argv[2] if len(argv) == 3 else None)
        elif argv[1] == "publish" and len(argv) in (2, 3):
            slug = argv[2] if len(argv) == 3 else None
            remote = publish(slug, None)
            print("published %s to %s" % (slug or "prod parity", remote))
        elif argv[1] == "publish-parity" and len(argv) == 2:
            sha = publish_parity()
            print("prod parity unchanged" if sha is None else "published %s" % sha[:10])
        else:
            print(usage, file=sys.stderr)
            return 2
    except (VersionError, gitstore.GitError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

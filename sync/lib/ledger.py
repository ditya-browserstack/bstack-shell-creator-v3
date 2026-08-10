#!/usr/bin/env python3
"""Ledger persistence for shell-sync.

Records when the workflow ran and every feature it has written into the shell.
That feature list is what lets a fresh Claude Design export be re-patched rather
than silently losing prior work.

**Stored as one file per fact, on purpose.** Anyone on the team may run the sync,
so two people can record work in the same week from different checkouts. A single
`ledger.json` made that a guaranteed merge conflict on a file nobody can sensibly
resolve by hand -- and worse, `last_run` was a shared scalar meaning "whoever ran
last", so one person's run silently moved another person's harvest window.

    ledger/
      features/<key>.json     one per feature ever added to the shell
      runs/<YYYY-MM-DD>.json  one per day the sync completed

Adds never touch the same path, so git merges them as a union with no conflict.
`last_run` is derived from the newest run file rather than stored, which is why a
run that ships nothing still advances the window: it writes a run file with no
features.
"""
import json
import re
from datetime import date, timedelta
from pathlib import Path

VERSION = 2

FEATURES_DIR = "features"
RUNS_DIR = "runs"
LEGACY_NAME = "ledger.json"

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _root(root=None):
    if root is not None:
        return Path(root)
    import paths
    return paths.LEDGER_DIR


def _key(feature):
    return "%s:%s" % (feature.get("lcam_id", ""), feature.get("name", "").lower())


def _filename(feature):
    """A stable, filesystem-safe name derived from the feature's key.

    Derived rather than random so the same feature recorded twice from two
    checkouts lands on the same path -- git then sees one file, not a duplicate
    pair that both survive a merge.
    """
    slug = _SLUG_RE.sub("-", _key(feature).lower()).strip("-")
    return (slug[:120] or "unnamed") + ".json"


def _legacy_path(root):
    return root.parent / LEGACY_NAME


def load(root=None):
    """Read the ledger. Falls back to a legacy single-file ledger if present."""
    target = _root(root)
    features, last_run = [], None

    fdir = target / FEATURES_DIR
    if fdir.is_dir():
        for item in sorted(fdir.glob("*.json")):
            features.append(json.loads(item.read_text(encoding="utf-8")))

    rdir = target / RUNS_DIR
    if rdir.is_dir():
        dates = sorted(p.stem for p in rdir.glob("*.json"))
        last_run = dates[-1] if dates else None

    if not features and last_run is None:
        legacy = _legacy_path(target)
        if legacy.is_file():
            data = json.loads(legacy.read_text(encoding="utf-8"))
            return {
                "version": data.get("version", 1),
                "last_run": data.get("last_run"),
                "features": data.get("features", []),
                "legacy": True,
            }

    # Deterministic order so a report never reshuffles between machines.
    features.sort(key=lambda f: (f.get("lcam_id", ""), f.get("name", "")))
    return {"version": VERSION, "last_run": last_run, "features": features}


def save(data, root=None):
    """Write every feature to its own file, and a run file for `last_run`."""
    target = _root(root)
    fdir = target / FEATURES_DIR
    rdir = target / RUNS_DIR
    fdir.mkdir(parents=True, exist_ok=True)
    rdir.mkdir(parents=True, exist_ok=True)

    for feature in data.get("features", []):
        (fdir / _filename(feature)).write_text(
            json.dumps(feature, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    last_run = data.get("last_run")
    if last_run:
        run_file = rdir / ("%s.json" % last_run)
        # Recording who ran makes a same-day collision from two checkouts obvious
        # in the diff instead of looking like a spurious change.
        payload = {"date": last_run, "features_total": len(data.get("features", []))}
        run_file.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return target


def window_start(data, window_days, today):
    """Return the inclusive start date for the harvest window, as YYYY-MM-DD.

    First run falls back to `window_days` before today. A last_run in the future
    (clock skew, a hand-added run file) clamps to today rather than producing a
    window that would re-harvest nothing meaningful.
    """
    last_run = data.get("last_run")
    if not last_run:
        return (today - timedelta(days=window_days)).isoformat()
    parsed = date(*[int(part) for part in last_run.split("-")])
    if parsed > today:
        return today.isoformat()
    return parsed.isoformat()


def record(data, feature):
    """Append a feature unless an entry with the same LCAM id and name exists."""
    existing = set(_key(item) for item in data["features"])
    if _key(feature) in existing:
        return
    data["features"].append(feature)


def added_feature_keys(data):
    return [_key(item) for item in data["features"]]


def migrate(root=None):
    """Convert a legacy `ledger.json` into the per-file layout.

    Leaves the legacy file in place; the caller deletes it once the new layout is
    committed, so a half-finished migration never loses the only copy.
    """
    target = _root(root)
    legacy = _legacy_path(target)
    if not legacy.is_file():
        return None
    data = json.loads(legacy.read_text(encoding="utf-8"))
    save(
        {"features": data.get("features", []), "last_run": data.get("last_run")},
        target,
    )
    return {
        "features": len(data.get("features", [])),
        "last_run": data.get("last_run"),
        "legacy": str(legacy),
    }

#!/usr/bin/env python3
"""Path resolution and config loading for shell-sync.

Paths resolve from this file's location, not cwd: harness skills are symlinked
into the workspace and run from workspace cwd. Path.resolve() follows the
symlink back to the real harness directory, which is what we want.
"""
import os
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = SKILL_DIR / "config.yaml"
SHELL_DIR = SKILL_DIR / "shell"
RUNS_DIR = SKILL_DIR / "runs"
LEDGER_PATH = SKILL_DIR / "ledger.json"   # legacy single-file ledger
LEDGER_DIR = SKILL_DIR / "ledger"         # one file per feature / per run

PATH_KEYS = ("shell_source",)

def _find_workspace(skill_dir):
    """Where relative shared paths are anchored.

    Two installs have to work, and they are not the same shape:

      <workspace>/<some-harness-repo>/.claude/skills/shell-sync   team install
      ~/.claude/skills/shell-sync                                 standalone

    In the team install the skill sits inside a checked-out repo, and a relative
    `version_repo` is meant to reach a *sibling* repo — so the anchor is the
    folder holding both. Standalone there are no siblings and no shared config
    to satisfy, so the anchor is the skill itself.

    Telling them apart by counting directories was the old approach and it was
    wrong: both layouts put the skill four levels under something. The reliable
    signal is whether the directory containing `.claude` is a git checkout.
    `SHELL_SYNC_WORKSPACE` overrides, for layouts neither rule fits.
    """
    override = os.environ.get("SHELL_SYNC_WORKSPACE")
    if override:
        return Path(os.path.expanduser(override)).resolve()
    for parent in skill_dir.parents:
        if parent.name != ".claude":
            continue
        repo = parent.parent
        if (repo / ".git").exists():
            return repo.parent
        break
    return skill_dir


WORKSPACE_DIR = _find_workspace(SKILL_DIR)


def resolve_shared(value):
    """Resolve a config path that must mean the same place on every machine.

    In a team install `version_repo` points at a sibling repo, which every
    teammate has under the same workspace but at a different absolute prefix. A
    relative value is resolved against the workspace root so one committed config
    works for everyone; an absolute value still wins, for anyone whose layout
    differs. Standalone, relative means "inside the skill".
    """
    path = Path(os.path.expanduser(value))
    if path.is_absolute():
        return path
    return (WORKSPACE_DIR / path).resolve()


def _coerce(value):
    if value.isdigit():
        return int(value)
    return value


def config_path():
    """Which config file to read.

    `APP_SHELL_PROFILE=<slug>` selects `profiles/<slug>.yaml`, so a second product
    is a new file rather than an edit to the shared one. Unset means the default
    `config.yaml`, which keeps every existing invocation working untouched.
    """
    profile = os.environ.get("APP_SHELL_PROFILE")
    if not profile:
        return CONFIG_PATH
    target = SKILL_DIR / "profiles" / ("%s.yaml" % profile)
    if not target.is_file():
        raise ValueError(
            "no profile %r at %s — run the onboarding flow first" % (profile, target)
        )
    return target


def load_config():
    """Read config.yaml.

    Deliberately minimal: flat "key: value" lines and "- item" lists. PyYAML is
    not guaranteed present, and the config has no need for nesting.
    """
    config = {}
    current_list_key = None
    for raw_line in config_path().read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.strip().startswith("#"):
            continue
        if line.startswith("  - ") or line.startswith("- "):
            if current_list_key is None:
                raise ValueError("list item outside of any key: %r" % line)
            item = line.split("- ", 1)[1].strip().strip('"').strip("'")
            config[current_list_key].append(item)
            continue
        if ":" not in line:
            raise ValueError("unparseable config line: %r" % line)
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if value == "":
            config[key] = []
            current_list_key = key
        else:
            current_list_key = None
            if key in PATH_KEYS:
                config[key] = str(Path(os.path.expanduser(value)))
            else:
                config[key] = _coerce(value)
    return config


def run_dir(date_str):
    """Return (creating if needed) the artifact directory for one run.

    live/manual/ is where the user drops screenshots for features the workflow
    could not reach itself. It is created up front so the path exists to be
    mentioned in the gap report.
    """
    target = RUNS_DIR / date_str
    (target / "live" / "manual").mkdir(parents=True, exist_ok=True)
    (target / "shell").mkdir(parents=True, exist_ok=True)
    return target

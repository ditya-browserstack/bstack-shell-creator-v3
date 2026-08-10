import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR / "lib"))

import paths  # noqa: E402

# The reader is tested against a config the test writes, not against whichever
# profile happens to be installed. Asserting on the local config made these tests
# a description of one team's answers -- they failed for anyone else, and failed
# for the same team the day they edited their own repo list.
SAMPLE = """\
# a comment, ignored
product_name: Acme Flow
product_url: https://acme.example.com/
default_window_days: 7

shell_source: ~/Documents/Acme/Shell.html
version_repo: acme-design-docs
shell_path: design-shells/acme/shell

repos:
  - acme/backend
  - acme/services

shared_repos:
  - acme/frontend-monorepo

drop_branch_patterns:
  - drop-*
  - "*_drop_*"
  - main
"""


class TestConfig(unittest.TestCase):
    def setUp(self):
        self._real = paths.CONFIG_PATH
        self._tmp = Path(tempfile.mkdtemp())
        target = self._tmp / "config.yaml"
        target.write_text(SAMPLE, encoding="utf-8")
        paths.CONFIG_PATH = target

    def tearDown(self):
        paths.CONFIG_PATH = self._real
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_skill_dir_resolves_to_skill_root(self):
        self.assertTrue((paths.SKILL_DIR / "lib" / "paths.py").is_file())

    def test_loads_scalar_values(self):
        cfg = paths.load_config()
        self.assertEqual(cfg["product_url"], "https://acme.example.com/")
        self.assertEqual(cfg["default_window_days"], 7)

    def test_loads_lists(self):
        cfg = paths.load_config()
        self.assertIn("acme/backend", cfg["repos"])
        self.assertEqual(len(cfg["repos"]), 2)
        self.assertIn("main", cfg["drop_branch_patterns"])

    def test_shared_repos_are_separate_from_dedicated(self):
        cfg = paths.load_config()
        self.assertIn("acme/frontend-monorepo", cfg["shared_repos"])
        self.assertNotIn("acme/frontend-monorepo", cfg["repos"])

    def test_strips_quotes_from_list_items(self):
        cfg = paths.load_config()
        self.assertIn("*_drop_*", cfg["drop_branch_patterns"])

    def test_shell_source_expands_home(self):
        cfg = paths.load_config()
        self.assertTrue(str(cfg["shell_source"]).startswith("/"))

    def test_the_version_repo_is_left_relative_for_the_team(self):
        """versions.repo_path resolves it against the workspace; the config keeps
        the relative value so one committed setting works on every machine."""
        self.assertEqual(paths.load_config()["version_repo"], "acme-design-docs")


class TestInstalledConfig(unittest.TestCase):
    """Whatever profile is installed here must at least be self-consistent.

    Deliberately does not assert *which* repos: that is the adopter's business.
    It only checks the tooling repos never appear as product repos, which is the
    mistake that puts the skill's own commits into the gap report.
    """

    def test_tooling_repos_are_not_watched_as_product_repos(self):
        if not paths.CONFIG_PATH.is_file():
            self.skipTest("no config.yaml — not yet onboarded")
        for repo in paths.load_config().get("repos") or []:
            self.assertNotIn("claude-harness", repo)
            self.assertNotIn("claude-docs", repo)

class TestRunDir(unittest.TestCase):
    """Redirects RUNS_DIR so tests do not litter the real runs/ directory."""

    def setUp(self):
        self._real = paths.RUNS_DIR
        self._tmp = Path(tempfile.mkdtemp())
        paths.RUNS_DIR = self._tmp

    def tearDown(self):
        paths.RUNS_DIR = self._real
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_run_dir_is_created(self):
        d = paths.run_dir("2026-01-01")
        self.assertTrue(d.is_dir())
        self.assertEqual(d.parent, self._tmp)

    def test_run_dir_includes_manual_screenshot_drop(self):
        d = paths.run_dir("2026-01-02")
        self.assertTrue((d / "live" / "manual").is_dir())
        self.assertTrue((d / "shell").is_dir())

    def test_run_dir_is_idempotent(self):
        first = paths.run_dir("2026-01-03")
        second = paths.run_dir("2026-01-03")
        self.assertEqual(first, second)



class TestSharedPaths(unittest.TestCase):
    """A shared path must mean the same place in every teammate's checkout."""

    def test_relative_resolves_against_the_workspace(self):
        got = paths.resolve_shared("design-docs/shells")
        self.assertEqual(got, (paths.WORKSPACE_DIR / "design-docs/shells").resolve())

    def test_absolute_wins_for_a_different_layout(self):
        self.assertEqual(str(paths.resolve_shared("/opt/shells")), "/opt/shells")

    def test_tilde_is_expanded(self):
        self.assertFalse(str(paths.resolve_shared("~/shells")).startswith("~"))


class TestWorkspaceDiscovery(unittest.TestCase):
    """Both install shapes are four levels deep, so depth cannot tell them apart.

    The team install has the skill inside a git checkout that sits beside other
    checkouts, and a relative version_repo is meant to reach one of them. The
    standalone install at ~/.claude/skills has no siblings; anchoring there would
    resolve relative paths into the user's home directory, or worse, /Users.
    """

    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _skill_at(self, base):
        skill = base / ".claude" / "skills" / "shell-sync"
        skill.mkdir(parents=True)
        return skill

    def test_team_install_anchors_at_the_folder_holding_the_checkouts(self):
        workspace = self._tmp / "workspace"
        repo = workspace / "some-harness"
        skill = self._skill_at(repo)
        (repo / ".git").mkdir()
        self.assertEqual(paths._find_workspace(skill), workspace)

    def test_standalone_install_anchors_at_the_skill_itself(self):
        home = self._tmp / "home"
        skill = self._skill_at(home)          # no .git -- not a checkout
        self.assertEqual(paths._find_workspace(skill), skill)

    def test_a_worktree_still_counts_as_a_checkout(self):
        """git worktrees carry .git as a file, not a directory."""
        workspace = self._tmp / "ws"
        repo = workspace / "harness"
        skill = self._skill_at(repo)
        (repo / ".git").write_text("gitdir: /elsewhere\n", encoding="utf-8")
        self.assertEqual(paths._find_workspace(skill), workspace)

    def test_env_override_wins(self):
        import os

        target = self._tmp / "chosen"
        target.mkdir()
        os.environ["SHELL_SYNC_WORKSPACE"] = str(target)
        try:
            self.assertEqual(paths._find_workspace(self._tmp), target.resolve())
        finally:
            del os.environ["SHELL_SYNC_WORKSPACE"]


if __name__ == "__main__":
    unittest.main()

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR / "lib"))

import onboard  # noqa: E402
import paths  # noqa: E402


def answers(**over):
    base = {
        "slug": "load-testing",
        "product_name": "Load Testing",
        "product_url": "https://load-testing.browserstack.com/",
        "ticket_prefix": "LT",
        "repos": ["browserstack/lt-backend"],
        "shared_repos": ["browserstack/frontend"],
        "product_signals": ["load testing"],
        "drop_branch_patterns": ["main", "master"],
    }
    base.update(over)
    return base


class TestValidate(unittest.TestCase):
    def test_a_complete_answer_set_passes(self):
        self.assertEqual(onboard.validate(answers()), [])

    def test_missing_answers_are_named(self):
        a = answers()
        del a["ticket_prefix"]
        with self.assertRaises(onboard.OnboardError) as c:
            onboard.validate(a)
        self.assertIn("ticket_prefix", str(c.exception))

    def test_prefix_must_look_like_a_jira_key(self):
        for bad in ("lt", "L", "Load-Testing", "12"):
            with self.assertRaises(onboard.OnboardError):
                onboard.validate(answers(ticket_prefix=bad))

    def test_repos_must_be_owner_slash_name(self):
        with self.assertRaises(onboard.OnboardError):
            onboard.validate(answers(repos=["just-a-name"]))

    def test_at_least_one_dedicated_repo(self):
        with self.assertRaises(onboard.OnboardError):
            onboard.validate(answers(repos=[]))

    def test_url_must_be_a_url(self):
        with self.assertRaises(onboard.OnboardError):
            onboard.validate(answers(product_url="load-testing"))

    def test_slug_cannot_escape_the_profiles_directory(self):
        for bad in ("../x", "a/b", "UPPER"):
            with self.assertRaises(onboard.OnboardError):
                onboard.validate(answers(slug=bad))


class TestWarnings(unittest.TestCase):
    """Warnings cover the mistakes that fail silently rather than loudly."""

    def test_missing_trunk_branch_warns(self):
        """The master-vs-main gap once hid an entire shipped feature."""
        w = onboard.validate(answers(drop_branch_patterns=["drop-*"]))
        self.assertTrue(any("trunk" in x for x in w))

    def test_no_shared_repo_warns(self):
        w = onboard.validate(answers(shared_repos=[]))
        self.assertTrue(any("shared monorepo" in x for x in w))

    def test_no_signals_warns(self):
        w = onboard.validate(answers(product_signals=[]))
        self.assertTrue(any("signals" in x for x in w))

    def test_a_good_config_warns_about_nothing(self):
        self.assertEqual(onboard.validate(answers()), [])


class TestRenderAndWrite(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._real = paths.SKILL_DIR
        paths.SKILL_DIR = self.tmp

    def tearDown(self):
        paths.SKILL_DIR = self._real
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def test_written_profile_is_readable_by_the_config_parser(self):
        """The profile must round-trip through the same minimal reader."""
        target = onboard.write(answers())
        real_cfg = paths.CONFIG_PATH
        paths.CONFIG_PATH = target
        try:
            cfg = paths.load_config()
        finally:
            paths.CONFIG_PATH = real_cfg
        self.assertEqual(cfg["ticket_prefix"], "LT")
        self.assertEqual(cfg["repos"], ["browserstack/lt-backend"])
        self.assertEqual(cfg["product_signals"], ["load testing"])
        self.assertIn("main", cfg["drop_branch_patterns"])

    def test_refuses_to_clobber_an_existing_profile(self):
        onboard.write(answers())
        with self.assertRaises(onboard.OnboardError):
            onboard.write(answers())

    def test_overwrite_is_explicit(self):
        onboard.write(answers())
        self.assertTrue(onboard.write(answers(), overwrite=True).is_file())

    def test_defaults_are_filled_for_paths(self):
        target = onboard.write(answers())
        body = target.read_text(encoding="utf-8")
        self.assertIn("version_repo:", body)
        self.assertIn("shell_path:", body)
        self.assertIn("product_slug: load-testing", body)
        self.assertIn("shell_source:", body)

    def test_profile_lands_under_profiles(self):
        target = onboard.write(answers())
        self.assertEqual(target.parent.name, onboard.PROFILES_DIRNAME)
        self.assertEqual(target.name, "load-testing.yaml")


if __name__ == "__main__":
    unittest.main()

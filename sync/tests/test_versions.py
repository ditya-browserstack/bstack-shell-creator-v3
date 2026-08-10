import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR / "lib"))

import bundle  # noqa: E402
import gitstore  # noqa: E402
import paths  # noqa: E402
import versions  # noqa: E402

FIXTURE = SKILL_DIR / "tests" / "fixtures" / "mini-bundle.html"


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo)] + list(args),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
    ).stdout.decode()


class VersionCase(unittest.TestCase):
    """A repo plus a prod-parity build, wired together the way a profile does."""

    PARITY = "<html><body>HEAD\nbuilds\neditor\nFOOT</body></html>\n"

    def setUp(self):
        self.repo = Path(tempfile.mkdtemp())
        git(self.repo, "init", "-q", "-b", "main", ".")
        git(self.repo, "config", "user.email", "t@example.com")
        git(self.repo, "config", "user.name", "Test")
        (self.repo / "README.md").write_text("docs\n", encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "initial")

        # The prod-parity *build* -- plain files, outside git versioning. The host
        # must come from a real unpack: pack() refuses a host with no sentinel, so
        # handing it the whole bundle silently produces an unpackable shell.
        self.shell_dir = Path(tempfile.mkdtemp())
        host, _ = bundle.unpack(FIXTURE.read_text(encoding="utf-8"))
        (self.shell_dir / "host.html").write_text(host, encoding="utf-8")
        (self.shell_dir / "template.html").write_text(self.PARITY, encoding="utf-8")
        self._real_shell = paths.SHELL_DIR
        paths.SHELL_DIR = self.shell_dir

        self.config = {
            "product_name": "Acme Flow",
            "product_slug": "acme",
            "version_repo": str(self.repo),
            "shell_path": "design-shells/acme/shell",
        }

    def tearDown(self):
        paths.SHELL_DIR = self._real_shell
        shutil.rmtree(self.repo, ignore_errors=True)
        shutil.rmtree(self.shell_dir, ignore_errors=True)

    def parity_becomes(self, text):
        (self.shell_dir / "template.html").write_text(text, encoding="utf-8")
        versions.publish_parity(self.config)


class TestNaming(unittest.TestCase):
    def test_rejects_names_that_could_escape_the_namespace(self):
        for bad in ("..", ".", "../x", "/abs", "a/b", ".hidden", "", "UPPER"):
            with self.assertRaises(versions.VersionError):
                versions._check_slug(bad)

    def test_rejects_the_baseline_name(self):
        """prod-parity is the baseline; a version by that name would shadow it."""
        with self.assertRaises(versions.VersionError):
            versions._check_slug("prod-parity")

    def test_accepts_ordinary_names(self):
        for good in ("v1", "v2", "secrets-redesign", "a.b_c-1"):
            self.assertEqual(versions._check_slug(good), good)

    def test_namespaces_by_product(self):
        """Two products in one repo must not collide on `shell/v2`."""
        a = versions.namespace({"product_slug": "acme"})
        b = versions.namespace({"product_slug": "load-testing"})
        self.assertNotEqual(a, b)
        self.assertTrue(a.startswith("shell/"))

    def test_namespace_falls_back_to_the_product_name(self):
        self.assertEqual(
            versions.namespace({"product_name": "Load Testing"}), "shell/load-testing/")


class TestParityPublishing(VersionCase):
    def test_publishing_creates_the_baseline_ref(self):
        versions.publish_parity(self.config)
        self.assertTrue(
            gitstore.ref_exists(self.repo, versions.parity_ref(self.config)))

    def test_the_baseline_branches_off_main_not_an_orphan(self):
        """A version must be relatable to the rest of the repo."""
        versions.publish_parity(self.config)
        base = gitstore.merge_base(
            self.repo, versions.parity_ref(self.config), "main")
        self.assertIsNotNone(base)

    def test_republishing_unchanged_parity_is_a_no_op(self):
        versions.publish_parity(self.config)
        self.assertIsNone(versions.publish_parity(self.config))

    def test_publishing_does_not_move_head(self):
        head = git(self.repo, "rev-parse", "HEAD").strip()
        versions.publish_parity(self.config)
        self.assertEqual(git(self.repo, "rev-parse", "HEAD").strip(), head)


class TestCreate(VersionCase):
    def test_a_new_version_starts_identical_to_parity(self):
        versions.create("v1", "first", self.config)
        self.assertEqual(versions.read_template("v1", self.config), self.PARITY)

    def test_the_label_survives_as_git_history(self):
        versions.create("v1", "secrets redesign", self.config)
        self.assertEqual(
            versions.read_manifest("v1", self.config)["label"], "secrets redesign")

    def test_a_version_with_no_label_is_fine(self):
        versions.create("v1", "", self.config)
        self.assertEqual(versions.read_manifest("v1", self.config)["label"], "")

    def test_duplicate_names_are_refused(self):
        versions.create("v1", "", self.config)
        with self.assertRaises((versions.VersionError, gitstore.GitError)):
            versions.create("v1", "", self.config)

    def test_creating_publishes_parity_if_it_is_missing(self):
        versions.create("v1", "", self.config)
        self.assertTrue(
            gitstore.ref_exists(self.repo, versions.parity_ref(self.config)))

    def test_listing_reports_versions_but_not_the_baseline(self):
        versions.create("v1", "one", self.config)
        versions.create("v2", "two", self.config)
        slugs = [m["slug"] for m in versions.list_versions(self.config)]
        self.assertEqual(slugs, ["v1", "v2"])


class TestImportFromClaudeDesign(VersionCase):
    """Work done in Claude Design comes back as an exported bundle."""

    def _an_export(self, marker):
        host, _ = bundle.unpack(FIXTURE.read_text(encoding="utf-8"))
        template = "<html><body>%s</body></html>\n" % marker
        out = Path(tempfile.mkdtemp()) / "Shell.html"
        out.write_text(bundle.pack(host, template), encoding="utf-8")
        return out, template

    def test_new_from_an_export_holds_the_design_not_prod_parity(self):
        """The two-step version of this silently left prod parity under a v2 name."""
        export, template = self._an_export("MY REDESIGN")
        versions.create("v2", "redesign", self.config, from_export=export)
        self.assertEqual(versions.read_template("v2", self.config), template)

    def test_a_bad_export_leaves_no_half_made_version(self):
        junk = Path(tempfile.mkdtemp()) / "screenshot.html"
        junk.write_text("<html>not an export</html>", encoding="utf-8")
        with self.assertRaises(versions.VersionError):
            versions.create("v2", "", self.config, from_export=junk)
        self.assertFalse(
            gitstore.ref_exists(self.repo, versions.version_ref("v2", self.config)))

    def test_a_missing_export_is_a_clear_error(self):
        with self.assertRaises(versions.VersionError):
            versions.template_from_export("/nope/Shell.html")

    def test_importing_into_an_existing_version_replaces_its_design(self):
        versions.create("v2", "", self.config)
        export, template = self._an_export("SECOND PASS")
        versions.import_into("v2", export, self.config)
        self.assertEqual(versions.read_template("v2", self.config), template)

    def test_reimporting_the_same_export_is_a_no_op(self):
        """Re-exporting without changing anything must not create empty history."""
        export, _ = self._an_export("SAME")
        versions.create("v2", "", self.config, from_export=export)
        self.assertIsNone(versions.import_into("v2", export, self.config))


class TestStaleness(VersionCase):
    def test_a_fresh_version_is_not_behind(self):
        versions.create("v1", "", self.config)
        self.assertEqual(versions.read_manifest("v1", self.config)["behind"], 0)

    def test_prod_changes_make_it_behind(self):
        versions.create("v1", "", self.config)
        self.parity_becomes("<html><body>HEAD+ran-with\nbuilds\neditor\nFOOT</body></html>\n")
        self.assertEqual(versions.read_manifest("v1", self.config)["behind"], 1)

    def test_unrelated_repo_activity_is_not_drift(self):
        """Measured unscoped in a shared repo this read as 58 commits behind."""
        versions.create("v1", "", self.config)
        for i in range(4):
            (self.repo / ("doc%d.md" % i)).write_text("x\n", encoding="utf-8")
            git(self.repo, "add", "-A")
            git(self.repo, "commit", "-qm", "unrelated %d" % i)
        self.assertEqual(versions.read_manifest("v1", self.config)["behind"], 0)

    def test_staleness_ignores_the_ledger_argument_it_still_accepts(self):
        versions.create("v1", "", self.config)
        manifest = versions.read_manifest("v1", self.config)
        self.assertEqual(versions.staleness(manifest, {"features": [{"x": 1}]}), 0)


class TestRefresh(VersionCase):
    def _v1_edits_the_foot(self):
        versions.create("v1", "", self.config)
        versions.write_template(
            "v1", "<html><body>HEAD\nbuilds\neditor\nFOOT+v1</body></html>\n",
            "v1: edit foot", self.config)

    def test_a_clean_refresh_keeps_both_sides(self):
        """The behaviour actually asked for: prod merges in, my edits survive."""
        self._v1_edits_the_foot()
        self.parity_becomes("<html><body>HEAD+ran-with\nbuilds\neditor\nFOOT</body></html>\n")
        status, _ = versions.refresh("v1", self.config)
        self.assertEqual(status, "clean")
        merged = versions.read_template("v1", self.config)
        self.assertIn("HEAD+ran-with", merged)
        self.assertIn("FOOT+v1", merged)

    def test_after_refresh_it_is_no_longer_behind(self):
        self._v1_edits_the_foot()
        self.parity_becomes("<html><body>HEAD+p\nbuilds\neditor\nFOOT</body></html>\n")
        versions.refresh("v1", self.config)
        self.assertEqual(versions.read_manifest("v1", self.config)["behind"], 0)

    def test_a_conflicting_refresh_leaves_the_version_untouched(self):
        versions.create("v1", "", self.config)
        versions.write_template(
            "v1", "<html><body>HEAD\nbuilds-MINE\neditor\nFOOT</body></html>\n",
            "v1: edit builds", self.config)
        before = versions.read_template("v1", self.config)
        self.parity_becomes("<html><body>HEAD\nbuilds-PROD\neditor\nFOOT</body></html>\n")

        status, conflicts = versions.refresh("v1", self.config)
        self.assertEqual(status, "conflict")
        self.assertTrue(conflicts)
        self.assertEqual(versions.read_template("v1", self.config), before)

    def test_refresh_all_reports_each_version_separately(self):
        self._v1_edits_the_foot()
        versions.create("v2", "", self.config)
        versions.write_template(
            "v2", "<html><body>HEAD\nbuilds-MINE\neditor\nFOOT</body></html>\n",
            "v2: edit builds", self.config)
        self.parity_becomes("<html><body>HEAD\nbuilds-PROD\neditor\nFOOT</body></html>\n")

        states = {name: state for name, state, _ in versions.refresh_all(self.config)}
        self.assertEqual(states["v1"], "merged")
        self.assertEqual(states["v2"], "conflict")

    def test_one_conflict_does_not_stop_the_others(self):
        """A single stuck version must not block the rest of the refresh."""
        self._v1_edits_the_foot()
        versions.create("v2", "", self.config)
        versions.write_template(
            "v2", "<html><body>HEAD\nbuilds-MINE\neditor\nFOOT</body></html>\n",
            "v2", self.config)
        self.parity_becomes("<html><body>HEAD\nbuilds-PROD\neditor\nFOOT</body></html>\n")
        versions.refresh_all(self.config)
        self.assertIn("builds-PROD", versions.read_template("v1", self.config))


class TestSharing(VersionCase):
    def test_packs_a_standalone_file(self):
        versions.create("v1", "secrets", self.config)
        out = Path(tempfile.mkdtemp()) / "share.html"
        versions.pack_version("v1", out, self.config)
        self.assertTrue(out.is_file())
        self.assertGreater(out.stat().st_size, 0)

    def test_the_badge_names_the_version_and_says_not_shipped(self):
        versions.create("v1", "secrets", self.config)
        out = Path(tempfile.mkdtemp()) / "share.html"
        body = versions.pack_version("v1", out, self.config).read_text(encoding="utf-8")
        self.assertIn("not shipped", body)
        self.assertIn("secrets", body)

    def test_the_badge_states_drift_so_a_handover_cannot_hide_it(self):
        versions.create("v1", "secrets", self.config)
        self.parity_becomes("<html><body>HEAD+p\nbuilds\neditor\nFOOT</body></html>\n")
        out = Path(tempfile.mkdtemp()) / "share.html"
        body = versions.pack_version("v1", out, self.config).read_text(encoding="utf-8")
        self.assertIn("1 prod change not in this", body)

    def test_a_current_version_gets_no_drift_note(self):
        versions.create("v1", "secrets", self.config)
        out = Path(tempfile.mkdtemp()) / "share.html"
        body = versions.pack_version("v1", out, self.config).read_text(encoding="utf-8")
        self.assertNotIn("prod change", body)


class TestSharing2(VersionCase):
    """A version nobody pushed is invisible to the team and looks fine locally."""

    def setUp(self):
        super().setUp()
        self.remote = Path(tempfile.mkdtemp())
        git(self.remote, "init", "-q", "--bare", ".")
        git(self.repo, "remote", "add", "origin", str(self.remote))

    def tearDown(self):
        shutil.rmtree(self.remote, ignore_errors=True)
        super().tearDown()

    def test_a_new_version_is_not_shared_until_published(self):
        versions.create("v1", "", self.config)
        self.assertFalse(versions.read_manifest("v1", self.config)["shared"])

    def test_publishing_makes_it_shared(self):
        versions.create("v1", "", self.config)
        versions.publish("v1", self.config)
        self.assertTrue(versions.read_manifest("v1", self.config)["shared"])

    def test_editing_after_publishing_makes_it_unshared_again(self):
        """The team has the old commit, so 'shared' must go false until re-pushed."""
        versions.create("v1", "", self.config)
        versions.publish("v1", self.config)
        versions.write_template("v1", "<html><body>changed</body></html>\n",
                                "v1: edit", self.config)
        self.assertFalse(versions.read_manifest("v1", self.config)["shared"])

    def test_publishing_something_that_does_not_exist_is_refused(self):
        with self.assertRaises(versions.VersionError):
            versions.publish("nope", self.config)

    def test_the_baseline_can_be_published_too(self):
        versions.publish_parity(self.config)
        versions.publish(None, self.config)
        self.assertTrue(
            gitstore.is_shared(self.repo, versions.parity_ref(self.config)))


class TestNoRemote(VersionCase):
    def test_nothing_is_shared_when_there_is_no_remote(self):
        versions.create("v1", "", self.config)
        self.assertFalse(versions.read_manifest("v1", self.config)["shared"])

    def test_publishing_without_a_remote_says_so(self):
        versions.create("v1", "", self.config)
        with self.assertRaises((versions.VersionError, gitstore.GitError)):
            versions.publish("v1", self.config)


class TestMissingConfig(unittest.TestCase):
    def test_no_repo_configured_is_a_clear_error(self):
        with self.assertRaises(versions.VersionError) as caught:
            versions.repo_path({"product_name": "Acme"})
        self.assertIn("version_repo", str(caught.exception))

    def test_a_non_repo_path_is_rejected(self):
        tmp = tempfile.mkdtemp()
        with self.assertRaises(versions.VersionError):
            versions.repo_path({"version_repo": tmp, "product_name": "Acme"})

    def test_listing_returns_empty_rather_than_exploding(self):
        """`check` must still run on a machine that has not configured this."""
        self.assertEqual(versions.list_versions({"product_name": "Acme"}), [])


if __name__ == "__main__":
    unittest.main()

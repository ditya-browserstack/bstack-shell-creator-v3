import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR / "lib"))

import gitstore  # noqa: E402

SHELL = "design-shells/acme/shell/template.html"


def git(repo, *args, **kw):
    return subprocess.run(
        ["git", "-C", str(repo)] + list(args),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, **kw
    ).stdout.decode()


class RepoCase(unittest.TestCase):
    """A repo shaped like the real one: shell content plus unrelated docs."""

    def setUp(self):
        self.repo = Path(tempfile.mkdtemp())
        git(self.repo, "init", "-q", "-b", "parity", ".")
        git(self.repo, "config", "user.email", "t@example.com")
        git(self.repo, "config", "user.name", "Test")
        target = self.repo / SHELL
        target.parent.mkdir(parents=True)
        target.write_text("HEAD\nbuilds\neditor\nFOOT\n", encoding="utf-8")
        (self.repo / "unrelated.md").write_text("docs\n", encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "parity: initial")

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def parity_says(self, text):
        (self.repo / SHELL).write_text(text, encoding="utf-8")
        git(self.repo, "commit", "-qam", "parity: update")


class TestReading(RepoCase):
    def test_reads_a_file_at_a_ref(self):
        self.assertIn("builds", gitstore.read_file(self.repo, "parity", SHELL))

    def test_missing_file_raises_rather_than_returning_empty(self):
        with self.assertRaises(gitstore.GitError):
            gitstore.read_file(self.repo, "parity", "nope.html")

    def test_resolve_returns_none_for_an_unknown_ref(self):
        self.assertIsNone(gitstore.resolve(self.repo, "shell/acme/nope"))


class TestWritingWithoutTouchingTheWorktree(RepoCase):
    """The invariant the whole design rests on."""

    def test_commit_file_leaves_head_and_the_worktree_alone(self):
        head_before = git(self.repo, "rev-parse", "HEAD").strip()
        branch_before = git(self.repo, "rev-parse", "--abbrev-ref", "HEAD").strip()
        on_disk_before = (self.repo / SHELL).read_text(encoding="utf-8")

        gitstore.commit_file(self.repo, "shell/acme/v2", SHELL, "V2 CONTENT\n",
                             "v2: edit", base_ref="parity")

        self.assertEqual(git(self.repo, "rev-parse", "HEAD").strip(), head_before)
        self.assertEqual(
            git(self.repo, "rev-parse", "--abbrev-ref", "HEAD").strip(), branch_before)
        self.assertEqual((self.repo / SHELL).read_text(encoding="utf-8"), on_disk_before)

    def test_the_written_content_is_readable_back_from_the_ref(self):
        gitstore.commit_file(self.repo, "shell/acme/v2", SHELL, "V2 CONTENT\n",
                             "v2: edit", base_ref="parity")
        self.assertEqual(
            gitstore.read_file(self.repo, "shell/acme/v2", SHELL), "V2 CONTENT\n")

    def test_writing_works_with_a_dirty_worktree(self):
        """A designer with unsaved edits must not block a version write."""
        (self.repo / "unrelated.md").write_text("uncommitted edit\n", encoding="utf-8")
        gitstore.commit_file(self.repo, "shell/acme/v2", SHELL, "X\n", "v2",
                             base_ref="parity")
        self.assertEqual(
            (self.repo / "unrelated.md").read_text(encoding="utf-8"),
            "uncommitted edit\n",
        )

    def test_the_real_index_is_not_disturbed(self):
        (self.repo / "staged.md").write_text("staged\n", encoding="utf-8")
        git(self.repo, "add", "staged.md")
        gitstore.commit_file(self.repo, "shell/acme/v2", SHELL, "X\n", "v2",
                             base_ref="parity")
        staged = git(self.repo, "diff", "--cached", "--name-only").strip()
        self.assertEqual(staged, "staged.md")

    def test_other_files_survive_a_write(self):
        """The tree is seeded from the base, not built from the one file."""
        gitstore.commit_file(self.repo, "shell/acme/v2", SHELL, "X\n", "v2",
                             base_ref="parity")
        self.assertEqual(
            gitstore.read_file(self.repo, "shell/acme/v2", "unrelated.md"), "docs\n")


class TestForking(RepoCase):
    def test_fork_records_its_label_in_the_first_commit(self):
        gitstore.branch_from(self.repo, "shell/acme/v2", "parity",
                             "version v2 — secrets redesign")
        subject = git(self.repo, "log", "-1", "--format=%s", "shell/acme/v2").strip()
        self.assertEqual(subject, "version v2 — secrets redesign")

    def test_fork_starts_identical_to_parity(self):
        gitstore.branch_from(self.repo, "shell/acme/v2", "parity", "version v2")
        self.assertEqual(
            gitstore.read_file(self.repo, "shell/acme/v2", SHELL),
            gitstore.read_file(self.repo, "parity", SHELL),
        )

    def test_forking_twice_is_refused(self):
        gitstore.branch_from(self.repo, "shell/acme/v2", "parity", "v2")
        with self.assertRaises(gitstore.GitError):
            gitstore.branch_from(self.repo, "shell/acme/v2", "parity", "v2 again")

    def test_listing_finds_versions_under_the_namespace(self):
        gitstore.branch_from(self.repo, "shell/acme/v1", "parity", "one")
        gitstore.branch_from(self.repo, "shell/acme/v2", "parity", "two")
        gitstore.branch_from(self.repo, "shell/other/v1", "parity", "another product")
        names = [r[0] for r in gitstore.list_refs(self.repo, "shell/acme/")]
        self.assertEqual(sorted(names), ["shell/acme/v1", "shell/acme/v2"])


class TestRefGlobbing(RepoCase):
    """Ref names here are two levels deep: shell/<product>/<name>.

    git's two glob syntaxes disagree about that, which is a genuine trap:
    `for-each-ref 'refs/heads/shell/*'` matches **nothing**, because a single
    star there does not cross a slash. A push refspec's star does. Listing must
    therefore glob at the full namespace depth, and this pins it -- a listing
    that silently returns zero versions reads as "you have none".
    """

    def test_listing_finds_refs_nested_two_levels_deep(self):
        gitstore.branch_from(self.repo, "shell/acme/v1", "parity", "one")
        names = [r[0] for r in gitstore.list_refs(self.repo, "shell/acme/")]
        self.assertEqual(names, ["shell/acme/v1"])

    def test_a_shallow_glob_would_have_missed_them(self):
        gitstore.branch_from(self.repo, "shell/acme/v1", "parity", "one")
        shallow = git(self.repo, "for-each-ref", "--format=%(refname)",
                      "refs/heads/shell/*").strip()
        self.assertEqual(shallow, "", "if this ever matches, the note above is stale")

    def test_listing_does_not_leak_another_products_versions(self):
        gitstore.branch_from(self.repo, "shell/acme/v1", "parity", "one")
        gitstore.branch_from(self.repo, "shell/acme-extra/v1", "parity", "other")
        names = [r[0] for r in gitstore.list_refs(self.repo, "shell/acme/")]
        self.assertEqual(names, ["shell/acme/v1"])


class TestBehindCount(RepoCase):
    """Unscoped counting is actively misleading in a shared repo."""

    def test_a_fresh_fork_is_not_behind(self):
        gitstore.branch_from(self.repo, "shell/acme/v2", "parity", "v2")
        self.assertEqual(
            gitstore.behind_count(self.repo, "shell/acme/v2", "parity", SHELL), 0)

    def test_counts_prod_changes_to_the_shell(self):
        gitstore.branch_from(self.repo, "shell/acme/v2", "parity", "v2")
        self.parity_says("HEAD\nbuilds+ran-with\neditor\nFOOT\n")
        self.parity_says("HEAD\nbuilds+ran-with\neditor+lock\nFOOT\n")
        self.assertEqual(
            gitstore.behind_count(self.repo, "shell/acme/v2", "parity", SHELL), 2)

    def test_unrelated_commits_do_not_count_as_drift(self):
        """The failure this prevents: 58 commits behind, none of them the shell."""
        gitstore.branch_from(self.repo, "shell/acme/v2", "parity", "v2")
        for i in range(5):
            (self.repo / ("doc%d.md" % i)).write_text("x\n", encoding="utf-8")
            git(self.repo, "add", "-A")
            git(self.repo, "commit", "-qm", "unrelated %d" % i)
        self.assertEqual(
            gitstore.behind_count(self.repo, "shell/acme/v2", "parity"), 5)
        self.assertEqual(
            gitstore.behind_count(self.repo, "shell/acme/v2", "parity", SHELL), 0)


class TestMerge(RepoCase):
    def test_a_clean_merge_brings_prod_changes_in(self):
        gitstore.branch_from(self.repo, "shell/acme/v2", "parity", "v2")
        # the version edits the foot, prod edits the head -- different regions
        gitstore.commit_file(self.repo, "shell/acme/v2", SHELL,
                             "HEAD\nbuilds\neditor\nFOOT+v2\n", "v2: edit foot")
        self.parity_says("HEAD+ran-with\nbuilds\neditor\nFOOT\n")

        status, _ = gitstore.merge(self.repo, "shell/acme/v2", "parity", "merge")
        self.assertEqual(status, "clean")
        merged = gitstore.read_file(self.repo, "shell/acme/v2", SHELL)
        self.assertIn("HEAD+ran-with", merged, "prod change must arrive")
        self.assertIn("FOOT+v2", merged, "the version's own edit must survive")

    def test_a_conflict_changes_nothing(self):
        """Safety property: an automatic merge must never mangle design work."""
        gitstore.branch_from(self.repo, "shell/acme/v2", "parity", "v2")
        gitstore.commit_file(self.repo, "shell/acme/v2", SHELL,
                             "HEAD\nbuilds-V2-VERSION\neditor\nFOOT\n", "v2: edit")
        before = gitstore.resolve(self.repo, "shell/acme/v2")
        self.parity_says("HEAD\nbuilds-PROD-VERSION\neditor\nFOOT\n")

        status, conflicts = gitstore.merge(self.repo, "shell/acme/v2", "parity", "merge")
        self.assertEqual(status, "conflict")
        self.assertIn(SHELL, conflicts)
        self.assertEqual(gitstore.resolve(self.repo, "shell/acme/v2"), before,
                         "the version ref must not move on conflict")
        self.assertIn("builds-V2-VERSION",
                      gitstore.read_file(self.repo, "shell/acme/v2", SHELL))

    def test_merging_when_already_up_to_date_is_a_no_op(self):
        gitstore.branch_from(self.repo, "shell/acme/v2", "parity", "v2")
        before = gitstore.resolve(self.repo, "shell/acme/v2")
        status, sha = gitstore.merge(self.repo, "shell/acme/v2", "parity", "merge")
        self.assertEqual(status, "clean")
        self.assertEqual(sha, before)

    def test_merge_does_not_move_head(self):
        gitstore.branch_from(self.repo, "shell/acme/v2", "parity", "v2")
        gitstore.commit_file(self.repo, "shell/acme/v2", SHELL,
                             "HEAD\nbuilds\neditor\nFOOT+v2\n", "v2")
        self.parity_says("HEAD+p\nbuilds\neditor\nFOOT\n")
        head_before = git(self.repo, "rev-parse", "HEAD").strip()
        gitstore.merge(self.repo, "shell/acme/v2", "parity", "merge")
        self.assertEqual(git(self.repo, "rev-parse", "HEAD").strip(), head_before)

    def test_after_a_clean_merge_the_version_is_no_longer_behind(self):
        gitstore.branch_from(self.repo, "shell/acme/v2", "parity", "v2")
        gitstore.commit_file(self.repo, "shell/acme/v2", SHELL,
                             "HEAD\nbuilds\neditor\nFOOT+v2\n", "v2")
        self.parity_says("HEAD+p\nbuilds\neditor\nFOOT\n")
        gitstore.merge(self.repo, "shell/acme/v2", "parity", "merge")
        self.assertEqual(
            gitstore.behind_count(self.repo, "shell/acme/v2", "parity", SHELL), 0)


class TestGitVersion(unittest.TestCase):
    def test_this_machine_can_merge_without_a_worktree(self):
        self.assertGreaterEqual(gitstore.git_version(), gitstore.MIN_GIT)


if __name__ == "__main__":
    unittest.main()

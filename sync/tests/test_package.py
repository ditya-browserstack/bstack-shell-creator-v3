import re
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR / "lib"))

import package  # noqa: E402


class TestCollect(unittest.TestCase):
    """What ships is an allow-list, and the point is what it leaves out."""

    def setUp(self):
        self.names = [arc for arc, _ in package.collect()]

    def test_ships_the_tool(self):
        self.assertIn("SKILL.md", self.names)
        self.assertIn("lib/bundle.py", self.names)
        self.assertIn("tests/test_bundle.py", self.names)

    def test_ships_no_shell(self):
        """5 MB of one team's product is the biggest thing not to leak."""
        self.assertFalse([n for n in self.names if n.startswith("shell/")])

    def test_ships_no_profile_or_history(self):
        for prefix in ("config.yaml", "ledger/", "profiles/", "runs/", "boards.json"):
            self.assertFalse(
                [n for n in self.names if n.startswith(prefix)],
                "%s must not ship" % prefix,
            )

    def test_ships_no_bytecode(self):
        self.assertFalse([n for n in self.names if n.endswith(".pyc")])
        self.assertFalse([n for n in self.names if "__pycache__" in n])


class TestAudit(unittest.TestCase):
    """The audit is the backstop. If it stops catching things, the zip leaks.

    The sample strings below are assembled at runtime rather than written out.
    This file ships inside the package, so a literal would make the audit flag its
    own test -- and the fix for that must never be "exclude this file", which is a
    hole. Assembling keeps the shipped file genuinely clean while still exercising
    the real regex.
    """

    ORG = "browser" + "stack"
    PRODUCT = "app" + "-lca"
    HOST = "app-low" + "-code." + "browserstack.com"

    def _write(self, text):
        tmp = Path(tempfile.mkdtemp()) / "f.py"
        tmp.write_text(text, encoding="utf-8")
        return [("f.py", tmp)]

    def test_flags_the_originating_repos(self):
        line = "clone %s/%s-claude-docs\n" % (self.ORG, "app-" + "lcnc")
        self.assertEqual(len(package.audit(self._write(line))), 1)

    def test_flags_the_product_name_in_any_casing(self):
        base = self.PRODUCT
        for spelling in (base, base.upper(), base.replace("-", " ").title(),
                         base.replace("-", "_"), base.replace("-", "")):
            self.assertTrue(package.audit(self._write(spelling)), spelling)

    def test_flags_the_product_url(self):
        self.assertTrue(package.audit(self._write("https://%s/" % self.HOST)))

    def test_passes_clean_text(self):
        self.assertEqual(package.audit(self._write("a generic tool\n")), [])

    def test_the_real_package_is_clean(self):
        """The one that matters: nothing shipped today names the originating team."""
        hits = package.audit(package.collect())
        self.assertEqual(
            hits, [], "\n".join("%s:%s %s" % h for h in hits)
        )


class TestBuild(unittest.TestCase):
    def test_refuses_to_write_when_something_leaks(self):
        """Strict by default: a leak must stop the build, not warn after it."""
        leaky = Path(tempfile.mkdtemp())
        (leaky / "lib").mkdir()
        (leaky / "SKILL.md").write_text(
            "built for %s" % TestAudit.PRODUCT, encoding="utf-8"
        )
        out = Path(tempfile.mkdtemp()) / "x.zip"
        with self.assertRaises(package.PackageError):
            package.build(out, skill_dir=leaky)
        self.assertFalse(out.exists(), "nothing may be written on refusal")

    def test_writes_a_usable_zip(self):
        out = Path(tempfile.mkdtemp()) / "shell-sync.zip"
        package.build(out)
        with zipfile.ZipFile(out) as zf:
            names = zf.namelist()
            self.assertTrue(all(n.startswith("shell-sync/") for n in names))
            self.assertIn("shell-sync/install.sh", names)
            self.assertIn("shell-sync/README.md", names)
            self.assertEqual(zf.testzip(), None)

    def test_installer_is_executable(self):
        """Without the mode bit, `bash install.sh` still works but `./install.sh` does not."""
        out = Path(tempfile.mkdtemp()) / "shell-sync.zip"
        package.build(out)
        with zipfile.ZipFile(out) as zf:
            mode = zf.getinfo("shell-sync/install.sh").external_attr >> 16
        self.assertTrue(mode & 0o111, oct(mode))


class TestDocumentationMatchesThePackage(unittest.TestCase):
    """adopt.html tells the recipient what each shipped file is for.

    That list is prose, so nothing stops it drifting as modules are added -- and a
    document confidently describing a folder that no longer looks like that is
    worse than one that says nothing. This fails the day they disagree.
    """

    def setUp(self):
        self.doc = (SKILL_DIR / "adopt.html").read_text(encoding="utf-8")
        self.shipped = [arc for arc, _ in package.collect()]

    def test_every_shipped_module_is_described(self):
        modules = [Path(n).name for n in self.shipped if n.startswith("lib/")]
        missing = [m for m in modules if m not in self.doc]
        self.assertEqual(missing, [], "undocumented in adopt.html: %s" % missing)

    def test_no_module_is_described_that_is_not_shipped(self):
        """The other direction: a file listed but removed reads as a broken package."""
        shipped = {Path(n).name for n in self.shipped if n.startswith("lib/")}
        described = set(re.findall(r"<code>([a-z_]+\.(?:py|mjs))</code>", self.doc))
        self.assertEqual(described - shipped - {"install.sh"}, set())

    def test_the_stated_file_counts_are_right(self):
        libs = len([n for n in self.shipped if n.startswith("lib/")])
        tests = len([n for n in self.shipped if n.startswith("tests/")])
        self.assertIn("%d files" % libs, self.doc, "lib/ count is wrong: %d" % libs)
        self.assertIn("%d files" % tests, self.doc, "tests/ count is wrong: %d" % tests)


if __name__ == "__main__":
    unittest.main()

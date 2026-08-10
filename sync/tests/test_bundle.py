import json
import unittest
from pathlib import Path
import sys

SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR / "lib"))

import bundle  # noqa: E402

FIXTURE = SKILL_DIR / "tests" / "fixtures" / "mini-bundle.html"
ESC = chr(92) + "u002F"


class TestRoundTrip(unittest.TestCase):
    def setUp(self):
        self.src = FIXTURE.read_text(encoding="utf-8")

    def test_identity_round_trip(self):
        host, template = bundle.unpack(self.src)
        self.assertEqual(bundle.pack(host, template), self.src)

    def test_host_preserves_manifest_verbatim(self):
        host, _ = bundle.unpack(self.src)
        self.assertIn('"uuid-1"', host)
        self.assertIn(bundle.SENTINEL, host)

    def test_template_is_decoded_source(self):
        _, template = bundle.unpack(self.src)
        self.assertIn("class Component extends DCLogic", template)
        self.assertIn("</script>", template)
        self.assertNotIn(ESC, template)

    def test_packed_output_escapes_closing_tags(self):
        host, template = bundle.unpack(self.src)
        packed = bundle.pack(host, template)
        start = packed.index('<script type="__bundler/template">')
        end = packed.index("</script>", start)
        region = packed[start:end]
        self.assertIn("<" + ESC + "script>", region)

    def test_packed_output_keeps_bare_slash_in_css_comment(self):
        host, template = bundle.unpack(self.src)
        packed = bundle.pack(host, template)
        self.assertIn("/* DesignStack", packed)

    def test_em_dash_survives_unescaped(self):
        host, template = bundle.unpack(self.src)
        packed = bundle.pack(host, template)
        self.assertIn("—", packed)
        self.assertNotIn(chr(92) + "u2014", packed)


class TestEditThenPack(unittest.TestCase):
    def test_edited_template_packs_and_reparses(self):
        src = FIXTURE.read_text(encoding="utf-8")
        host, template = bundle.unpack(src)
        edited = template.replace("{{ title }}", "{{ title }}<b>NEW</b>")
        packed = bundle.pack(host, edited)
        _, reparsed = bundle.unpack(packed)
        self.assertEqual(reparsed, edited)
        self.assertIn("<b>NEW</b>", reparsed)


class TestErrors(unittest.TestCase):
    def test_missing_template_script_raises(self):
        with self.assertRaises(bundle.BundleError):
            bundle.unpack("<html><body>no template here</body></html>")

    def test_sentinel_already_present_raises(self):
        src = FIXTURE.read_text(encoding="utf-8")
        with self.assertRaises(bundle.BundleError):
            bundle.unpack(src.replace("<body>", "<body>" + bundle.SENTINEL))

    def test_pack_without_sentinel_raises(self):
        with self.assertRaises(bundle.BundleError):
            bundle.pack("<html>no sentinel</html>", "tpl")


if __name__ == "__main__":
    unittest.main()

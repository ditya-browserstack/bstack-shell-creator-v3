import unittest
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR / "lib"))

import index  # noqa: E402

REAL_TEMPLATE = SKILL_DIR / "shell" / "template.html"

SAMPLE = """
<x-dc>
<div>Run test</div>
<sc-if cond="screen === 'editor'"><span>Editor here</span></sc-if>
<sc-if cond="screen === 'list'"><span>List here</span></sc-if>
</x-dc>
<script type="text/x-dc" data-dc-script="">
class Component extends DCLogic {
  state = {
    title: 'Untitled test',
    screen: 'editor',
    steps: []
  };

  catalog() {
    return [
      { name: 'Gestures', items: [
        { icon: 'touch_app', label: 'Tap on element', desc: 'Tap an element' },
        { icon: 'ads_click', label: 'Double tap', desc: 'Double tap an element' }
      ] },
      { name: 'Input', items: [
        { icon: 'keyboard', label: 'Type text', desc: 'Type into a field' }
      ] }
    ];
  }

  showToast(msg) { }
}
</script>
"""


class TestBuildFromSample(unittest.TestCase):
    def setUp(self):
        self.idx = index.build(SAMPLE)

    def test_extracts_catalog_groups(self):
        self.assertEqual(self.idx["catalog_groups"], ["Gestures", "Input"])

    def test_extracts_catalog_labels(self):
        self.assertIn("Tap on element", self.idx["catalog_labels"])
        self.assertIn("Type text", self.idx["catalog_labels"])

    def test_extracts_screens(self):
        self.assertEqual(sorted(self.idx["screens"]), ["editor", "list"])

    def test_extracts_state_keys(self):
        self.assertIn("title", self.idx["state_keys"])
        self.assertIn("screen", self.idx["state_keys"])

    def test_extracts_methods(self):
        self.assertIn("catalog", self.idx["methods"])
        self.assertIn("showToast", self.idx["methods"])

    def test_extracts_markup_labels(self):
        self.assertIn("Run test", self.idx["markup_labels"])


class TestNormalize(unittest.TestCase):
    def test_lowercases_and_collapses_space(self):
        self.assertEqual(index.normalize("  Tap  On   Element "), "tap on element")

    def test_strips_punctuation(self):
        self.assertEqual(index.normalize("Swipe up!"), "swipe up")


class TestStateShapes(unittest.TestCase):
    """Shells write the state initializer in more than one shape."""

    def test_single_line_state_block(self):
        # The session shell writes state on one line. A regex anchored on a
        # closing "\n  };" silently returned no keys at all for this form.
        src = "state = { hover: null, px: 300, sel: [], screen: 'home' };"
        self.assertEqual(
            index.build(src)["state_keys"], ["hover", "px", "sel", "screen"]
        )

    def test_nested_values_do_not_leak_keys(self):
        src = "state = { a: { inner: 1 }, b: [{ deep: 2 }], c: 3 };"
        self.assertEqual(index.build(src)["state_keys"], ["a", "b", "c"])

    def test_braces_inside_strings_are_ignored(self):
        src = "state = { tpl: 'a { b } c', done: true };"
        self.assertEqual(index.build(src)["state_keys"], ["tpl", "done"])

    def test_setstate_keys_are_included(self):
        src = "state = { a: 1 };\nthis.setState({ exitOpen: false });"
        self.assertIn("exitOpen", index.build(src)["state_keys"])

    def test_catalogless_template_does_not_crash(self):
        idx = index.build("<x-dc><div>Hello</div></x-dc>")
        self.assertEqual(idx["catalog_labels"], [])
        self.assertEqual(idx["catalog_groups"], [])
        self.assertIn("Hello", idx["markup_labels"])


class TestIconFiltering(unittest.TestCase):
    def test_icon_glyph_names_are_not_labels(self):
        src = '<div><span class="icon" style="x">close</span>Disconnected</div>'
        idx = index.build(src)
        self.assertNotIn("close", idx["markup_labels"])
        self.assertIn("Disconnected", idx["markup_labels"])

    def test_label_immediately_after_an_icon_survives(self):
        # The real shell writes <span class="icon">check</span>Complete test.
        src = '<div><span class="icon">check</span>Complete test</div>'
        self.assertIn("Complete test", index.build(src)["markup_labels"])

    def test_label_matching_an_icon_name_by_case_survives(self):
        src = '<span class="icon">delete</span><button>Delete</button>'
        labels = index.build(src)["markup_labels"]
        self.assertIn("Delete", labels)
        self.assertNotIn("delete", labels)


class TestScriptExclusion(unittest.TestCase):
    def test_javascript_comparisons_are_not_labels(self):
        # ">=" inside logic used to be harvested as if it were UI text.
        src = ('<div>Real label</div>'
               '<script type="text/x-dc">if (a >= b && c) { d(); }</script>')
        labels = index.build(src)["markup_labels"]
        self.assertIn("Real label", labels)
        self.assertEqual([l for l in labels if "&&" in l or l.startswith("=")], [])

    def test_state_is_still_read_from_inside_the_script(self):
        src = '<script type="text/x-dc">state = { screen: \'home\' };</script>'
        self.assertIn("screen", index.build(src)["state_keys"])


class TestRealShell(unittest.TestCase):
    """Asserts against whatever shell config.yaml currently points at.

    Kept shell-agnostic on purpose: the two known exports differ completely in
    shape, so these check invariants plus a few strings from the configured file
    rather than one export's catalog.
    """

    def setUp(self):
        if not REAL_TEMPLATE.is_file():
            self.skipTest("shell/template.html not initialized (run Task 2)")
        self.idx = index.build(REAL_TEMPLATE.read_text(encoding="utf-8"))

    def test_index_has_every_key(self):
        for key in ("catalog_groups", "catalog_labels", "screens",
                    "state_keys", "methods", "markup_labels"):
            self.assertIn(key, self.idx)

    def test_has_a_usable_feature_signal(self):
        # Either a command catalog or markup text must be populated, or nothing
        # downstream can decide presence.
        self.assertTrue(self.idx["catalog_labels"] or self.idx["markup_labels"])

    def test_screen_state_is_discovered(self):
        self.assertIn("screen", self.idx["state_keys"])
        self.assertTrue(self.idx["screens"])

    def test_no_icon_glyph_names_in_labels(self):
        for glyph in ("close", "add", "arrow_back", "more_vert", "refresh"):
            self.assertNotIn(glyph, self.idx["markup_labels"])

    def test_known_session_shell_strings(self):
        for label in ("Test configuration", "Save test", "Complete test"):
            self.assertIn(label, self.idx["markup_labels"])


if __name__ == "__main__":
    unittest.main()

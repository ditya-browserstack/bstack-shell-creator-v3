import json
import shutil
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR / "lib"))

import storyboard  # noqa: E402

REAL_TEMPLATE = SKILL_DIR / "shell" / "template.html"

# A 1x1 transparent PNG, so card building can be exercised without a browser.
TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000a49444154789c6300010000050001"
    "0d0a2db40000000049454e44ae426082"
)


class TestGateRegion(unittest.TestCase):
    def test_unknown_gate_returns_empty(self):
        self.assertEqual(storyboard.gate_region("<div>nothing</div>", "nope"), "")

    def test_region_stops_at_the_matching_close_not_the_first(self):
        """Nested sc-if blocks are the norm in this shell; a naive match truncates."""
        template = (
            '<sc-if value="{{ outer }}">A'
            '<sc-if value="{{ inner }}">B</sc-if>'
            "C</sc-if>TAIL"
        )
        region = storyboard.gate_region(template, "outer")
        self.assertIn("A", region)
        self.assertIn("B", region)
        self.assertIn("C", region)
        self.assertNotIn("TAIL", region)

    def test_unterminated_region_returns_remainder_rather_than_raising(self):
        region = storyboard.gate_region('<sc-if value="{{ x }}">body', "x")
        self.assertIn("body", region)


class TestComponents(unittest.TestCase):
    def test_detects_pill_regardless_of_declaration_order(self):
        for markup in (
            'style="border-radius:9999px;padding:4px 12px;"',
            'style="padding:4px 12px;border-radius:9999px;"',
            "borderRadius: 9999, padding: '5px 14px'",
        ):
            self.assertIn("Badge", storyboard.components_in(markup), markup)

    def test_detects_table_and_tooltip(self):
        self.assertIn("Table", storyboard.components_in("letter-spacing:0.06em"))
        self.assertIn("Tooltip", storyboard.components_in("background:#1F2937"))

    def test_reports_nothing_for_plain_markup(self):
        self.assertEqual(storyboard.components_in("<div>hello</div>"), [])


class TestExpandRegion(unittest.TestCase):
    def test_pulls_in_computed_style_definitions(self):
        """Half the shell's styling is computed; scanning markup alone misses it."""
        template = (
            '<sc-if value="{{ g }}"><span style="{{ tagStyle }}">x</span></sc-if>'
            "\ntagStyle: { borderRadius: 9999, padding: '5px 14px' },"
        )
        region = storyboard.gate_region(template, "g")
        self.assertNotIn("Badge", storyboard.components_in(region))
        expanded = storyboard.expand_region(template, region)
        self.assertIn("Badge", storyboard.components_in(expanded))

    def test_handles_dotted_interpolations(self):
        template = '<sc-if value="{{ g }}">{{ a.rowStyle }}</sc-if>\nrowStyle: { x: 1 },'
        region = storyboard.gate_region(template, "g")
        self.assertIn("rowStyle", storyboard.expand_region(template, region))


class TestActionsAndHeading(unittest.TestCase):
    def test_extracts_button_labels_in_order_without_duplicates(self):
        region = "<button>Save test suite</button><button>Discard</button><button>Discard</button>"
        self.assertEqual(storyboard.actions_in(region), ["Save test suite", "Discard"])

    def test_ignores_interpolated_headings(self):
        self.assertEqual(storyboard.heading_in("<h1>{{ dynamic }}</h1>"), "")

    def test_reads_a_literal_heading(self):
        self.assertEqual(storyboard.heading_in('<h1 style="x">Builds</h1>'), "Builds")


class TestFeatures(unittest.TestCase):
    def setUp(self):
        self.ledger = {
            "features": [
                {"lcam_id": "LCAM-2580", "name": "Ran with column", "surface": "builds"},
                {"lcam_id": "LCAM-2580", "name": "SA tag", "surface": "suite-config"},
                {"lcam_id": "LCAM-9", "name": "No surface", "surface": ""},
            ]
        }

    def _screen(self, slug):
        return {"slug": slug}

    def test_matches_surface_to_slug(self):
        found = storyboard.features_for(self._screen("builds"), self.ledger)
        self.assertEqual([f["name"] for f in found], ["Ran with column"])

    def test_matches_when_slug_is_longer_than_surface(self):
        found = storyboard.features_for(self._screen("suite-config"), self.ledger)
        self.assertEqual([f["name"] for f in found], ["SA tag"])

    def test_blank_surface_never_matches(self):
        for slug in ("builds", "tests", "secrets"):
            names = [f["name"] for f in storyboard.features_for(self._screen(slug), self.ledger)]
            self.assertNotIn("No surface", names)


class TestScreenMap(unittest.TestCase):
    """Guards the screen map against the shell it claims to describe.

    This caught two wrong entries when the first map was written: one screen
    pointed at a state the screen does not actually render under, and another
    expected "Test dataset" where the heading reads "Test Dataset". Without this
    test both would have produced confidently mislabelled cards.

    Skipped on a fresh install, where there is no shell yet -- run it again once
    you have imported your export and written your map. It is the check that tells
    you the map is right before you spend a capture run finding out it is not.
    """

    @classmethod
    def setUpClass(cls):
        if not REAL_TEMPLATE.is_file():
            raise unittest.SkipTest(
                "no shell imported yet — nothing for the screen map to describe"
            )
        cls.template = REAL_TEMPLATE.read_text(encoding="utf-8")

    def test_every_gate_exists_in_the_shell(self):
        for screen in storyboard.SCREENS:
            region = storyboard.gate_region(self.template, screen["gate"])
            self.assertTrue(region, "no region for gate %s" % screen["gate"])

    def test_every_verify_string_is_inside_its_own_region(self):
        for screen in storyboard.SCREENS:
            region = storyboard.gate_region(self.template, screen["gate"])
            self.assertIn(
                screen["verify"],
                region,
                "%s: %r not under gate %s" % (screen["slug"], screen["verify"], screen["gate"]),
            )

    def test_slugs_are_unique(self):
        slugs = [s["slug"] for s in storyboard.SCREENS]
        self.assertEqual(len(slugs), len(set(slugs)))

    def test_every_screen_declares_a_nav_path(self):
        for screen in storyboard.SCREENS:
            self.assertTrue(screen["nav"], screen["slug"])


class TestBuildBundle(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.shots = self.tmp / "shots"
        self.shots.mkdir()
        self.out = self.tmp / "cards"
        self.template = (
            '<sc-if value="{{ buildsListOpen }}">Search by build name'
            '<button>Filters</button></sc-if>'
        )
        self.ledger = {
            "features": [{"lcam_id": "LCAM-2580", "name": "Ran with", "surface": "builds"}]
        }

    def tearDown(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def _shot(self, slug):
        (self.shots / ("%s.png" % slug)).write_bytes(TINY_PNG)
        return self.shots / ("%s.png" % slug)

    def test_builds_a_card_per_captured_screen(self):
        shots = {"builds": self._shot("builds")}
        written = storyboard.build_bundle(
            self.out, shots, self.template, self.ledger, "prod parity"
        )
        self.assertEqual(len(written), 1)
        self.assertTrue((self.out / "shell-builds.html").is_file())

    def test_uncaptured_screens_are_skipped_not_placeholdered(self):
        """A blank artboard reads as 'this screen is empty', which is worse than absent."""
        written = storyboard.build_bundle(
            self.out, {}, self.template, self.ledger, "prod parity"
        )
        self.assertEqual(written, [])

    def test_dscard_marker_is_the_first_line(self):
        storyboard.build_bundle(
            self.out, {"builds": self._shot("builds")}, self.template, self.ledger, "x"
        )
        first = (self.out / "shell-builds.html").read_text(encoding="utf-8").splitlines()[0]
        self.assertTrue(first.startswith("<!-- @dsCard group="))

    def test_card_embeds_the_screenshot_as_a_data_uri(self):
        storyboard.build_bundle(
            self.out, {"builds": self._shot("builds")}, self.template, self.ledger, "x"
        )
        body = (self.out / "shell-builds.html").read_text(encoding="utf-8")
        self.assertIn("data:image/png;base64,", body)

    def test_card_carries_the_dev_notes(self):
        storyboard.build_bundle(
            self.out, {"builds": self._shot("builds")}, self.template, self.ledger, "x"
        )
        body = (self.out / "shell-builds.html").read_text(encoding="utf-8")
        self.assertIn("Ran with", body)
        self.assertIn("buildsListOpen", body)
        self.assertIn("Filters", body)

    def test_manifest_records_every_card(self):
        storyboard.build_bundle(
            self.out, {"builds": self._shot("builds")}, self.template, self.ledger, "v2 label"
        )
        data = json.loads((self.out / "storyboard.json").read_text(encoding="utf-8"))
        self.assertEqual(data["source"], "v2 label")
        self.assertEqual(len(data["cards"]), 1)
        self.assertEqual(data["cards"][0]["path"], "shell/shell-builds.html")

    def test_group_override_sections_the_pane_by_source(self):
        """Prod parity and each version share one project, so the group is the source."""
        storyboard.build_bundle(
            self.out, {"builds": self._shot("builds")}, self.template, self.ledger,
            "v2 — not shipped", prefix="v2", group="v2 — secrets redesign",
        )
        first = (self.out / "v2-builds.html").read_text(encoding="utf-8").splitlines()[0]
        self.assertEqual(first, '<!-- @dsCard group="v2 — secrets redesign" -->')

    def test_prefix_namespaces_the_project_path(self):
        written = storyboard.build_bundle(
            self.out, {"builds": self._shot("builds")}, self.template, self.ledger,
            "v2", prefix="v2",
        )
        self.assertEqual(written[0]["path"], "v2/v2-builds.html")
        self.assertEqual(written[0]["local"], "v2-builds.html")

    def test_two_sources_do_not_collide(self):
        shots = {"builds": self._shot("builds")}
        a = storyboard.build_bundle(
            self.out / "a", shots, self.template, self.ledger, "prod", prefix="prod-parity"
        )
        b = storyboard.build_bundle(
            self.out / "b", shots, self.template, self.ledger, "v2", prefix="v2"
        )
        self.assertNotEqual(a[0]["path"], b[0]["path"])

    def test_group_defaults_to_the_screen_kind(self):
        storyboard.build_bundle(
            self.out, {"builds": self._shot("builds")}, self.template, self.ledger, "x"
        )
        first = (self.out / "shell-builds.html").read_text(encoding="utf-8").splitlines()[0]
        self.assertEqual(first, '<!-- @dsCard group="Screens" -->')

    def test_group_is_escaped_into_the_marker(self):
        storyboard.build_bundle(
            self.out, {"builds": self._shot("builds")}, self.template, self.ledger,
            "x", group='has "quotes"',
        )
        first = (self.out / "shell-builds.html").read_text(encoding="utf-8").splitlines()[0]
        self.assertNotIn('group="has "quotes""', first)
        self.assertIn("&quot;", first)

    def test_source_label_is_escaped_into_the_card(self):
        storyboard.build_bundle(
            self.out, {"builds": self._shot("builds")}, self.template, self.ledger, "<b>x</b>"
        )
        body = (self.out / "shell-builds.html").read_text(encoding="utf-8")
        self.assertNotIn("<b>x</b>", body)
        self.assertIn("&lt;b&gt;x&lt;/b&gt;", body)


class TestInteractive(unittest.TestCase):
    """The packed shell, marked so it can be uploaded alongside the cards."""

    PACKED = '<!DOCTYPE html>\n<html><head><title>Bundled Page</title></head><body>x</body></html>'

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def test_marker_is_first_and_doctype_survives(self):
        """A comment before <!DOCTYPE html> is safe -- verified in Chrome, compatMode
        stays CSS1Compat -- but the doctype must still be the first *tag*."""
        out = storyboard.interactive_html(self.PACKED, "Prod parity", "T")
        lines = out.splitlines()
        self.assertEqual(lines[0], '<!-- @dsCard group="Prod parity" -->')
        self.assertEqual(lines[1], "<!DOCTYPE html>")

    def test_bundled_page_title_is_replaced(self):
        out = storyboard.interactive_html(self.PACKED, "g", "Acme shell (clickable)")
        self.assertNotIn("Bundled Page", out)
        self.assertIn("<title>Acme shell (clickable)</title>", out)

    def test_only_the_first_title_is_touched(self):
        packed = self.PACKED + "<title>second</title>"
        out = storyboard.interactive_html(packed, "g", "new")
        self.assertIn("<title>second</title>", out)

    def test_group_and_title_are_escaped(self):
        out = storyboard.interactive_html(self.PACKED, 'a"b', "<x>")
        self.assertNotIn('group="a"b"', out)
        self.assertIn("&lt;x&gt;", out)

    def test_body_is_otherwise_untouched(self):
        out = storyboard.interactive_html(self.PACKED, "g", "t")
        self.assertIn("<body>x</body>", out)

    def test_written_into_the_cards_dir_for_a_single_upload_plan(self):
        packed = self.tmp / "packed.html"
        packed.write_text(self.PACKED, encoding="utf-8")
        cards = self.tmp / "cards"
        cards.mkdir()
        target = storyboard.write_interactive(packed, cards, "v2", "v2 grp", "title")
        self.assertEqual(target.name, "v2-interactive.html")
        self.assertEqual(target.parent, cards)

    def test_source_labels_prod_parity(self):
        label, group, title = storyboard.source_labels("prod-parity")
        self.assertEqual(group, "Prod parity")
        self.assertIn("clickable", title)

    def test_source_labels_marks_a_version_as_not_shipped(self):
        """The clickable prototype of a version must say so in its own name."""
        import versions
        orig = versions.read_manifest
        versions.read_manifest = lambda s, c=None: {"slug": s, "label": "secrets"}
        try:
            label, group, title = storyboard.source_labels("v2")
            self.assertIn("not shipped", label)
            self.assertIn("not shipped", title)
            self.assertEqual(group, "v2 — secrets")
        finally:
            versions.read_manifest = orig


class TestBoardState(unittest.TestCase):
    """Board staleness is what stops Claude Design drifting after a sync."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.path = self.tmp / "boards.json"

    def tearDown(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def test_missing_file_loads_empty(self):
        self.assertEqual(storyboard.load_boards(self.path)["boards"], {})

    def test_round_trips(self):
        data = storyboard.load_boards(self.path)
        storyboard.record_board(data, "prod-parity", "<html>", 11, date(2026, 8, 5))
        storyboard.save_boards(data, self.path)
        again = storyboard.load_boards(self.path)
        self.assertEqual(again["boards"]["prod-parity"]["cards"], 11)
        self.assertEqual(again["boards"]["prod-parity"]["pushed"], "2026-08-05")

    def test_fingerprint_tracks_content_not_identity(self):
        self.assertEqual(storyboard.fingerprint("<a>"), storyboard.fingerprint("<a>"))
        self.assertNotEqual(storyboard.fingerprint("<a>"), storyboard.fingerprint("<b>"))

    def test_recording_stores_the_fingerprint_of_what_was_built(self):
        data = {"boards": {}}
        entry = storyboard.record_board(data, "v2", "<html>x</html>", 11)
        self.assertEqual(entry["fingerprint"], storyboard.fingerprint("<html>x</html>"))

    def test_status_reports_current_then_stale_after_an_edit(self):
        shell = self.tmp / "shell"
        shell.mkdir()
        template = shell / "template.html"
        template.write_text("<html>v1</html>", encoding="utf-8")

        import paths
        real = paths.SHELL_DIR
        paths.SHELL_DIR = shell
        try:
            data = {"boards": {}}
            storyboard.record_board(data, "prod-parity", template.read_text(), 11)
            self.assertEqual(storyboard.board_status(data)[0]["state"], "current")

            template.write_text("<html>v2 edited</html>", encoding="utf-8")
            self.assertEqual(storyboard.board_status(data)[0]["state"], "stale")
        finally:
            paths.SHELL_DIR = real

    def test_status_reports_missing_when_the_template_is_gone(self):
        """A deleted version is worth naming, not silently calling stale."""
        import paths
        real = paths.SHELL_DIR
        paths.SHELL_DIR = self.tmp / "does-not-exist"
        try:
            data = {"boards": {"prod-parity": {"fingerprint": "x", "pushed": "2026-08-05"}}}
            self.assertEqual(storyboard.board_status(data)[0]["state"], "missing")
        finally:
            paths.SHELL_DIR = real

    def test_status_is_empty_when_nothing_boarded(self):
        self.assertEqual(storyboard.board_status({"boards": {}}), [])


if __name__ == "__main__":
    unittest.main()

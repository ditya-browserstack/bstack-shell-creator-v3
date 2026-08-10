import unittest
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR / "lib"))

import match  # noqa: E402

# Built explicitly: the stripper is per-product, so a test that relied on the
# installed profile would pass here and fail on a fresh install with no config.
ACME = match.ticket_prefix_re("ACME")

IDX = {
    "catalog_groups": ["Gestures", "Input"],
    "catalog_labels": ["Tap on element", "Double tap", "Type text", "Swipe up"],
    "screens": ["editor", "list"],
    "state_keys": ["title", "screen", "steps"],
    "methods": ["catalog", "showToast"],
    "markup_labels": ["Run test", "Save"],
}


class TestClassify(unittest.TestCase):
    def test_exact_catalog_label_is_present(self):
        result = match.classify("Tap on element", IDX)
        self.assertEqual(result["verdict"], match.PRESENT)

    def test_case_and_punctuation_insensitive(self):
        self.assertEqual(match.classify("tap on element!", IDX)["verdict"],
                         match.PRESENT)

    def test_markup_label_is_present(self):
        self.assertEqual(match.classify("Run test", IDX)["verdict"], match.PRESENT)

    def test_unrelated_feature_is_missing(self):
        result = match.classify("Service accounts", IDX)
        self.assertEqual(result["verdict"], match.MISSING)

    def test_fabricated_feature_is_missing(self):
        self.assertEqual(
            match.classify("Quantum teleport gesture", IDX)["verdict"], match.MISSING
        )

    def test_near_miss_is_uncertain(self):
        result = match.classify("Swipe up on element", IDX)
        self.assertEqual(result["verdict"], match.UNCERTAIN)

    def test_evidence_names_the_matched_entry(self):
        result = match.classify("Double tap", IDX)
        self.assertIn("Double tap", result["evidence"])

    def test_empty_name_is_uncertain_not_present(self):
        self.assertNotEqual(match.classify("", IDX)["verdict"], match.PRESENT)

    def test_short_index_entry_does_not_trigger_false_uncertain(self):
        # Regression: with min() in the overlap denominator, the single-word
        # label "Create" scored 1.0 against this and every other feature that
        # happened to contain the word.
        idx = {"markup_labels": ["Create", "Save", "Run"], "catalog_labels": [],
               "catalog_groups": [], "screens": [], "state_keys": [],
               "methods": []}
        result = match.classify("Create API adding error classifiers", idx)
        self.assertEqual(result["verdict"], match.MISSING)

    def test_plural_and_singular_are_treated_as_a_near_miss(self):
        idx = {"markup_labels": ["Service account"], "catalog_labels": [],
               "catalog_groups": [], "screens": [], "state_keys": [],
               "methods": []}
        self.assertEqual(
            match.classify("Service accounts", idx)["verdict"], match.UNCERTAIN
        )

    def test_one_shared_word_in_a_long_name_is_missing(self):
        idx = {"markup_labels": ["App Live"], "catalog_labels": [],
               "catalog_groups": [], "screens": [], "state_keys": [],
               "methods": []}
        result = match.classify("fix webex acme baseurl", idx)
        self.assertEqual(result["verdict"], match.MISSING)


class TestClassifyAll(unittest.TestCase):
    def test_classifies_each_candidate(self):
        candidates = [
            {"lcam_id": "LCAM-1", "name": "Tap on element", "prs": []},
            {"lcam_id": "LCAM-2", "name": "Service accounts", "prs": []},
        ]
        results = match.classify_all(candidates, IDX)
        self.assertEqual(results[0]["verdict"], match.PRESENT)
        self.assertEqual(results[1]["verdict"], match.MISSING)
        self.assertEqual(results[1]["lcam_id"], "LCAM-2")

    def test_strips_ticket_prefix_from_name_before_matching(self):
        candidates = [{"lcam_id": "ACME-2580", "name": "Acme 2580 tap on element",
                       "prs": []}]
        results = match.classify_all(candidates, IDX, ACME)
        self.assertEqual(results[0]["verdict"], match.PRESENT)

    def test_strips_colon_style_ticket_prefix(self):
        candidates = [{"lcam_id": "ACME-131", "name": "ACME-131: Double tap",
                       "prs": []}]
        results = match.classify_all(candidates, IDX, ACME)
        self.assertEqual(results[0]["verdict"], match.PRESENT)

    def test_a_foreign_prefix_is_left_alone(self):
        """Stripping is per-product; another team's id is not a prefix here."""
        candidates = [{"lcam_id": None, "name": "ZZZ-9 tap on element", "prs": []}]
        results = match.classify_all(candidates, IDX, ACME)
        self.assertNotEqual(results[0]["verdict"], match.PRESENT)

    def test_no_configured_prefix_strips_nothing(self):
        """An unset prefix must match nothing, not everything."""
        none_re = match.ticket_prefix_re("")
        candidates = [{"lcam_id": None, "name": "Tap on element", "prs": []}]
        results = match.classify_all(candidates, IDX, none_re)
        self.assertEqual(results[0]["verdict"], match.PRESENT)


class TestContainment(unittest.TestCase):
    """A verbosely-named feature must not be reported as MISSING.

    Found by running the skill against an older export: "Builds list Ran with
    column" scored 0.40 against the label "RAN WITH" and came back MISSING, while
    its own evidence line named the label it had just failed to match. MISSING is
    the dangerous verdict -- it enters the gap report as work to do, where
    UNCERTAIN forces adjudication instead.
    """

    IDX = {"markup_labels": ["RAN WITH", "Service account", "Create", "Secrets"]}

    def _verdict(self, name):
        return match.classify(name, self.IDX)["verdict"]

    def test_verbose_name_containing_a_label_is_uncertain_not_missing(self):
        self.assertEqual(self._verdict("Builds list Ran with column"), match.UNCERTAIN)

    def test_exact_name_still_wins_outright(self):
        self.assertEqual(self._verdict("Ran with"), match.PRESENT)

    def test_a_single_word_label_does_not_escalate_everything(self):
        """Without the two-token floor, "Create" sits inside half the product and
        every unrelated feature would escalate -- the original UNCERTAIN flood."""
        self.assertEqual(self._verdict("Create a brand new module thing"), match.MISSING)

    def test_genuinely_absent_features_stay_missing(self):
        self.assertEqual(self._verdict("Flaky test insights dashboard"), match.MISSING)

    def test_evidence_names_the_contained_label(self):
        result = match.classify("Builds list Ran with column", self.IDX)
        self.assertIn("contained in feature name", result["evidence"])
        self.assertIn("RAN WITH", result["evidence"])

    def test_containment_is_direction_agnostic(self):
        """A label longer than the feature name is the same kind of near-miss."""
        idx = {"markup_labels": ["Service account settings page"]}
        self.assertEqual(match.classify("Service account", idx)["verdict"], match.UNCERTAIN)

    def test_contained_helper_requires_two_tokens(self):
        self.assertFalse(match._contained(["create", "module"], ["create"]))
        self.assertTrue(match._contained(["ran", "with", "column"], ["ran", "with"]))


if __name__ == "__main__":
    unittest.main()

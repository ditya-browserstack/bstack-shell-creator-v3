import unittest
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR / "lib"))

import harvest  # noqa: E402

# Both patterns are config-built, so the tests stand up a fictional product
# rather than depending on whichever profile happens to be installed. The
# fixtures below are real PR titles from a production harvest with the product
# names swapped -- their shapes are what these tests are really about.
PREFIX = "ACME"
SIGNALS = ["acme", "acmeflow", "flow builder"]
TICKET = harvest.ticket_re(PREFIX)
SIGNAL = harvest.signal_re(PREFIX, SIGNALS)

PATTERNS = ["drop-*", "ACME_*drop*", "*_drop_*", "main"]


class TestBranchMatching(unittest.TestCase):
    def test_matches_drop_prefix(self):
        self.assertTrue(harvest.matches_release_branch("drop-28-july", PATTERNS))
        self.assertTrue(harvest.matches_release_branch("drop-20jul", PATTERNS))

    def test_matches_prefixed_drop_forms(self):
        self.assertTrue(harvest.matches_release_branch("ACME_july_drop", PATTERNS))
        self.assertTrue(harvest.matches_release_branch("ACME_drop_15_6_26", PATTERNS))
        self.assertTrue(harvest.matches_release_branch("28_may_drop_be_staging", PATTERNS))

    def test_matches_main(self):
        self.assertTrue(harvest.matches_release_branch("main", PATTERNS))

    def test_rejects_feature_branches(self):
        self.assertFalse(
            harvest.matches_release_branch("ACME-2580-service-accounts", PATTERNS)
        )
        self.assertFalse(harvest.matches_release_branch("ALA-5-aiAuthoring", PATTERNS))


class TestTicketExtraction(unittest.TestCase):
    def test_extracts_from_title_uppercase(self):
        pr = {"title": "fix(auth): default to v2 (ACME-2145)", "body": "",
              "headRefName": ""}
        self.assertEqual(harvest.extract_ticket_ids(pr, TICKET, PREFIX), ["ACME-2145"])

    def test_extracts_from_lowercase_spaced_title(self):
        pr = {"title": "Acme 2580 service accounts", "body": "", "headRefName": ""}
        self.assertEqual(harvest.extract_ticket_ids(pr, TICKET, PREFIX), ["ACME-2580"])

    def test_extracts_from_branch_name(self):
        pr = {"title": "service accounts", "body": "",
              "headRefName": "ACME-2580-service-accounts"}
        self.assertEqual(harvest.extract_ticket_ids(pr, TICKET, PREFIX), ["ACME-2580"])

    def test_deduplicates_across_fields(self):
        pr = {"title": "Acme 2580 service accounts", "body": "refs ACME-2580",
              "headRefName": "ACME-2580-x"}
        self.assertEqual(harvest.extract_ticket_ids(pr, TICKET, PREFIX), ["ACME-2580"])

    def test_returns_empty_when_absent(self):
        pr = {"title": "bump deps", "body": "", "headRefName": "deps"}
        self.assertEqual(harvest.extract_ticket_ids(pr, TICKET, PREFIX), [])


class TestNoise(unittest.TestCase):
    def test_dependency_bumps_are_noise(self):
        self.assertTrue(harvest.is_noise("chore(ACME-2653): bump mysql2 gem to 0.5.7"))
        self.assertTrue(harvest.is_noise("Acme 2653 mysql2 0.5.7"))

    def test_ci_changes_are_noise(self):
        self.assertTrue(harvest.is_noise("ACME_2492_ci_cd_alert"))

    def test_test_only_changes_are_noise(self):
        self.assertTrue(harvest.is_noise("chore: add specs for parser"))

    def test_unit_test_prs_are_noise(self):
        # Real titles from the July 2026 harvest.
        self.assertTrue(harvest.is_noise("ACME-2644 - Adding UTs for Email automation"))
        self.assertTrue(harvest.is_noise("ACME-2488 Parallelisation UTs enabler automation"))

    def test_lockfile_prs_are_noise(self):
        self.assertTrue(harvest.is_noise("updated the package-lock file for runner"))
        self.assertTrue(harvest.is_noise("chore: plock update for variable gating restore"))

    def test_noise_words_are_word_bounded_not_substrings(self):
        # "uts" must not match inside these, or real features get dropped.
        self.assertFalse(harvest.is_noise("Acme 2600 add keyboard shortcuts"))
        self.assertFalse(harvest.is_noise("Acme 2601 show step outputs"))

    def test_real_features_are_not_noise(self):
        self.assertFalse(harvest.is_noise("Acme 2580 service accounts"))
        self.assertFalse(harvest.is_noise("Acme 2520 ip country subdivision validation"))


class TestFilterAndCandidates(unittest.TestCase):
    def setUp(self):
        self.prs = [
            {"number": 312, "title": "Acme 2580 service accounts",
             "body": "", "headRefName": "ACME-2580-service-accounts",
             "baseRefName": "drop-28-july", "mergedAt": "2026-07-28T13:57:48Z",
             "url": "u1", "repo": "acme-backend"},
            {"number": 307, "title": "ACME-2580: enterprise entitlement",
             "body": "", "headRefName": "ACME-2580-service-accounts",
             "baseRefName": "ACME-2580-service-accounts",
             "mergedAt": "2026-07-22T11:15:51Z", "url": "u2",
             "repo": "acme-backend"},
            {"number": 305, "title": "chore(ACME-2653): bump mysql2 gem",
             "body": "", "headRefName": "x", "baseRefName": "main",
             "mergedAt": "2026-07-24T11:19:25Z", "url": "u3",
             "repo": "acme-backend"},
        ]

    def test_filter_keeps_only_release_branch_and_signal(self):
        kept = harvest.filter_prs(self.prs, PATTERNS, SIGNAL)
        self.assertEqual([pr["number"] for pr in kept], [312])

    def test_candidates_group_by_ticket_id(self):
        candidates = harvest.to_candidates(harvest.filter_prs(self.prs, PATTERNS, SIGNAL), TICKET, PREFIX)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["lcam_id"], "ACME-2580")
        self.assertEqual(candidates[0]["prs"][0]["number"], 312)

    def test_candidates_keep_prs_without_ticket_id(self):
        prs = [{"number": 1, "title": "add swipe left command", "body": "",
                "headRefName": "x", "baseRefName": "drop-28-july",
                "mergedAt": "2026-07-28T00:00:00Z", "url": "u",
                "repo": "acme-services"}]
        candidates = harvest.to_candidates(harvest.filter_prs(prs, PATTERNS, SIGNAL), TICKET, PREFIX)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["lcam_id"], None)


class TestSharedRepoGating(unittest.TestCase):
    """A shared monorepo serves every product; only this product's work counts."""

    def _pr(self, title, branch="x", shared=True):
        return {"number": 1, "title": title, "body": "", "headRefName": branch,
                "baseRefName": "drop-27-july", "mergedAt": "2026-07-27T00:00:00Z",
                "url": "u", "repo": "frontend", "shared": shared}

    def test_other_products_are_dropped(self):
        # Real titles from the July 2026 frontend harvest.
        for title in ("Tmpd 2566 cross folder bulk actions",
                      "AIR-491 rca-thinking-stepper",
                      "A11Y-12451: add Chrome-on-Android accessibility info"):
            self.assertEqual(harvest.filter_prs([self._pr(title)], PATTERNS, SIGNAL), [])

    def test_ticket_id_keeps_it(self):
        pr = self._pr("Acme 678 fix webex acme baseurl")
        self.assertEqual(len(harvest.filter_prs([pr], PATTERNS, SIGNAL)), 1)

    def test_product_token_keeps_it(self):
        pr = self._pr("Os 20501 lt acmeflow mount")
        self.assertEqual(len(harvest.filter_prs([pr], PATTERNS, SIGNAL)), 1)

    def test_multi_word_token_keeps_it(self):
        pr = self._pr("add flow-builder entry point to nav")
        self.assertEqual(len(harvest.filter_prs([pr], PATTERNS, SIGNAL)), 1)

    def test_dedicated_repo_needs_no_signal(self):
        pr = self._pr("local fix", shared=False)
        pr["repo"] = "acme-infra-ops"
        self.assertEqual(len(harvest.filter_prs([pr], PATTERNS, SIGNAL)), 1)

class TestProductAgnostic(unittest.TestCase):
    """The two product patterns come from config so a second product needs a
    profile, not a fork of harvest.py."""

    def test_ticket_prefix_is_configurable(self):
        lt = harvest.ticket_re("LT")
        pr = {"title": "LT-4412 add ramp-up profile", "headRefName": "x", "body": ""}
        self.assertEqual(harvest.extract_ticket_ids(pr, lt, "LT"), ["LT-4412"])

    def test_a_different_prefix_ignores_the_old_one(self):
        lt = harvest.ticket_re("LT")
        pr = {"title": "ACME-2580 service accounts", "headRefName": "x", "body": ""}
        self.assertEqual(harvest.extract_ticket_ids(pr, lt, "LT"), [])

    def test_signals_are_configurable(self):
        sig = harvest.signal_re("LT", ["load testing", "loadgen"])
        for title in ("Os 1 lt load-testing mount", "feat: loadgen tuning", "LT-99 x"):
            self.assertTrue(sig.search(title), title)

    def test_a_space_in_a_signal_also_matches_dash_and_underscore(self):
        sig = harvest.signal_re("LT", ["load testing"])
        for title in ("load testing", "load-testing", "load_testing"):
            self.assertTrue(sig.search(title), title)

    def test_signals_are_word_bounded(self):
        """Substring matching would pull in every unrelated product."""
        sig = harvest.signal_re("LT", ["lca"])
        self.assertFalse(sig.search("localisation work"))

    def test_there_is_no_default_ticket_prefix(self):
        """A default here would be wrong for everyone except whoever set it."""
        self.assertEqual(harvest.DEFAULT_TICKET_PREFIX, "")
        self.assertEqual(harvest.DEFAULT_PRODUCT_SIGNALS, ())

    def test_an_empty_prefix_is_refused_rather_than_interpolated(self):
        """The failure this prevents is silent, so it must be loud.

        `\\b[\\s_-]*(\\d{1,5})\\b` -- what an empty prefix would compile to --
        matches every bare number in every PR title, so an unset prefix would
        classify a whole shared monorepo as this product's work while every
        stage still reported success.
        """
        with self.assertRaises(harvest.HarvestError):
            harvest.ticket_re("")

    def test_no_prefix_and_no_signals_is_refused(self):
        with self.assertRaises(harvest.HarvestError):
            harvest.signal_re("", [])

    def test_signals_alone_are_enough(self):
        """A product with no ticket prefix in its PR titles is still workable."""
        sig = harvest.signal_re("", ["loadgen"])
        self.assertTrue(sig.search("feat: loadgen tuning"))
        self.assertFalse(sig.search("LT-99 unrelated"))


class TestTruncation(unittest.TestCase):
    """A busy shared monorepo can exceed the page size; silence would under-report."""

    def test_hitting_the_limit_is_an_error_not_a_silent_short_answer(self):
        import json as _json
        from unittest import mock
        payload = _json.dumps([
            {"number": i, "title": "t", "body": "", "headRefName": "h",
             "baseRefName": "main", "mergedAt": "2026-08-01T00:00:00Z", "url": "u"}
            for i in range(harvest.PR_LIMIT)
        ]).encode("utf-8")
        completed = mock.Mock(returncode=0, stdout=payload, stderr=b"")
        with mock.patch("subprocess.run", return_value=completed):
            with self.assertRaises(harvest.HarvestError) as ctx:
                harvest.fetch_prs("browserstack/frontend", "2026-07-22")
        self.assertIn("not seen", str(ctx.exception))

    def test_a_normal_page_is_returned_untouched(self):
        import json as _json
        from unittest import mock
        payload = _json.dumps([
            {"number": 1, "title": "t", "body": "", "headRefName": "h",
             "baseRefName": "main", "mergedAt": "2026-08-01T00:00:00Z", "url": "u"}
        ]).encode("utf-8")
        completed = mock.Mock(returncode=0, stdout=payload, stderr=b"")
        with mock.patch("subprocess.run", return_value=completed):
            prs = harvest.fetch_prs("browserstack/acme-backend", "2026-07-22")
        self.assertEqual(len(prs), 1)
        self.assertEqual(prs[0]["repo"], "acme-backend")


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Tests for the reviews, commits and head SHA pull_request.sh records.

Fixtures are GitHub REST responses built from the examples in GitHub's OpenAPI
description; see fixtures/.
"""

import json
import unittest

from harness import ScriptTestCase, fixture, fixture_json

SHA1 = "4b7e1d9c2a5f8e3b6d0c9a1f7e2d5b8c4a3f6e19"
SHA2 = "9f1c2e7d4b8a6f3e0c5d2b1a7e4f8c3d6b9a0e21"


class PullRequestTest(ScriptTestCase):
    script = "pull_request.sh"

    def pr(self, body=None):
        self.route(endswith="/repos/acme/widget/pulls/7", body=body or fixture("pull_request.json"))

    def listing(self, kind, body, codes=("200",), page="1"):
        self.route(endswith=f"/pulls/7/{kind}?per_page=100&page={page}", body=body, codes=codes)

    def run_pr(self):
        return self.run_script(LUNAR_COMPONENT_PR="7")

    def vcs_pr(self):
        return self.component_json()["vcs"]["pr"]

    def test_records_reviews_commits_and_head(self):
        self.pr()
        self.listing("reviews", fixture("pull_request_reviews.json"))
        self.listing("commits", fixture("pull_request_commits.json"))
        rc, _ = self.run_pr()
        self.assertEqual(rc, 0)
        pr = self.vcs_pr()
        self.assertEqual(pr["head_sha"], SHA2)
        self.assertEqual(pr["reviews"], [
            {"reviewer": "octocat", "state": "CHANGES_REQUESTED",
             "submitted_at": "2024-05-02T09:14:07Z", "commit_sha": SHA1},
            {"reviewer": "octocat", "state": "APPROVED",
             "submitted_at": "2024-05-02T15:40:51Z", "commit_sha": SHA2},
            # Deleted user and garbage-collected commit; the PENDING draft is left out.
            {"reviewer": "ghost", "state": "COMMENTED", "submitted_at": "2024-05-02T16:01:00Z"},
        ])
        self.assertEqual(pr["commits"], [
            {"sha": SHA1, "author": "octocat", "signature": {"verified": True, "reason": "valid"}},
            # An author email not linked to an account has no login.
            {"sha": SHA2, "signature": {"verified": False, "reason": "unsigned"}},
        ])
        # The existing fields are still written.
        self.assertEqual(pr["number"], 1347)
        self.assertEqual(pr["state"], "open")

    def test_pr_with_no_reviews_records_an_empty_list(self):
        self.pr()
        self.listing("reviews", "[]")
        self.listing("commits", fixture("pull_request_commits.json"))
        rc, _ = self.run_pr()
        self.assertEqual(rc, 0)
        self.assertEqual(self.vcs_pr()["reviews"], [])

    def test_lists_are_read_past_the_first_page(self):
        review = fixture_json("pull_request_reviews.json")[1]
        self.pr()
        self.listing("reviews", json.dumps([review] * 100), page="1")
        self.listing("reviews", json.dumps([review]), page="2")
        self.listing("commits", fixture("pull_request_commits.json"))
        rc, _ = self.run_pr()
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.vcs_pr()["reviews"]), 101)

    def test_more_commits_than_github_lists_records_none(self):
        # GitHub lists at most 250 commits; a partial list must not be written.
        pr = fixture_json("pull_request.json")
        pr["commits"] = 300
        self.pr(json.dumps(pr))
        self.listing("reviews", fixture("pull_request_reviews.json"))
        self.listing("commits", fixture("pull_request_commits.json"))
        rc, stderr = self.run_pr()
        self.assertEqual(rc, 0)
        pr_json = self.vcs_pr()
        self.assertNotIn("commits", pr_json)
        self.assertIn("reviews", pr_json)
        self.assertIn("at most 250", stderr)

    def test_listing_error_skips_only_that_list(self):
        self.pr()
        self.listing("reviews", '{"message":"Resource not accessible by integration"}', codes=("403",))
        self.listing("commits", fixture("pull_request_commits.json"))
        rc, stderr = self.run_pr()
        self.assertEqual(rc, 0)
        pr = self.vcs_pr()
        self.assertNotIn("reviews", pr)
        self.assertEqual(len(pr["commits"]), 2)
        self.assertIn(".vcs.pr.reviews not collected", stderr)

    def test_error_on_a_later_page_writes_no_partial_list(self):
        review = fixture_json("pull_request_reviews.json")[1]
        self.pr()
        self.listing("reviews", json.dumps([review] * 100), page="1")
        self.listing("reviews", "{}", codes=("500",), page="2")
        self.listing("commits", fixture("pull_request_commits.json"))
        rc, _ = self.run_pr()
        self.assertEqual(rc, 0)
        self.assertNotIn("reviews", self.vcs_pr())

    def test_transient_error_is_retried(self):
        self.pr()
        self.listing("reviews", fixture("pull_request_reviews.json"))
        self.listing("commits", fixture("pull_request_commits.json"), codes=("502", "200"))
        rc, _ = self.run_pr()
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.vcs_pr()["commits"]), 2)

    def test_outside_a_pr_writes_nothing(self):
        rc, _ = self.run_script()
        self.assertEqual(rc, 0)
        self.assertEqual(self.collected(), "")
        self.assertEqual(self.requests(), [])


if __name__ == "__main__":
    unittest.main()

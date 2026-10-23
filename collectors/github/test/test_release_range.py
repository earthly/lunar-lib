#!/usr/bin/env python3
"""Tests for release_range.sh.

Fixtures are GitHub GraphQL responses shaped like ones captured from the live
API; see fixtures/gql_*.json.
"""

import json
import unittest

from harness import ScriptTestCase, fixture

HEAD = "c3e8a1f6d9b2e5a7c0f4d8b1e6a3c9f2d5b7e0a4"
PATTERN = r"^v[0-9]+\.[0-9]+\.[0-9]+$"

TAGS = "refs(refPrefix"
COMPARE = "{ aheadBy }"
RANGE = "commits(first: $first"


class ReleaseRangeTest(ScriptTestCase):
    script = "release_range.sh"

    def standard_routes(self, range_fixture="gql_range.json"):
        self.route(TAGS, body=fixture("gql_tags.json"))
        self.route(COMPARE, body=fixture("gql_compare.json"))
        self.route(RANGE, body=fixture(range_fixture))

    def run_range(self, **env):
        base = {
            "LUNAR_COMPONENT_GIT_SHA": HEAD,
            "LUNAR_VAR_RELEASE_TAG_PATTERN": PATTERN,
        }
        base.update(env)
        return self.run_script(**base)

    def release_range(self):
        return self.component_json()["vcs"]["release_range"]

    def test_records_the_range_since_the_previous_release(self):
        self.standard_routes()
        rc, stderr = self.run_range()
        self.assertEqual(rc, 0, stderr)
        rr = self.release_range()
        # v1.2.0 sits on HEAD (nothing ahead of it) and nightly-* doesn't match,
        # so the previous release is v1.1.0, peeled through its annotated tag.
        self.assertEqual(rr["base"], {"tag": "v1.1.0", "sha": "e1d4b7a0c3f6e9d2b5a8c1f4e7d0b3a6c9f2e5d8"})
        self.assertEqual(rr["tag_pattern"], PATTERN)
        self.assertEqual(rr["head_sha"], HEAD)
        self.assertEqual(rr["default_branch"], "main")
        self.assertEqual(rr["total_commits"], 3)
        self.assertIs(rr["truncated"], False)
        c1, c2, c3 = rr["commits"]
        self.assertEqual(c1, {
            "sha": "a7c0f3e6d9b2a5c8f1e4d7b0a3c6f9e2d5b8a1c4",
            "author": "jdoe",
            "signature": {"verified": True, "reason": "valid"},
            "pull_request": {
                "number": 41, "base_branch": "main", "head_branch": "feature/payments",
                "merged_at": "2024-05-02T16:02:13Z",
                "merged_by": "octocat", "head_sha": "9f1c2e7d4b8a6f3e0c5d2b1a7e4f8c3d6b9a0e21",
                "approvals": [
                    {"reviewer": "alice", "submitted_at": "2024-05-02T15:40:51Z",
                     "commit_sha": "9f1c2e7d4b8a6f3e0c5d2b1a7e4f8c3d6b9a0e21"},
                    # GraphQL drops the [bot] suffix REST logins carry; it is put back.
                    {"reviewer": "review-bot[bot]", "submitted_at": "2024-05-02T15:41:10Z",
                     "commit_sha": "9f1c2e7d4b8a6f3e0c5d2b1a7e4f8c3d6b9a0e21"},
                    {"reviewer": "ghost", "submitted_at": "2024-05-02T15:42:00Z"},
                ],
            },
        })
        # A direct push: unsigned, and no pull_request key at all.
        self.assertEqual(c2, {
            "sha": "6d9b2e5a8c1f4d7b0e3a6c9f2d5b8e1a4c7f0d3b",
            "author": "github-actions[bot]",
            "signature": {"verified": False, "reason": "unsigned"},
        })
        # A commit merged into both main and develop (a gitflow hotfix): the PR
        # into the default branch is recorded; the unmerged PR is ignored.
        # GraphQL's UNKNOWN_SIG_TYPE maps to REST's reason.
        self.assertEqual(c3["signature"], {"verified": False, "reason": "unknown_signature_type"})
        self.assertEqual(c3["pull_request"]["number"], 43)
        self.assertEqual(c3["pull_request"]["merged_by"], "merge-queue[bot]")
        self.assertEqual(c3["pull_request"]["approvals"], [])

    def test_previous_release_is_the_nearest_not_the_newest(self):
        # v1.1.0 is newer by commit date but sits on a branch cut long ago (a
        # hotfix, say): v1.0.0 leaves fewer commits ahead and is the base.
        self.route(TAGS, body=fixture("gql_tags.json"))
        self.route(COMPARE, body=json.dumps({"data": {"repository": {
            "t0": {"compare": {"aheadBy": 0}}, "t1": {"compare": {"aheadBy": 12}},
            "t2": {"compare": {"aheadBy": 3}}}}}))
        self.route(RANGE, body=fixture("gql_range.json"))
        rc, _ = self.run_range()
        self.assertEqual(rc, 0)
        self.assertEqual(self.release_range()["base"]["tag"], "v1.0.0")

    def test_unmerged_pull_request_does_not_count(self):
        data = json.loads(fixture("gql_range.json"))
        nodes = data["data"]["repository"]["ref"]["compare"]["commits"]["nodes"]
        open_pr = dict(nodes[2]["associatedPullRequests"]["nodes"][2])  # #44, not merged
        nodes[1]["associatedPullRequests"]["nodes"] = [open_pr]
        self.route(TAGS, body=fixture("gql_tags.json"))
        self.route(COMPARE, body=fixture("gql_compare.json"))
        self.route(RANGE, body=json.dumps(data))
        rc, _ = self.run_range()
        self.assertEqual(rc, 0)
        self.assertNotIn("pull_request", self.release_range()["commits"][1])

    def test_queries_name_the_right_refs(self):
        self.standard_routes()
        rc, _ = self.run_range()
        self.assertEqual(rc, 0)
        compare, rng = [r["payload"]["variables"] for r in self.requests()[1:]]
        self.assertEqual(
            {k: v for k, v in compare.items() if k.startswith("t")},
            {"t0": "refs/tags/v1.2.0", "t1": "refs/tags/v1.1.0", "t2": "refs/tags/v1.0.0"},
        )
        self.assertEqual(compare["head"], HEAD)
        self.assertEqual((rng["base"], rng["head"], rng["first"]), ("refs/tags/v1.1.0", HEAD, 100))
        self.assertEqual(self.requests()[0]["url"], "https://api.github.com/graphql")

    def test_pages_through_the_range(self):
        self.route(TAGS, body=fixture("gql_tags.json"))
        self.route(COMPARE, body=fixture("gql_compare.json"))
        self.route(RANGE, body=fixture("gql_range_page1.json"), cursor=None)
        self.route(RANGE, body=fixture("gql_range_page2.json"), cursor="Mg")
        rc, _ = self.run_range()
        self.assertEqual(rc, 0)
        rr = self.release_range()
        self.assertEqual([c["sha"][:7] for c in rr["commits"]], ["a7c0f3e", "6d9b2e5", "c3e8a1f"])
        self.assertIs(rr["truncated"], False)

    def test_stops_at_max_commits_and_marks_the_range_truncated(self):
        self.route(TAGS, body=fixture("gql_tags.json"))
        self.route(COMPARE, body=fixture("gql_compare.json"))
        self.route(RANGE, body=fixture("gql_range_page1.json"), cursor=None)
        rc, _ = self.run_range(LUNAR_VAR_RELEASE_RANGE_MAX_COMMITS="2")
        self.assertEqual(rc, 0)
        rr = self.release_range()
        self.assertEqual(len(rr["commits"]), 2)
        self.assertEqual(rr["total_commits"], 3)
        self.assertIs(rr["truncated"], True)
        ranges = [r for r in self.requests() if RANGE in r["payload"]["query"]]
        self.assertEqual([r["payload"]["variables"]["first"] for r in ranges], [2])

    def test_max_commits_is_read_as_decimal_and_capped(self):
        # 0250 would be octal to bash and 08 an arithmetic error; huge values
        # wrap. GitHub lists at most 1000 commits of a comparison.
        for raw, first in (("002", 2), ("08", 8), ("123456789012345678901", 100)):
            with self.subTest(raw=raw):
                self.tearDown()
                self.setUp()  # fresh mocks and capture for each value
                self.standard_routes()
                rc, stderr = self.run_range(LUNAR_VAR_RELEASE_RANGE_MAX_COMMITS=raw)
                self.assertEqual(rc, 0, stderr)
                ranges = [r for r in self.requests() if RANGE in r["payload"]["query"]]
                self.assertEqual(ranges[0]["payload"]["variables"]["first"], first)
                self.assertGreater(len(self.release_range()["commits"]), 0)

    def test_no_matching_tag_records_the_pattern_without_a_base(self):
        self.standard_routes()
        rc, stderr = self.run_range(LUNAR_VAR_RELEASE_TAG_PATTERN="^release-")
        self.assertEqual(rc, 0)
        self.assertEqual(self.release_range(), {"tag_pattern": "^release-", "head_sha": HEAD})
        self.assertIn("No tag matches", stderr)
        self.assertEqual(len(self.requests()), 1)

    def test_no_tag_before_head_records_no_base(self):
        self.route(TAGS, body=fixture("gql_tags.json"))
        self.route(COMPARE, body=json.dumps({"data": {"repository": {
            "t0": {"compare": {"aheadBy": 0}}, "t1": {"compare": {"aheadBy": 0}}, "t2": None}}}))
        rc, _ = self.run_range()
        self.assertEqual(rc, 0)
        self.assertEqual(self.release_range(), {"tag_pattern": PATTERN, "head_sha": HEAD})

    def test_graphql_errors_abort_without_emitting(self):
        self.route(TAGS, body=fixture("gql_errors.json"))
        rc, stderr = self.run_range()
        self.assertNotEqual(rc, 0)
        self.assertEqual(self.collected(), "")
        self.assertIn("Could not resolve to a Repository", stderr)

    def test_persistent_server_error_aborts_after_retries(self):
        self.route(TAGS, body="{}", codes=("502",))
        rc, _ = self.run_range()
        self.assertNotEqual(rc, 0)
        self.assertEqual(self.collected(), "")
        self.assertEqual(len(self.requests()), 3)

    def test_failed_comparison_aborts_without_emitting(self):
        self.route(TAGS, body=fixture("gql_tags.json"))
        self.route(COMPARE, body=fixture("gql_compare.json"))
        self.route(RANGE, body=json.dumps({"data": {"repository": {"ref": {"compare": None}}}}))
        rc, _ = self.run_range()
        self.assertNotEqual(rc, 0)
        self.assertEqual(self.collected(), "")

    def test_enterprise_server_uses_its_graphql_endpoint(self):
        self.standard_routes()
        rc, _ = self.run_range(LUNAR_COMPONENT_ID="ghe.example.com/acme/widget/services/api")
        self.assertEqual(rc, 0)
        self.assertEqual(self.requests()[0]["url"], "https://ghe.example.com/api/graphql")
        self.assertEqual(self.requests()[0]["payload"]["variables"]["name"], "widget")

    def test_does_nothing_until_a_pattern_is_set(self):
        rc, stderr = self.run_range(LUNAR_VAR_RELEASE_TAG_PATTERN=None)
        self.assertEqual(rc, 0)
        self.assertEqual(self.requests(), [])
        self.assertEqual(self.collected(), "")
        self.assertIn("release_tag_pattern is not set", stderr)

    def test_missing_token_exits_cleanly(self):
        rc, stderr = self.run_range(LUNAR_SECRET_GH_TOKEN=None)
        self.assertEqual(rc, 0)
        self.assertEqual(self.requests(), [])
        self.assertIn("LUNAR_SECRET_GH_TOKEN is not set", stderr)

    def test_invalid_inputs_fail_loudly(self):
        for env in ({"LUNAR_VAR_RELEASE_TAG_PATTERN": "v[0-9"},
                    {"LUNAR_VAR_RELEASE_RANGE_MAX_COMMITS": "0"},
                    {"LUNAR_VAR_RELEASE_RANGE_MAX_COMMITS": "000"},
                    {"LUNAR_VAR_RELEASE_RANGE_MAX_COMMITS": "lots"}):
            with self.subTest(env=env):
                rc, _ = self.run_range(**env)
                self.assertNotEqual(rc, 0)
                self.assertEqual(self.requests(), [])


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Tests for the ruleset and bypass data branch_protection.sh records.

Fixtures are GitHub REST responses built from the examples in GitHub's OpenAPI
description; see fixtures/.
"""

import json
import unittest

from harness import ScriptTestCase, fixture, fixture_json

REPO = json.dumps({"default_branch": "main"})


class RulesetBypassTest(ScriptTestCase):
    script = "branch_protection.sh"

    def rules(self, body, codes=("200",), page="1"):
        self.route(endswith=f"/rules/branches/main?per_page=100&page={page}", body=body, codes=codes)

    def ruleset(self, rid, body, codes=("200",)):
        self.route(endswith=f"/rulesets/{rid}", body=body, codes=codes)

    def base(self, classic=None):
        self.route(endswith="/repos/acme/widget", body=REPO)
        if classic is None:
            self.route(endswith="/branches/main/protection", body='{"message":"Branch not protected"}', codes=("404",))
        else:
            self.route(endswith="/branches/main/protection", body=classic)

    def bp(self):
        return self.component_json()["vcs"]["branch_protection"]

    def test_ruleset_bypass_actors_visible_and_hidden(self):
        self.base()
        self.rules(fixture("rules_branch.json"))
        self.ruleset(42, fixture("ruleset_42.json"))
        self.ruleset(73, fixture("ruleset_73_hidden.json"))
        rc, _ = self.run_script()
        self.assertEqual(rc, 0)
        bp = self.bp()
        self.assertEqual(bp["source"], "ruleset")
        self.assertEqual(bp["rulesets"], [
            {
                "id": 42, "name": "super cool ruleset",
                "source_type": "Repository", "source": "monalisa/my-repo",
                "bypass_actors": [
                    # actor_id is null for OrganizationAdmin: dropped, not written as null
                    {"actor_type": "OrganizationAdmin", "bypass_mode": "always"},
                    {"actor_type": "RepositoryRole", "actor_id": 5, "bypass_mode": "always"},
                    {"actor_type": "Integration", "actor_id": 98765, "bypass_mode": "pull_request"},
                ],
            },
            # No write access to the org ruleset: hidden, so no bypass_actors key.
            {"id": 73, "name": "org baseline", "source_type": "Organization", "source": "my-org"},
        ])
        # Existing ruleset-derived fields are unchanged.
        self.assertTrue(bp["require_pr"])
        self.assertTrue(bp["require_signed_commits"])
        self.assertNotIn("enforce_admins", bp)
        self.assertNotIn("bypass_pull_request_allowances", bp)

    def test_empty_bypass_list_is_recorded_as_empty(self):
        self.base()
        self.rules(fixture("rules_branch.json"))
        self.ruleset(42, fixture("ruleset_42.json"))
        self.ruleset(73, fixture("ruleset_73_empty.json"))
        rc, _ = self.run_script()
        self.assertEqual(rc, 0)
        self.assertEqual(self.bp()["rulesets"][1]["bypass_actors"], [])

    def test_ruleset_404_is_recorded_as_hidden(self):
        # A ruleset deleted between the two calls: keep what the rules call knew.
        self.base()
        self.rules(fixture("rules_branch.json"))
        self.ruleset(42, fixture("ruleset_42.json"))
        self.ruleset(73, '{"message":"Not Found"}', codes=("404",))
        rc, _ = self.run_script()
        self.assertEqual(rc, 0)
        self.assertEqual(self.bp()["rulesets"][1], {"id": 73, "source_type": "Organization", "source": "my-org"})

    def test_ruleset_server_error_aborts_without_emitting(self):
        self.base()
        self.rules(fixture("rules_branch.json"))
        self.ruleset(42, "{}", codes=("502",))
        rc, stderr = self.run_script()
        self.assertNotEqual(rc, 0)
        self.assertNotIn(".vcs.branch_protection.enabled", self.collected())
        self.assertIn("HTTP 502", stderr)

    def test_rules_are_read_past_the_first_page(self):
        # 100 rules on page 1 means there may be more; ruleset 73 is only on page 2.
        page1 = [{"type": "pull_request", "ruleset_source_type": "Repository",
                  "ruleset_source": "monalisa/my-repo", "ruleset_id": 42,
                  "parameters": {"required_approving_review_count": 1}}] * 100
        page2 = [fixture_json("rules_branch.json")[-1]]
        self.base()
        self.rules(json.dumps(page1), page="1")
        self.rules(json.dumps(page2), page="2")
        self.ruleset(42, fixture("ruleset_42.json"))
        self.ruleset(73, fixture("ruleset_73_empty.json"))
        rc, _ = self.run_script()
        self.assertEqual(rc, 0)
        bp = self.bp()
        self.assertEqual([r["id"] for r in bp["rulesets"]], [42, 73])
        self.assertTrue(bp["require_signed_commits"])  # the page-2 rule counts

    def test_repository_target_rulesets_are_left_out(self):
        # The rules call also returns repository-target rulesets (delete,
        # transfer, visibility rules); their bypass lists don't cover the branch.
        rules = fixture_json("rules_branch.json") + [
            {"type": "repository_delete", "ruleset_source_type": "Organization",
             "ruleset_source": "my-org", "ruleset_id": 99}]
        self.base()
        self.rules(json.dumps(rules))
        self.ruleset(42, fixture("ruleset_42.json"))
        self.ruleset(73, fixture("ruleset_73_empty.json"))
        self.ruleset(99, fixture("ruleset_99_repository.json"))
        rc, _ = self.run_script()
        self.assertEqual(rc, 0)
        self.assertEqual([r["id"] for r in self.bp()["rulesets"]], [42, 73])

    def test_rules_listing_cut_off_after_ten_pages_aborts(self):
        full = json.dumps([{"type": "pull_request", "ruleset_source_type": "Repository",
                            "ruleset_source": "monalisa/my-repo", "ruleset_id": 42,
                            "parameters": {"required_approving_review_count": 1}}] * 100)
        self.base()
        for page in range(1, 11):
            self.rules(full, page=str(page))
        rc, _ = self.run_script()
        self.assertNotEqual(rc, 0)
        self.assertNotIn(".vcs.branch_protection.enabled", self.collected())

    def test_unprotected_branch_records_no_rulesets(self):
        self.base()
        self.rules("[]")
        rc, _ = self.run_script()
        self.assertEqual(rc, 0)
        bp = self.bp()
        self.assertEqual(bp["source"], "none")
        self.assertEqual(bp["rulesets"], [])

    def test_classic_records_admin_enforcement_and_bypass_allowances(self):
        self.base(classic=fixture("classic_bypass.json"))
        self.rules(fixture("rules_branch.json"))
        self.ruleset(42, fixture("ruleset_42.json"))
        self.ruleset(73, fixture("ruleset_73_empty.json"))
        rc, _ = self.run_script()
        self.assertEqual(rc, 0)
        bp = self.bp()
        self.assertEqual(bp["source"], "classic")
        self.assertIs(bp["enforce_admins"], False)
        self.assertEqual(bp["bypass_pull_request_allowances"],
                         {"users": ["octocat"], "teams": ["justice-league"], "apps": ["octoapp"]})
        # Rulesets layered on top of classic protection are read too.
        self.assertEqual([r["id"] for r in bp["rulesets"]], [42, 73])

    def test_classic_without_allowances_records_empty_lists(self):
        classic = fixture_json("classic_bypass.json")
        classic["enforce_admins"]["enabled"] = True
        del classic["required_pull_request_reviews"]["bypass_pull_request_allowances"]
        self.base(classic=json.dumps(classic))
        self.rules("[]")
        rc, _ = self.run_script()
        self.assertEqual(rc, 0)
        bp = self.bp()
        self.assertIs(bp["enforce_admins"], True)
        self.assertEqual(bp["bypass_pull_request_allowances"], {"users": [], "teams": [], "apps": []})
        self.assertEqual(bp["rulesets"], [])

    def test_classic_keeps_its_data_when_rulesets_cannot_be_read(self):
        # The classic fields are accurate on their own; only .rulesets is unknown.
        self.base(classic=fixture("classic_bypass.json"))
        self.rules("{}", codes=("500",))
        rc, stderr = self.run_script()
        self.assertEqual(rc, 0)
        bp = self.bp()
        self.assertEqual(bp["source"], "classic")
        self.assertIs(bp["enforce_admins"], False)
        self.assertNotIn("rulesets", bp)
        self.assertIn("rulesets not collected", stderr)

    def test_classic_keeps_its_data_when_a_ruleset_cannot_be_read(self):
        self.base(classic=fixture("classic_bypass.json"))
        self.rules(fixture("rules_branch.json"))
        self.ruleset(42, fixture("ruleset_42.json"))
        self.ruleset(73, "{}", codes=("502",))
        rc, stderr = self.run_script()
        self.assertEqual(rc, 0)
        bp = self.bp()
        self.assertEqual(bp["source"], "classic")
        self.assertNotIn("rulesets", bp)
        self.assertIn("HTTP 502", stderr)


if __name__ == "__main__":
    unittest.main()

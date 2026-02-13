#!/usr/bin/env python3
"""Tests for CODEOWNERS policy checks."""

import os
import sys
import unittest

# Add policy directory to path
sys.path.insert(0, os.path.dirname(__file__))

from lunar_policy import CheckStatus, Node

from exists import main as check_exists
from valid import main as check_valid
from catchall import main as check_catchall
from min_owners import main as check_min_owners
from team_owners import main as check_team_owners
from no_individuals_only import main as check_no_individuals_only
from no_empty_rules import main as check_no_empty_rules
from max_owners import main as check_max_owners


# ---------------------------------------------------------------------------
# Test data helpers
# ---------------------------------------------------------------------------

def make_node(codeowners_data):
    """Build a Node from a codeowners dict."""
    return Node.from_component_json({"ownership": {"codeowners": codeowners_data}})


def make_typical():
    """Standard CODEOWNERS with teams, individuals, and catch-all."""
    return make_node({
        "exists": True,
        "valid": True,
        "path": "CODEOWNERS",
        "errors": [],
        "owners": ["@acme/backend", "@acme/platform", "@jane"],
        "team_owners": ["@acme/backend", "@acme/platform"],
        "individual_owners": ["@jane"],
        "rules": [
            {"pattern": "*", "owners": ["@acme/platform"], "owner_count": 1, "line": 2},
            {"pattern": "/src/", "owners": ["@acme/backend", "@jane"], "owner_count": 2, "line": 4},
        ],
    })


def make_no_file():
    """CODEOWNERS file does not exist."""
    return make_node({"exists": False})


def make_empty_data():
    """No codeowners data at all."""
    return Node.from_component_json({})


# ---------------------------------------------------------------------------
# exists
# ---------------------------------------------------------------------------
class TestExists(unittest.TestCase):
    def test_file_exists_passes(self):
        check = check_exists(make_typical())
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_file_missing_pending(self):
        # assert_exists on a missing path in a test node yields PENDING
        # (in production, after collectors finish, this becomes FAIL)
        check = check_exists(make_no_file())
        self.assertEqual(check.status, CheckStatus.PENDING)

    def test_no_data_pending(self):
        check = check_exists(make_empty_data())
        self.assertEqual(check.status, CheckStatus.PENDING)


# ---------------------------------------------------------------------------
# valid
# ---------------------------------------------------------------------------
class TestValid(unittest.TestCase):
    def test_valid_passes(self):
        check = check_valid(make_typical())
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_invalid_fails(self):
        node = make_node({
            "exists": True,
            "valid": False,
            "errors": [
                {"line": 3, "message": "Invalid owner format: 'bad'", "content": "/src/ bad"},
                {"line": 5, "message": "Invalid owner format: 'also_bad'", "content": "docs/ also_bad"},
            ],
            "owners": [],
            "team_owners": [],
            "individual_owners": [],
            "rules": [],
        })
        check = check_valid(node)
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertEqual(len(check.failure_reasons), 2)
        self.assertIn("Line 3", check.failure_reasons[0])
        self.assertIn("Line 5", check.failure_reasons[1])

    def test_no_file_pending(self):
        check = check_valid(make_no_file())
        self.assertEqual(check.status, CheckStatus.PENDING)


# ---------------------------------------------------------------------------
# catchall
# ---------------------------------------------------------------------------
class TestCatchall(unittest.TestCase):
    def test_has_catchall_passes(self):
        check = check_catchall(make_typical())
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_no_catchall_fails(self):
        node = make_node({
            "exists": True,
            "valid": True,
            "errors": [],
            "owners": ["@acme/backend"],
            "team_owners": ["@acme/backend"],
            "individual_owners": [],
            "rules": [
                {"pattern": "/src/", "owners": ["@acme/backend"], "owner_count": 1, "line": 1},
            ],
        })
        check = check_catchall(node)
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("no default catch-all", check.failure_reasons[0])

    def test_no_file_pending(self):
        check = check_catchall(make_no_file())
        self.assertEqual(check.status, CheckStatus.PENDING)


# ---------------------------------------------------------------------------
# min-owners
# ---------------------------------------------------------------------------
class TestMinOwners(unittest.TestCase):
    def test_all_rules_meet_default_fails(self):
        # Default is 2, but catch-all has only 1
        check = check_min_owners(make_typical(), min_owners_override="2")
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("'*' has 1 owner", check.failure_reasons[0])

    def test_all_rules_meet_minimum_passes(self):
        check = check_min_owners(make_typical(), min_owners_override="1")
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_custom_threshold(self):
        node = make_node({
            "exists": True,
            "valid": True,
            "errors": [],
            "owners": ["@a/t1", "@a/t2", "@a/t3"],
            "team_owners": ["@a/t1", "@a/t2", "@a/t3"],
            "individual_owners": [],
            "rules": [
                {"pattern": "*", "owners": ["@a/t1", "@a/t2", "@a/t3"], "owner_count": 3, "line": 1},
            ],
        })
        check = check_min_owners(node, min_owners_override="3")
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_skips_empty_rules(self):
        """Rules with 0 owners should be skipped (handled by no-empty-rules)."""
        node = make_node({
            "exists": True,
            "valid": True,
            "errors": [],
            "owners": ["@acme/team"],
            "team_owners": ["@acme/team"],
            "individual_owners": [],
            "rules": [
                {"pattern": "*", "owners": ["@acme/team"], "owner_count": 1, "line": 1},
                {"pattern": "/vendor/", "owners": [], "owner_count": 0, "line": 3},
            ],
        })
        check = check_min_owners(node, min_owners_override="1")
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_no_file_pending(self):
        check = check_min_owners(make_no_file())
        self.assertEqual(check.status, CheckStatus.PENDING)


# ---------------------------------------------------------------------------
# team-owners
# ---------------------------------------------------------------------------
class TestTeamOwners(unittest.TestCase):
    def test_has_teams_passes(self):
        check = check_team_owners(make_typical())
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_no_teams_fails(self):
        node = make_node({
            "exists": True,
            "valid": True,
            "errors": [],
            "owners": ["@alice", "@bob"],
            "team_owners": [],
            "individual_owners": ["@alice", "@bob"],
            "rules": [
                {"pattern": "*", "owners": ["@alice", "@bob"], "owner_count": 2, "line": 1},
            ],
        })
        check = check_team_owners(node)
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("no team-based owners", check.failure_reasons[0])

    def test_no_file_pending(self):
        check = check_team_owners(make_no_file())
        self.assertEqual(check.status, CheckStatus.PENDING)


# ---------------------------------------------------------------------------
# no-individuals-only
# ---------------------------------------------------------------------------
class TestNoIndividualsOnly(unittest.TestCase):
    def test_all_rules_have_teams_passes(self):
        node = make_node({
            "exists": True,
            "valid": True,
            "errors": [],
            "owners": ["@acme/team", "@jane"],
            "team_owners": ["@acme/team"],
            "individual_owners": ["@jane"],
            "rules": [
                {"pattern": "*", "owners": ["@acme/team", "@jane"], "owner_count": 2, "line": 1},
            ],
        })
        check = check_no_individuals_only(node)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_rule_with_only_individuals_fails(self):
        node = make_node({
            "exists": True,
            "valid": True,
            "errors": [],
            "owners": ["@acme/team", "@alice", "@bob"],
            "team_owners": ["@acme/team"],
            "individual_owners": ["@alice", "@bob"],
            "rules": [
                {"pattern": "*", "owners": ["@acme/team"], "owner_count": 1, "line": 1},
                {"pattern": "/src/", "owners": ["@alice", "@bob"], "owner_count": 2, "line": 3},
            ],
        })
        check = check_no_individuals_only(node)
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("'/src/'", check.failure_reasons[0])
        self.assertIn("only individual owners", check.failure_reasons[0])

    def test_no_file_pending(self):
        check = check_no_individuals_only(make_no_file())
        self.assertEqual(check.status, CheckStatus.PENDING)


# ---------------------------------------------------------------------------
# no-empty-rules
# ---------------------------------------------------------------------------
class TestNoEmptyRules(unittest.TestCase):
    def test_all_rules_have_owners_passes(self):
        check = check_no_empty_rules(make_typical())
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_empty_rule_fails(self):
        node = make_node({
            "exists": True,
            "valid": True,
            "errors": [],
            "owners": ["@acme/team"],
            "team_owners": ["@acme/team"],
            "individual_owners": [],
            "rules": [
                {"pattern": "*", "owners": ["@acme/team"], "owner_count": 1, "line": 1},
                {"pattern": "/vendor/", "owners": [], "owner_count": 0, "line": 3},
            ],
        })
        check = check_no_empty_rules(node)
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("'/vendor/'", check.failure_reasons[0])
        self.assertIn("no owners", check.failure_reasons[0])

    def test_no_file_pending(self):
        check = check_no_empty_rules(make_no_file())
        self.assertEqual(check.status, CheckStatus.PENDING)


# ---------------------------------------------------------------------------
# max-owners
# ---------------------------------------------------------------------------
class TestMaxOwners(unittest.TestCase):
    def test_within_limit_passes(self):
        check = check_max_owners(make_typical(), max_owners_override="10")
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_exceeds_limit_fails(self):
        many_owners = [f"@acme/team{i}" for i in range(12)]
        node = make_node({
            "exists": True,
            "valid": True,
            "errors": [],
            "owners": many_owners,
            "team_owners": many_owners,
            "individual_owners": [],
            "rules": [
                {"pattern": "*", "owners": many_owners, "owner_count": 12, "line": 1},
            ],
        })
        check = check_max_owners(node, max_owners_override="10")
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("12 owners", check.failure_reasons[0])
        self.assertIn("maximum is 10", check.failure_reasons[0])

    def test_custom_threshold(self):
        check = check_max_owners(make_typical(), max_owners_override="2")
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_no_file_pending(self):
        check = check_max_owners(make_no_file())
        self.assertEqual(check.status, CheckStatus.PENDING)


if __name__ == "__main__":
    unittest.main()

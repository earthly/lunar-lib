#!/usr/bin/env python3
"""Tests for parse_codeowners.py."""

import os
import sys
import unittest

# Add parent directory so we can import the parser
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from parse_codeowners import classify_owner, parse_codeowners

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def fixture(name):
    return os.path.join(FIXTURES, name)


# ---------------------------------------------------------------------------
# Unit tests for classify_owner
# ---------------------------------------------------------------------------
class TestClassifyOwner(unittest.TestCase):
    def test_team(self):
        self.assertEqual(classify_owner("@acme/platform"), "team")

    def test_team_with_dots(self):
        self.assertEqual(classify_owner("@acme/platform.core"), "team")

    def test_team_with_hyphens(self):
        self.assertEqual(classify_owner("@my-org/my-team"), "team")

    def test_user(self):
        self.assertEqual(classify_owner("@jane"), "user")

    def test_user_with_hyphens(self):
        self.assertEqual(classify_owner("@jane-doe"), "user")

    def test_user_with_dots(self):
        self.assertEqual(classify_owner("@user.name"), "user")

    def test_email(self):
        self.assertEqual(classify_owner("alice@example.com"), "email")

    def test_email_subdomain(self):
        self.assertEqual(classify_owner("ops-lead@company.io"), "email")

    def test_invalid_bare_word(self):
        self.assertIsNone(classify_owner("not-an-owner"))

    def test_invalid_double_at(self):
        self.assertIsNone(classify_owner("@bob@example.com"))

    def test_invalid_empty(self):
        self.assertIsNone(classify_owner(""))

    def test_invalid_at_only(self):
        self.assertIsNone(classify_owner("@"))

    def test_invalid_slash_no_org(self):
        self.assertIsNone(classify_owner("@/team"))


# ---------------------------------------------------------------------------
# Integration tests against fixture files
# ---------------------------------------------------------------------------
class TestTypical(unittest.TestCase):
    """Standard CODEOWNERS with catch-all, teams, and individuals."""

    def setUp(self):
        self.result = parse_codeowners(fixture("typical.CODEOWNERS"))

    def test_exists_and_valid(self):
        self.assertTrue(self.result["exists"])
        self.assertTrue(self.result["valid"])
        self.assertEqual(self.result["errors"], [])

    def test_rules(self):
        rules = self.result["rules"]
        self.assertEqual(len(rules), 5)
        # First rule is the catch-all
        self.assertEqual(rules[0]["pattern"], "*")
        self.assertEqual(rules[0]["owners"], ["@acme/platform-team"])

    def test_owners(self):
        self.assertIn("@acme/platform-team", self.result["owners"])
        self.assertIn("@jane", self.result["owners"])
        self.assertIn("@john", self.result["owners"])

    def test_team_vs_individual(self):
        self.assertIn("@acme/platform-team", self.result["team_owners"])
        self.assertIn("@acme/frontend-team", self.result["team_owners"])
        self.assertIn("@jane", self.result["individual_owners"])
        self.assertIn("@john", self.result["individual_owners"])
        # Teams should not appear in individual list
        self.assertNotIn("@acme/platform-team", self.result["individual_owners"])


class TestEmpty(unittest.TestCase):
    """Completely empty file."""

    def setUp(self):
        self.result = parse_codeowners(fixture("empty.CODEOWNERS"))

    def test_exists_and_valid(self):
        self.assertTrue(self.result["exists"])
        self.assertTrue(self.result["valid"])

    def test_no_rules(self):
        self.assertEqual(self.result["rules"], [])

    def test_no_owners(self):
        self.assertEqual(self.result["owners"], [])
        self.assertEqual(self.result["team_owners"], [])
        self.assertEqual(self.result["individual_owners"], [])


class TestCommentsOnly(unittest.TestCase):
    """File with only comments and blank lines."""

    def setUp(self):
        self.result = parse_codeowners(fixture("comments_only.CODEOWNERS"))

    def test_valid_with_no_rules(self):
        self.assertTrue(self.result["valid"])
        self.assertEqual(self.result["rules"], [])
        self.assertEqual(self.result["owners"], [])


class TestNoCatchall(unittest.TestCase):
    """File with rules but no * pattern."""

    def setUp(self):
        self.result = parse_codeowners(fixture("no_catchall.CODEOWNERS"))

    def test_valid(self):
        self.assertTrue(self.result["valid"])

    def test_rules_exist(self):
        self.assertEqual(len(self.result["rules"]), 2)

    def test_no_catchall_rule(self):
        patterns = [r["pattern"] for r in self.result["rules"]]
        self.assertNotIn("*", patterns)


class TestEmails(unittest.TestCase):
    """Owners specified as email addresses."""

    def setUp(self):
        self.result = parse_codeowners(fixture("emails.CODEOWNERS"))

    def test_valid(self):
        self.assertTrue(self.result["valid"])

    def test_emails_are_individuals(self):
        self.assertIn("alice@example.com", self.result["individual_owners"])
        self.assertIn("bob@example.com", self.result["individual_owners"])
        self.assertIn("ops-lead@company.io", self.result["individual_owners"])

    def test_mixed_rule(self):
        # /ops/ has an email and a team
        ops_rule = self.result["rules"][1]
        self.assertEqual(ops_rule["pattern"], "/ops/")
        self.assertIn("ops-lead@company.io", ops_rule["owners"])
        self.assertIn("@acme/ops-team", ops_rule["owners"])

    def test_team_from_mixed_rule(self):
        self.assertIn("@acme/ops-team", self.result["team_owners"])


class TestInvalidOwners(unittest.TestCase):
    """File with some invalid owner formats."""

    def setUp(self):
        self.result = parse_codeowners(fixture("invalid_owners.CODEOWNERS"))

    def test_not_valid(self):
        self.assertFalse(self.result["valid"])

    def test_error_count(self):
        self.assertEqual(len(self.result["errors"]), 2)

    def test_error_details(self):
        messages = [e["message"] for e in self.result["errors"]]
        self.assertIn("Invalid owner format: 'not-an-owner'", messages)
        self.assertIn("Invalid owner format: 'also_bad'", messages)

    def test_error_line_numbers(self):
        lines = {e["line"] for e in self.result["errors"]}
        self.assertEqual(lines, {3})  # Both errors on same line

    def test_valid_owners_still_collected(self):
        # Valid owners from the bad line and other lines should still appear
        self.assertIn("@acme/platform", self.result["owners"])
        self.assertIn("@acme/backend", self.result["owners"])
        self.assertIn("@acme/docs", self.result["owners"])

    def test_rules_still_parsed(self):
        self.assertEqual(len(self.result["rules"]), 3)


class TestUnassign(unittest.TestCase):
    """Pattern with no owners (un-assigns ownership)."""

    def setUp(self):
        self.result = parse_codeowners(fixture("unassign.CODEOWNERS"))

    def test_valid(self):
        # No-owner rules are valid CODEOWNERS syntax
        self.assertTrue(self.result["valid"])

    def test_unassign_rule(self):
        vendor_rule = self.result["rules"][1]
        self.assertEqual(vendor_rule["pattern"], "/vendor/")
        self.assertEqual(vendor_rule["owners"], [])
        self.assertEqual(vendor_rule["owner_count"], 0)


class TestInlineComments(unittest.TestCase):
    """Lines with inline # comments after owners."""

    def setUp(self):
        self.result = parse_codeowners(fixture("inline_comments.CODEOWNERS"))

    def test_valid(self):
        self.assertTrue(self.result["valid"])

    def test_comments_stripped(self):
        # Inline comments should not appear as owners
        all_owners = self.result["owners"]
        for owner in all_owners:
            self.assertFalse(owner.startswith("#"), f"Comment leaked as owner: {owner}")

    def test_owners_correct(self):
        self.assertEqual(
            self.result["owners"],
            ["@acme/backend", "@acme/docs", "@acme/platform", "@jane"],
        )

    def test_rule_owners(self):
        # /src/ should have @acme/backend and @jane, not the comment
        src_rule = self.result["rules"][1]
        self.assertEqual(src_rule["owners"], ["@acme/backend", "@jane"])
        self.assertEqual(src_rule["owner_count"], 2)


class TestTeamsOnly(unittest.TestCase):
    """All owners are teams."""

    def setUp(self):
        self.result = parse_codeowners(fixture("teams_only.CODEOWNERS"))

    def test_all_teams(self):
        self.assertEqual(len(self.result["team_owners"]), 4)
        self.assertEqual(self.result["individual_owners"], [])


class TestIndividualsOnly(unittest.TestCase):
    """All owners are individuals (users and emails)."""

    def setUp(self):
        self.result = parse_codeowners(fixture("individuals_only.CODEOWNERS"))

    def test_no_teams(self):
        self.assertEqual(self.result["team_owners"], [])

    def test_individuals(self):
        self.assertIn("@alice", self.result["individual_owners"])
        self.assertIn("@bob", self.result["individual_owners"])
        self.assertIn("@charlie", self.result["individual_owners"])
        self.assertIn("alice@example.com", self.result["individual_owners"])


class TestComplexPatterns(unittest.TestCase):
    """Various glob patterns including negation."""

    def setUp(self):
        self.result = parse_codeowners(fixture("complex_patterns.CODEOWNERS"))

    def test_valid(self):
        self.assertTrue(self.result["valid"])

    def test_patterns_preserved(self):
        patterns = [r["pattern"] for r in self.result["rules"]]
        self.assertIn("*.go", patterns)
        self.assertIn("*.js", patterns)
        self.assertIn("/docs/*.md", patterns)
        self.assertIn("/scripts/**/*.sh", patterns)
        self.assertIn("!README.md", patterns)

    def test_rule_count(self):
        self.assertEqual(len(self.result["rules"]), 7)


class TestWhitespace(unittest.TestCase):
    """File with leading/trailing whitespace and extra spaces between tokens."""

    def setUp(self):
        self.result = parse_codeowners(fixture("whitespace.CODEOWNERS"))

    def test_valid(self):
        self.assertTrue(self.result["valid"])

    def test_rules_parsed(self):
        self.assertEqual(len(self.result["rules"]), 2)

    def test_owners_correct(self):
        # Extra spaces should not affect parsing
        catchall = self.result["rules"][0]
        self.assertEqual(catchall["pattern"], "*")
        self.assertEqual(catchall["owners"], ["@acme/platform", "@jane"])

    def test_indented_comment_skipped(self):
        # Indented comment should not become a rule
        patterns = [r["pattern"] for r in self.result["rules"]]
        self.assertNotIn("#", patterns)


class TestSingleRule(unittest.TestCase):
    """Minimal file with just one catch-all rule."""

    def setUp(self):
        self.result = parse_codeowners(fixture("single_rule.CODEOWNERS"))

    def test_valid(self):
        self.assertTrue(self.result["valid"])

    def test_one_rule(self):
        self.assertEqual(len(self.result["rules"]), 1)
        self.assertEqual(self.result["rules"][0]["pattern"], "*")
        self.assertEqual(self.result["rules"][0]["owners"], ["@acme/everyone"])


class TestDuplicateCatchall(unittest.TestCase):
    """Multiple * rules — both should appear in rules list."""

    def setUp(self):
        self.result = parse_codeowners(fixture("duplicate_catchall.CODEOWNERS"))

    def test_valid(self):
        self.assertTrue(self.result["valid"])

    def test_both_catchall_rules_present(self):
        catchalls = [r for r in self.result["rules"] if r["pattern"] == "*"]
        self.assertEqual(len(catchalls), 2)

    def test_rule_order_preserved(self):
        rules = self.result["rules"]
        # First *, then /src/, then second *
        self.assertEqual(rules[0]["pattern"], "*")
        self.assertEqual(rules[0]["owners"], ["@acme/old-team"])
        self.assertEqual(rules[1]["pattern"], "/src/")
        self.assertEqual(rules[2]["pattern"], "*")
        self.assertEqual(rules[2]["owners"], ["@acme/new-team", "@alice"])


class TestDottedNames(unittest.TestCase):
    """Teams and users with dots in their names."""

    def setUp(self):
        self.result = parse_codeowners(fixture("dotted_names.CODEOWNERS"))

    def test_valid(self):
        self.assertTrue(self.result["valid"])

    def test_dotted_team(self):
        self.assertIn("@acme/platform.core", self.result["team_owners"])
        self.assertIn("@my-org/my.team.name", self.result["team_owners"])

    def test_dotted_user(self):
        self.assertIn("@user.name", self.result["individual_owners"])


class TestLineNumbers(unittest.TestCase):
    """Line numbers should reflect the actual file lines, counting comments and blanks."""

    def setUp(self):
        self.result = parse_codeowners(fixture("typical.CODEOWNERS"))

    def test_line_numbers(self):
        rules = self.result["rules"]
        # typical.CODEOWNERS:
        # 1: # Default owners
        # 2: * @acme/platform-team
        # 3: (blank)
        # 4: # Frontend
        # 5: /src/frontend/ @acme/frontend-team @jane
        # 6: *.js @acme/frontend-team
        # 7: (blank)
        # 8: # Backend
        # 9: /src/backend/ @acme/backend-team @john
        # 10: (blank)
        # 11: # Docs
        # 12: docs/ @acme/docs-team
        self.assertEqual(rules[0]["line"], 2)
        self.assertEqual(rules[1]["line"], 5)
        self.assertEqual(rules[2]["line"], 6)
        self.assertEqual(rules[3]["line"], 9)
        self.assertEqual(rules[4]["line"], 12)


if __name__ == "__main__":
    unittest.main()

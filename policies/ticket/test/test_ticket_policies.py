"""Unit tests for the ticket policy checks.

fixtures/jira-issue-*.json are Jira REST API v3 issue responses: the Get issue
example from Atlassian's reference with a status, issue type, assignee,
priority, labels and custom fields added in the documented shapes. The tests
wrap them in the ticket record the jira collector writes, so `ticket_field`
paths run against the same structure a real import produces.
"""

import importlib.util
import io
import json
import os
import sys
import unittest
from contextlib import contextmanager, redirect_stderr
from pathlib import Path

from lunar_policy import CheckStatus, Node

POLICY_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(POLICY_DIR))

from helpers import parse_list  # noqa: E402


def load_policy(filename):
    spec = importlib.util.spec_from_file_location(
        filename.replace("-", "_"), POLICY_DIR / f"{filename}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.main


ticket_present = load_policy("ticket-present")
ticket_valid = load_policy("ticket-valid")
ticket_source = load_policy("ticket-source")
ticket_status = load_policy("ticket-status")
ticket_type = load_policy("ticket-type")
ticket_reuse = load_policy("ticket-reuse")
ticket_field = load_policy("ticket-field")


def load_issue(key):
    with open(Path(__file__).parent / "fixtures" / f"jira-issue-{key}.json") as f:
        return json.load(f)


ARB = load_issue("ARB-56")
TP = load_issue("TP-1")
SECOND = ".vcs.pr.architecture_review"


def record(issue, **overrides):
    """The ticket record the jira collector writes for a confirmed issue."""
    fields = issue["fields"]
    rec = {
        "id": issue["key"],
        "source": {"tool": "jira", "integration": "api"},
        "url": f"https://acme.atlassian.net/browse/{issue['key']}",
        "valid": True,
        "status": fields["status"]["name"],
        "type": fields["issuetype"]["name"],
        "summary": fields["summary"],
        "assignee": fields["assignee"]["emailAddress"],
        "native": {"jira": issue},
    }
    rec.update(overrides)
    return rec


def with_fields(issue, **fields):
    """A copy of an issue with some fields replaced."""
    copy = json.loads(json.dumps(issue))
    copy["fields"].update(fields)
    return copy


def component(ticket=None, second=None, author=None):
    pr = {"number": 8, "title": "[TP-1] Add payment retries"}
    if author is not None:
        pr["author"] = author
    if ticket is not None:
        pr["ticket"] = ticket
    if second is not None:
        pr["architecture_review"] = second
    return {"vcs": {"pr": pr}}


def node(data, finished=True):
    return Node.from_component_json(
        data, bundle_info={"workflows_finished": True} if finished else {})


@contextmanager
def policy_vars(**kwargs):
    saved = {}
    try:
        for key, value in kwargs.items():
            env_key = f"LUNAR_VAR_{key}"
            saved[env_key] = os.environ.get(env_key)
            os.environ[env_key] = value
        yield
    finally:
        for env_key, old in saved.items():
            if old is None:
                os.environ.pop(env_key, None)
            else:
                os.environ[env_key] = old


def outcome(check):
    """pass / fail / skip / pending. Check.status folds a skip into PASS."""
    if any(r.result == CheckStatus.SKIPPED for r in check._results):
        return "skip"
    return {CheckStatus.PASS: "pass", CheckStatus.FAIL: "fail",
            CheckStatus.PENDING: "pending", CheckStatus.ERROR: "error"}[check.status]


def message(check):
    return "\n".join(r.failure_message or "" for r in check._results)


class TestTicketField(unittest.TestCase):
    OPTION = "native.jira.fields.customfield_10042"

    def run_field(self, data, finished=True, **vars):
        # These cases are about matching the field; TestRerunHint covers the hint.
        vars.setdefault("rerun_collectors", "")
        with policy_vars(**vars):
            return ticket_field(node(data, finished))

    def test_unconfigured_skips(self):
        check = self.run_field(component(record(ARB)))
        self.assertEqual(outcome(check), "skip")
        self.assertIn("No ticket_field configured", message(check))

    def test_no_ticket_skips_once_collection_finished(self):
        check = self.run_field(component(), ticket_field=self.OPTION)
        self.assertEqual(outcome(check), "skip")

    def test_no_ticket_is_pending_while_collecting(self):
        check = self.run_field(component(), finished=False, ticket_field=self.OPTION)
        self.assertEqual(outcome(check), "pending")

    def test_unconfirmed_ticket_skips(self):
        ticket = {"id": "ARB-99", "source": {"tool": "jira"}, "tracker_error": "not_found"}
        check = self.run_field(component(ticket), ticket_field=self.OPTION,
                               allowed_field_values="Payments")
        self.assertEqual(outcome(check), "skip")
        self.assertIn("ARB-99", message(check))

    def test_select_option_matches_on_its_value(self):
        check = self.run_field(component(record(ARB)), ticket_field=self.OPTION,
                               allowed_field_values="Payments,Platform")
        self.assertEqual(outcome(check), "pass")

    def test_select_option_outside_the_allowed_list_fails(self):
        check = self.run_field(component(record(ARB)), ticket_field=self.OPTION,
                               allowed_field_values="Platform")
        self.assertEqual(outcome(check), "fail")
        self.assertEqual(
            message(check),
            "Ticket ARB-56 field native.jira.fields.customfield_10042 is 'Payments', "
            "which is not in the allowed list: 'Platform'.")

    def test_unset_custom_field_fails(self):
        # Jira returns an unset custom field as null.
        check = self.run_field(component(record(ARB)),
                               ticket_field="native.jira.fields.customfield_10044",
                               allowed_field_values="Payments")
        self.assertEqual(outcome(check), "fail")
        self.assertEqual(message(check),
                         "Ticket ARB-56 has no value for native.jira.fields.customfield_10044.")

    def test_field_the_ticket_does_not_have_fails(self):
        check = self.run_field(component(record(ARB)),
                               ticket_field="native.jira.fields.customfield_99999")
        self.assertEqual(outcome(check), "fail")
        self.assertIn("has no value for native.jira.fields.customfield_99999", message(check))

    def test_without_allowed_values_the_field_only_has_to_be_set(self):
        self.assertEqual(outcome(self.run_field(component(record(ARB)),
                                                ticket_field=self.OPTION)), "pass")
        self.assertEqual(outcome(self.run_field(component(record(TP)),
                                                ticket_field=self.OPTION)), "fail")

    def test_multi_select_passes_when_any_value_is_allowed(self):
        field = "native.jira.fields.customfield_10043"   # [PCI, PII]
        self.assertEqual(outcome(self.run_field(component(record(ARB)), ticket_field=field,
                                                allowed_field_values="PII")), "pass")
        check = self.run_field(component(record(ARB)), ticket_field=field,
                               allowed_field_values="None")
        self.assertEqual(outcome(check), "fail")
        self.assertIn("is 'PCI', 'PII'", message(check))

    def test_labels_match_as_strings(self):
        check = self.run_field(component(record(ARB)), ticket_field="native.jira.fields.labels",
                               allowed_field_values="payments")
        self.assertEqual(outcome(check), "pass")

    def test_empty_list_has_no_value(self):
        issue = with_fields(ARB, labels=[])
        check = self.run_field(component(record(issue)), ticket_field="native.jira.fields.labels")
        self.assertEqual(outcome(check), "fail")
        self.assertIn("has no value for native.jira.fields.labels", message(check))

    def test_user_matches_on_display_name_past_the_empty_name(self):
        # Jira users carry the deprecated `name` as "", so it must not win.
        field = "native.jira.fields.assignee"
        self.assertEqual(outcome(self.run_field(component(record(ARB)), ticket_field=field,
                                                allowed_field_values="Mia Krystof")), "pass")
        check = self.run_field(component(record(ARB)), ticket_field=field,
                               allowed_field_values="Someone Else")
        self.assertIn("is 'Mia Krystof'", message(check))

    def test_status_object_matches_on_its_name(self):
        check = self.run_field(component(record(ARB)), ticket_field="native.jira.fields.status",
                               allowed_field_values="Approved")
        self.assertEqual(outcome(check), "pass")

    def test_normalized_field(self):
        check = self.run_field(component(record(ARB)), ticket_field="type",
                               allowed_field_values="Submission")
        self.assertEqual(outcome(check), "pass")

    def test_number_field_matches_its_integral_value(self):
        issue = with_fields(ARB, customfield_10050=5.0)
        check = self.run_field(component(record(issue)),
                               ticket_field="native.jira.fields.customfield_10050",
                               allowed_field_values="4,5")
        self.assertEqual(outcome(check), "pass")

    def test_rich_text_field_cannot_be_compared(self):
        # description is an Atlassian Document Format object: set, but with no
        # value to compare against a list.
        with policy_vars(ticket_field="native.jira.fields.description",
                         allowed_field_values="anything"):
            with self.assertRaisesRegex(ValueError, "without a value, name or displayName"):
                ticket_field(node(component(record(ARB))))
        self.assertEqual(outcome(self.run_field(component(record(ARB)),
                                                ticket_field="native.jira.fields.description")),
                         "pass")

    def test_field_path_forms(self):
        for field in (".native.jira.fields.customfield_10042",
                      "native.jira.fields['customfield_10042']",
                      "['native'].jira.fields.customfield_10042.value"):
            with self.subTest(field=field):
                check = self.run_field(component(record(ARB)), ticket_field=field,
                                       allowed_field_values="Payments")
                self.assertEqual(outcome(check), "pass")

    def test_invalid_field_path_errors(self):
        with policy_vars(ticket_field="native.jira.fields.custom-field"):
            with self.assertRaisesRegex(ValueError, "Invalid path format"):
                ticket_field(node(component(record(ARB))))

    def test_ticket_path_points_the_check_at_the_second_reference(self):
        data = component(record(TP), record(ARB))
        vars = dict(ticket_field=self.OPTION, allowed_field_values="Payments")
        self.assertEqual(outcome(self.run_field(data, ticket_path=SECOND, **vars)), "pass")
        # The delivery ticket leaves the field unset.
        self.assertEqual(outcome(self.run_field(data, **vars)), "fail")


class TestParseList(unittest.TestCase):
    def test_forms(self):
        self.assertEqual(parse_list("x", "Approved, Done"), ["Approved", "Done"])
        self.assertEqual(parse_list("x", "Approved\nApproved with conditions\n"),
                         ["Approved", "Approved with conditions"])
        self.assertEqual(parse_list("x", '["Approved, with conditions", 5, true]'),
                         ["Approved, with conditions", "5", "true"])
        self.assertEqual(parse_list("x", "  "), [])

    def test_malformed_json_errors(self):
        with self.assertRaisesRegex(ValueError, "allowed_field_values: invalid JSON array"):
            parse_list("allowed_field_values", '["Approved"')


class TestDefaultPath(unittest.TestCase):
    """The six existing checks, unchanged when ticket_path is unset."""

    def test_present(self):
        self.assertEqual(outcome(ticket_present(node(component(record(TP))))), "pass")
        check = ticket_present(node(component()))
        self.assertEqual(outcome(check), "fail")
        self.assertEqual(message(check), "PR does not reference a ticket. "
                                         "Include a ticket ID in the PR title (e.g. [ABC-123]). "
                                         "Then comment `/lunar rerun jira` to re-check without "
                                         "a new commit.")
        self.assertEqual(outcome(ticket_present(node(component(), finished=False))), "pending")

    def test_valid(self):
        self.assertEqual(outcome(ticket_valid(node(component(record(TP))))), "pass")
        for error, text in (("not_found", "does not exist in Jira"),
                            ("unreachable", "Jira was unreachable")):
            check = ticket_valid(node(component({"id": "TP-9", "tracker_error": error})))
            self.assertEqual(outcome(check), "fail")
            self.assertIn(text, message(check))
        self.assertEqual(outcome(ticket_valid(node(component()))), "skip")

    def test_source_status_type(self):
        data = component(record(TP))
        with policy_vars(allowed_sources="jira", allowed_statuses="In Progress",
                         allowed_types="Story"):
            self.assertEqual(outcome(ticket_source(node(data))), "pass")
            self.assertEqual(outcome(ticket_status(node(data))), "pass")
            self.assertEqual(outcome(ticket_type(node(data))), "pass")
        with policy_vars(allowed_sources="linear", allowed_statuses="Done",
                         allowed_types="Bug"):
            self.assertEqual(outcome(ticket_source(node(data))), "fail")
            self.assertEqual(outcome(ticket_status(node(data))), "fail")
            self.assertEqual(outcome(ticket_type(node(data))), "fail")
        self.assertEqual(outcome(ticket_status(node(data))), "skip")

    def test_reuse(self):
        self.assertEqual(outcome(ticket_reuse(node(component(record(TP, reuse_count=1))))),
                         "pass")
        self.assertEqual(outcome(ticket_reuse(node(component(record(TP, reuse_count=4))))),
                         "fail")
        self.assertEqual(outcome(ticket_reuse(node(component(record(TP))))), "skip")


class TestSecondReference(unittest.TestCase):
    """ticket_path points every check at the second reference, independently of
    the delivery ticket next to it."""

    def run_check(self, check, data, **vars):
        # As the README configures it: the second jira import, renamed.
        vars.setdefault("rerun_collectors", "jira-architecture-review")
        with policy_vars(ticket_path=SECOND, **vars):
            return check(node(data))

    def test_present(self):
        self.assertEqual(outcome(self.run_check(ticket_present, component(None, record(ARB)))),
                         "pass")
        check = self.run_check(ticket_present, component(record(TP)))
        self.assertEqual(outcome(check), "fail")
        self.assertEqual(message(check),
                         "PR does not reference a ticket for .vcs.pr.architecture_review. "
                         "Include its key in the PR title or description. Then comment "
                         "`/lunar rerun jira-architecture-review` to re-check without a new "
                         "commit.")

    def test_valid(self):
        self.assertEqual(outcome(self.run_check(ticket_valid, component(record(TP), record(ARB)))),
                         "pass")
        check = self.run_check(ticket_valid, component(
            record(TP), {"id": "ARB-99", "tracker_error": "not_found"}))
        self.assertEqual(outcome(check), "fail")
        self.assertIn("ARB-99 does not exist in Jira", message(check))

    def test_status(self):
        data = component(record(TP), record(ARB))
        self.assertEqual(outcome(self.run_check(ticket_status, data, allowed_statuses="Approved")),
                         "pass")
        with policy_vars(allowed_statuses="Approved"):
            self.assertEqual(outcome(ticket_status(node(data))), "fail")   # TP-1: In Progress

    def test_checks_do_not_depend_on_the_delivery_ticket(self):
        # Only the second reference is present, so a check that still gated on
        # .vcs.pr.ticket would skip here instead of evaluating it.
        data = component(None, record(ARB, reuse_count=5))
        for check, vars, expected in (
                (ticket_status, {"allowed_statuses": "Approved"}, "pass"),
                (ticket_status, {"allowed_statuses": "Done"}, "fail"),
                (ticket_type, {"allowed_types": "Submission"}, "pass"),
                (ticket_type, {"allowed_types": "Story"}, "fail"),
                (ticket_source, {"allowed_sources": "jira"}, "pass"),
                (ticket_source, {"allowed_sources": "linear"}, "fail"),
                (ticket_valid, {}, "pass"),
                (ticket_reuse, {"max_ticket_reuse": "5"}, "pass"),
                (ticket_reuse, {"max_ticket_reuse": "4"}, "fail")):
            with self.subTest(check=check.__module__, vars=vars):
                self.assertEqual(outcome(self.run_check(check, data, **vars)), expected)

    def test_source_type_reuse(self):
        data = component(record(TP), record(ARB, reuse_count=5))
        self.assertEqual(outcome(self.run_check(ticket_source, data, allowed_sources="jira")),
                         "pass")
        self.assertEqual(outcome(self.run_check(ticket_type, data, allowed_types="Submission")),
                         "pass")
        check = self.run_check(ticket_reuse, data)
        self.assertEqual(outcome(check), "fail")
        self.assertIn("ARB-56 has been used in 5 other PRs", message(check))

    def test_path_without_the_leading_dot(self):
        with policy_vars(ticket_path="vcs.pr.architecture_review"):
            check = ticket_present(node(component(None, record(ARB))))
        self.assertEqual(outcome(check), "pass")

    def test_malformed_ticket_path_errors_rather_than_reading_as_no_ticket(self):
        checks = (ticket_present, ticket_valid, ticket_source, ticket_status,
                  ticket_type, ticket_reuse, ticket_field)
        for check in checks:
            with self.subTest(check=check.__module__):
                with policy_vars(ticket_path=".vcs.pr.architecture-review",
                                 ticket_field="status"):
                    with self.assertRaisesRegex(ValueError, "Invalid path format"):
                        check(node(component(record(TP), record(ARB))))


BOT = "dependabot[bot]"


class TestSkipAuthors(unittest.TestCase):
    """skip_authors skips every check on a PR opened by a listed login."""

    # A failing case per check, so a skip can only come from skip_authors.
    CASES = (
        (ticket_present, None, {}),
        (ticket_valid, {"id": "TP-9", "tracker_error": "not_found"}, {}),
        (ticket_source, record(TP), {"allowed_sources": "linear"}),
        (ticket_status, record(TP), {"allowed_statuses": "Done"}),
        (ticket_type, record(TP), {"allowed_types": "Bug"}),
        (ticket_reuse, record(TP, reuse_count=4), {}),
        (ticket_field, record(TP), {"ticket_field": TestTicketField.OPTION}),
    )

    def run_check(self, check, data, finished=True, **vars):
        with policy_vars(**vars):
            return check(node(data, finished))

    def test_listed_author_skips_every_check(self):
        for check, ticket, vars in self.CASES:
            with self.subTest(check=check.__module__):
                data = component(ticket, author=BOT)
                self.assertEqual(outcome(self.run_check(check, data, **vars)), "fail")
                result = self.run_check(check, data, skip_authors=BOT, **vars)
                self.assertEqual(outcome(result), "skip")
                self.assertEqual(message(result), "PR author dependabot[bot] is in skip_authors")

    def test_other_authors_are_checked(self):
        for check, ticket, vars in self.CASES:
            with self.subTest(check=check.__module__):
                result = self.run_check(check, component(ticket, author="octocat"),
                                        skip_authors=BOT, **vars)
                self.assertEqual(outcome(result), "fail")

    def test_login_matches_exactly_ignoring_case(self):
        for author, listed, expected in ((BOT, "Dependabot[Bot]", "skip"),
                                         ("AcmeReleaseBot", "acmereleasebot", "skip"),
                                         (BOT, "dependabot", "fail"),
                                         (BOT, "dependabot[bot]-preview", "fail")):
            with self.subTest(author=author, listed=listed):
                check = self.run_check(ticket_present, component(author=author),
                                       skip_authors=listed)
                self.assertEqual(outcome(check), expected)

    def test_list_forms(self):
        for listed in ("dependabot[bot], renovate[bot]", "dependabot[bot]\nrenovate[bot]\n",
                       '["dependabot[bot]", "renovate[bot]"]'):
            with self.subTest(listed=listed):
                check = self.run_check(ticket_present, component(author="renovate[bot]"),
                                       skip_authors=listed)
                self.assertEqual(outcome(check), "skip")

    def test_pends_until_the_author_is_collected(self):
        # The ticket can land before the author. Without skip_authors the check
        # fails right away, as it always has; with it, it waits for the author
        # instead of failing and then flipping to a skip.
        data = component({"id": "TP-9", "tracker_error": "not_found"})
        self.assertEqual(outcome(self.run_check(ticket_valid, data, finished=False)), "fail")
        self.assertEqual(outcome(self.run_check(ticket_valid, data, finished=False,
                                                skip_authors=BOT)), "pending")

    def test_pr_without_a_collected_author_is_checked(self):
        check = self.run_check(ticket_present, component(), skip_authors=BOT)
        self.assertEqual(outcome(check), "fail")

    def test_second_reference_import(self):
        data = component(record(TP), author=BOT)
        check = self.run_check(ticket_present, data, ticket_path=SECOND, skip_authors=BOT)
        self.assertEqual(outcome(check), "skip")

    def test_malformed_list_errors(self):
        with policy_vars(skip_authors='["dependabot[bot]"'):
            with self.assertRaisesRegex(ValueError, "skip_authors: invalid JSON array"):
                ticket_present(node(component(author=BOT)))


CHECK_NAMES = ("ticket-present", "ticket-valid", "ticket-source", "ticket-status",
               "ticket-type", "ticket-reuse", "ticket-field")


class TestRerunHint(unittest.TestCase):
    """rerun_collectors ends a failure the PR author can fix without a commit
    with the `/lunar rerun` comment that re-checks it."""

    def run_check(self, check, data, finished=True, **vars):
        with policy_vars(**vars):
            return check(node(data, finished))

    def test_every_fixable_failure_ends_with_the_comment(self):
        update = (" Update the ticket or the PR title, then comment `/lunar rerun jira` "
                  "to re-check without a new commit.")
        for check, ticket, vars, expected in (
                (ticket_present, None, {},
                 "PR does not reference a ticket. Include a ticket ID in the PR title "
                 "(e.g. [ABC-123]). Then comment `/lunar rerun jira` to re-check without "
                 "a new commit."),
                (ticket_valid, {"id": "TP-9", "tracker_error": "not_found"}, {},
                 "Ticket TP-9 does not exist in Jira. Correct the key in the PR title or "
                 "description, then comment `/lunar rerun jira` to re-check without a "
                 "new commit."),
                (ticket_valid, {"id": "TP-9", "tracker_error": "unreachable"}, {},
                 "Ticket TP-9 could not be validated: Jira was unreachable. Comment "
                 "`/lunar rerun jira` to retry once Jira is reachable."),
                (ticket_status, record(TP), {"allowed_statuses": "Approved"},
                 "Ticket TP-1 has status 'In Progress' which is not in the allowed list: "
                 "Approved." + update),
                (ticket_status, record(TP), {"disallowed_statuses": "In Progress"},
                 "Ticket TP-1 has status 'In Progress' which is in the disallowed list: "
                 "In Progress." + update),
                (ticket_type, record(TP), {"allowed_types": "Bug"},
                 "Ticket TP-1 has type 'Story' which is not in the allowed list: Bug."
                 + update),
                (ticket_source, record(TP), {"allowed_sources": "linear"},
                 "Ticket TP-1 comes from 'jira' which is not in the allowed list: linear. "
                 "Reference a ticket from an allowed tracker, then comment "
                 "`/lunar rerun jira` to re-check without a new commit."),
                (ticket_reuse, record(TP, reuse_count=4), {},
                 "Ticket TP-1 has been used in 4 other PRs (max allowed: 3). Create a new "
                 "ticket for this work. Reference it in the PR title, then comment "
                 "`/lunar rerun jira` to re-check without a new commit."),
                (ticket_field, record(TP), {"ticket_field": TestTicketField.OPTION},
                 "Ticket TP-1 has no value for native.jira.fields.customfield_10042."
                 + update),
                (ticket_field, record(ARB), {"ticket_field": TestTicketField.OPTION,
                                             "allowed_field_values": "Platform"},
                 "Ticket ARB-56 field native.jira.fields.customfield_10042 is 'Payments', "
                 "which is not in the allowed list: 'Platform'." + update)):
            with self.subTest(check=check.__module__, vars=vars):
                result = self.run_check(check, component(ticket), **vars)
                self.assertEqual(outcome(result), "fail")
                self.assertEqual(message(result), expected)
                # Set to "", the failure reads as it did before the input: the
                # hinted message is that message plus the hint.
                off = self.run_check(check, component(ticket), rerun_collectors="", **vars)
                self.assertEqual(outcome(off), "fail")
                self.assertNotIn("/lunar rerun", message(off))
                self.assertTrue(expected.startswith(message(off) + " "))

    def test_defaults_to_jira_and_empty_turns_it_off(self):
        default = self.run_check(ticket_present, component())
        self.assertIn("comment `/lunar rerun jira` to re-check", message(default))
        self.assertEqual(message(self.run_check(ticket_present, component(),
                                                rerun_collectors="jira")), message(default))
        for off in ("", "  ", " , "):
            with self.subTest(off=off):
                result = self.run_check(ticket_present, component(), rerun_collectors=off)
                self.assertEqual(message(result), "PR does not reference a ticket. "
                                 "Include a ticket ID in the PR title (e.g. [ABC-123]).")

    def test_no_hint_where_a_rerun_cannot_fix_it(self):
        # tracker_error unset is also what a ticket reads when Jira validation
        # isn't configured, and a valid: false from another collector says
        # nothing about the fix.
        for ticket in ({"id": "TP-9"}, {"id": "TP-9", "valid": False}):
            with self.subTest(ticket=ticket):
                result = self.run_check(ticket_valid, component(ticket),
                                        rerun_collectors="jira")
                self.assertEqual(outcome(result), "fail")
                self.assertNotIn("/lunar rerun", message(result))

    def test_renamed_collector_import(self):
        # A collector imported with `name: tickets` is `tickets.ticket` on the
        # Hub, and `/lunar rerun` matches that name, so the hint takes whatever
        # the deployment wrote and never falls back to the library's default.
        result = self.run_check(ticket_present, component(), rerun_collectors="tickets")
        self.assertIn("comment `/lunar rerun tickets` to re-check", message(result))
        self.assertNotIn("jira", message(result))

    def test_renamed_policy_import(self):
        # The policy can't see the name its import gives it (the Hub passes it
        # no name), so no message names a policy: the report's check header
        # carries the effective name, e.g. `architecture-review.ticket-present`.
        # This is the second-reference import from the README, with its own
        # renamed jira collector import.
        data = component(record(TP), {"id": "ARB-99", "tracker_error": "not_found"})
        vars = dict(ticket_path=SECOND, rerun_collectors="jira-architecture-review")
        present = self.run_check(ticket_present, component(record(TP)), **vars)
        self.assertEqual(message(present),
                         "PR does not reference a ticket for .vcs.pr.architecture_review. "
                         "Include its key in the PR title or description. Then comment "
                         "`/lunar rerun jira-architecture-review` to re-check without a new "
                         "commit.")
        valid = self.run_check(ticket_valid, data, **vars)
        self.assertIn("`/lunar rerun jira-architecture-review`", message(valid))
        for result in (present, valid):
            for name in CHECK_NAMES + ("architecture-review.",):
                self.assertNotIn(name, message(result))

    def test_names_as_the_hub_parses_them(self):
        # The Hub splits names on commas and whitespace; the hint joins them
        # with commas, in the order given, without repeats.
        both = "/lunar rerun github.pull-request,jira"
        for raw, command in (("jira", "/lunar rerun jira"),
                             ("github.pull-request,jira", both),
                             (" github.pull-request, jira ", both),
                             ("github.pull-request jira\njira", both),
                             ("jira.ticket-from-json", "/lunar rerun jira.ticket-from-json")):
            with self.subTest(raw=raw):
                result = self.run_check(ticket_present, component(), rerun_collectors=raw)
                self.assertIn(f"`{command}`", message(result))

    def test_malformed_name_drops_the_hint_without_changing_the_verdict(self):
        for raw in ("jira`", '["jira"]', "jira](https://example.com)", "-jira"):
            with self.subTest(raw=raw):
                log = io.StringIO()
                with redirect_stderr(log):
                    failing = self.run_check(ticket_present, component(), rerun_collectors=raw)
                self.assertIn("rerun_collectors: no rerun hint", log.getvalue())
                self.assertEqual(outcome(failing), "fail")
                self.assertEqual(message(failing), "PR does not reference a ticket. "
                                 "Include a ticket ID in the PR title (e.g. [ABC-123]).")
                with redirect_stderr(io.StringIO()):
                    passing = self.run_check(ticket_type, component(record(TP)),
                                             rerun_collectors=raw, allowed_types="Story")
                self.assertEqual(outcome(passing), "pass")

    def test_other_outcomes_are_unchanged(self):
        vars = {"rerun_collectors": "jira"}
        self.assertEqual(outcome(self.run_check(ticket_present, component(record(TP)),
                                                **vars)), "pass")
        self.assertEqual(outcome(self.run_check(ticket_present, component(), finished=False,
                                                **vars)), "pending")
        self.assertEqual(outcome(self.run_check(ticket_valid, component(), **vars)), "skip")
        skipped = self.run_check(ticket_present, component(author=BOT), skip_authors=BOT,
                                 **vars)
        self.assertEqual(outcome(skipped), "skip")
        self.assertEqual(message(skipped), "PR author dependabot[bot] is in skip_authors")


if __name__ == "__main__":
    unittest.main()

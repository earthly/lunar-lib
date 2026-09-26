"""Unit tests for the ticket policy checks.

fixtures/jira-issue-*.json are Jira REST API v3 issue responses: the Get issue
example from Atlassian's reference with a status, issue type, assignee,
priority, labels and custom fields added in the documented shapes. The tests
wrap them in the ticket record the jira collector writes, so `ticket_field`
paths run against the same structure a real import produces.
"""

import importlib.util
import json
import os
import sys
import unittest
from contextlib import contextmanager
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


def component(ticket=None, second=None):
    pr = {"number": 8, "title": "[TP-1] Add payment retries"}
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
            "which is not in the allowed list: Platform.")

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
                                         "Include a ticket ID in the PR title (e.g. [ABC-123]).")
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
        with policy_vars(ticket_path=SECOND, **vars):
            return check(node(data))

    def test_present(self):
        self.assertEqual(outcome(self.run_check(ticket_present, component(None, record(ARB)))),
                         "pass")
        check = self.run_check(ticket_present, component(record(TP)))
        self.assertEqual(outcome(check), "fail")
        self.assertEqual(message(check),
                         "PR does not reference a ticket for .vcs.pr.architecture_review. "
                         "Include its key in the PR title or description.")

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


if __name__ == "__main__":
    unittest.main()

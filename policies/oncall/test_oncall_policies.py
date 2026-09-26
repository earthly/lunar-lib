"""Unit tests for the oncall policy checks. Wired into the root +test target."""

import os
import unittest
from unittest import mock

from lunar_policy import CheckStatus, Node

from escalation_defined import main as check_escalation
from min_participants import main as check_min_participants
from schedule_configured import main as check_schedule


def node(oncall=None, finished=True):
    data = {} if oncall is None else {"oncall": oncall}
    return Node.from_component_json(data, {"workflows_finished": finished})


def failures(check):
    return [r.failure_message for r in check._results if r.result == CheckStatus.FAIL]


# The normalized shape every oncall collector writes (see collectors/datadog's
# example_component_json; pagerduty and opsgenie write the same keys).
STAFFED = {
    "service": {"id": "8f3b4c1e-6d2a-4b7e-9c1f-2a5d8e7b3c90", "name": "Payments"},
    "escalation": {"exists": True, "levels": 2, "policy_name": "Payments escalation"},
    "schedule": {"exists": True, "participants": 2, "rotation": "weekly"},
    "summary": {"has_oncall": True, "has_escalation": True, "min_participants": 2},
    "source": {"tool": "datadog", "integration": "api"},
}

# What a collector records for a team whose routing rules page no policy.
UNSTAFFED = {
    "service": {"id": "8f3b4c1e-6d2a-4b7e-9c1f-2a5d8e7b3c90", "name": "Payments"},
    "escalation": {"exists": False, "levels": 0, "policy_name": ""},
    "schedule": {"exists": False, "participants": 0, "rotation": "unknown"},
    "summary": {"has_oncall": False, "has_escalation": False, "min_participants": 0},
    "source": {"tool": "datadog", "integration": "api"},
}


class ScheduleConfiguredTest(unittest.TestCase):
    def test_pass_when_a_schedule_exists(self):
        self.assertEqual(check_schedule(node(STAFFED)).status, CheckStatus.PASS)

    def test_fail_when_no_schedule(self):
        c = check_schedule(node(UNSTAFFED))
        self.assertEqual(c.status, CheckStatus.FAIL)
        self.assertIn("no on-call schedule", failures(c)[0])

    def test_fail_when_no_oncall_data_after_collection(self):
        self.assertEqual(check_schedule(node()).status, CheckStatus.FAIL)

    def test_pending_while_collection_runs(self):
        self.assertEqual(check_schedule(node(finished=False)).status, CheckStatus.PENDING)


class EscalationDefinedTest(unittest.TestCase):
    def test_pass_when_a_policy_exists(self):
        self.assertEqual(check_escalation(node(STAFFED)).status, CheckStatus.PASS)

    def test_fail_when_no_policy(self):
        c = check_escalation(node(UNSTAFFED))
        self.assertEqual(c.status, CheckStatus.FAIL)
        self.assertIn("no escalation policy", failures(c)[0])

    def test_fail_when_no_oncall_data_after_collection(self):
        self.assertEqual(check_escalation(node()).status, CheckStatus.FAIL)

    def test_pending_while_collection_runs(self):
        self.assertEqual(check_escalation(node(finished=False)).status, CheckStatus.PENDING)


class MinParticipantsTest(unittest.TestCase):
    def test_pass_at_the_default_minimum(self):
        self.assertEqual(check_min_participants(node(STAFFED)).status, CheckStatus.PASS)

    def test_fail_below_the_default_minimum(self):
        oncall = {**STAFFED, "schedule": {"exists": True, "participants": 1, "rotation": "weekly"}}
        c = check_min_participants(node(oncall))
        self.assertEqual(c.status, CheckStatus.FAIL)
        self.assertIn("1 participant(s); at least 2 required", failures(c)[0])

    def test_fail_when_the_schedule_is_empty(self):
        self.assertEqual(check_min_participants(node(UNSTAFFED)).status, CheckStatus.FAIL)

    def test_min_participants_input(self):
        with mock.patch.dict(os.environ, {"LUNAR_VAR_min_participants": "3"}):
            c = check_min_participants(node(STAFFED))
        self.assertEqual(c.status, CheckStatus.FAIL)
        self.assertIn("at least 3 required", failures(c)[0])
        with mock.patch.dict(os.environ, {"LUNAR_VAR_min_participants": "1"}):
            self.assertEqual(check_min_participants(node(UNSTAFFED)).status, CheckStatus.FAIL)
            oncall = {**STAFFED, "schedule": {"exists": True, "participants": 1, "rotation": "daily"}}
            self.assertEqual(check_min_participants(node(oncall)).status, CheckStatus.PASS)

    def test_fail_when_no_oncall_data_after_collection(self):
        c = check_min_participants(node())
        self.assertEqual(c.status, CheckStatus.FAIL)
        self.assertIn("no participants configured", failures(c)[0])

    def test_pending_while_collection_runs(self):
        self.assertEqual(check_min_participants(node(finished=False)).status, CheckStatus.PENDING)


if __name__ == "__main__":
    unittest.main()

"""Unit tests for oncall.service-mapped. Wired into the root +test target."""

import unittest

from lunar_policy import CheckStatus, Node

from service_mapped import main as check

SOURCE = {"tool": "pagerduty", "integration": "api"}
SEARCHED = [
    "meta:pagerduty/service-id",
    "input:service_id",
    "component:default/checkout",
    "system:default/payment-platform",
    "file:catalog-info.yaml",
]


def node(oncall=None, finished=True):
    data = {} if oncall is None else {"oncall": oncall}
    return Node.from_component_json(data, {"workflows_finished": finished})


def outcome(c):
    # Check.status reports a skip as PASS, so read the recorded result.
    return c._results[0].result


class ServiceMappedTest(unittest.TestCase):
    def test_pass_when_mapped(self):
        c = check(node({"source": SOURCE, "service": {"id": "PSYS001", "discovered_via": "system:default/payment-platform"}}))
        self.assertEqual(outcome(c), CheckStatus.PASS)

    def test_pass_when_mapped_but_pagerduty_could_not_be_read(self):
        # A PagerDuty 404 still records the mapping; the other checks report the rest.
        c = check(node({"source": SOURCE, "service": {"id": "PGONE00", "discovered_via": "file:catalog-info.yaml"}}))
        self.assertEqual(outcome(c), CheckStatus.PASS)

    def test_pass_when_another_collector_maps_it(self):
        oncall = {"source": {"tool": "datadog"}, "service": {"id": "team-1"}, "unmapped": {"searched": SEARCHED}}
        self.assertEqual(outcome(check(node(oncall))), CheckStatus.PASS)

    def test_fail_when_unmapped(self):
        c = check(node({"source": SOURCE, "unmapped": {"searched": SEARCHED}}))
        self.assertEqual(outcome(c), CheckStatus.FAIL)
        self.assertEqual(
            c.failure_reasons,
            [
                "No PagerDuty service is mapped to this component (looked in: meta:pagerduty/service-id, "
                "input:service_id, component:default/checkout, system:default/payment-platform, "
                "file:catalog-info.yaml). Annotate its Backstage Component, System or Domain with "
                "pagerduty.com/service-id, or set the pagerduty/service-id meta or the collector's "
                "service_id input."
            ],
        )

    def test_fail_message_drops_repeats_from_code_and_cron(self):
        c = check(node({"source": SOURCE, "unmapped": {"searched": SEARCHED[:2] + SEARCHED[:2]}}))
        self.assertIn("(looked in: meta:pagerduty/service-id, input:service_id).", c.failure_reasons[0])

    def test_fail_without_a_searched_list(self):
        c = check(node({"source": SOURCE, "unmapped": {}}))
        self.assertEqual(outcome(c), CheckStatus.FAIL)
        self.assertTrue(c.failure_reasons[0].startswith("No PagerDuty service is mapped to this component. "))

    def test_generic_wording_for_other_tools(self):
        c = check(node({"source": {"tool": "opsgenie"}, "unmapped": {"searched": ["input:team_id"]}}))
        self.assertEqual(
            c.failure_reasons,
            [
                "No on-call service is mapped to this component (looked in: input:team_id). "
                "Map it in your on-call collector's configuration."
            ],
        )

    def test_skip_when_no_collector_ran(self):
        c = check(node())
        self.assertEqual(outcome(c), CheckStatus.SKIPPED)
        self.assertIn("No on-call collector reported a service lookup", c._results[0].failure_message)

    def test_skip_when_only_other_oncall_data(self):
        # dr-docs writes .oncall.disaster_recovery on every component.
        self.assertEqual(outcome(check(node({"disaster_recovery": {"exercise_count": 0}}))), CheckStatus.SKIPPED)

    def test_skip_when_a_collector_ran_but_recorded_no_lookup(self):
        # The opsgenie collector writes only .oncall.source when its API call fails.
        self.assertEqual(outcome(check(node({"source": {"tool": "opsgenie"}}))), CheckStatus.SKIPPED)

    def test_pending_while_collection_runs(self):
        self.assertEqual(check(node(finished=False)).status, CheckStatus.PENDING)

    def test_pending_while_collection_runs_even_if_unmapped_so_far(self):
        c = check(node({"source": SOURCE, "unmapped": {"searched": SEARCHED}}, finished=False))
        self.assertEqual(c.status, CheckStatus.PENDING)

    def test_mapped_passes_before_collection_finishes(self):
        c = check(node({"service": {"id": "PSYS001"}}, finished=False))
        self.assertEqual(outcome(c), CheckStatus.PASS)


if __name__ == "__main__":
    unittest.main()

"""Unit tests for the compliance-docs policy checks."""

import importlib.util
import os
import unittest
from datetime import date, timedelta

from lunar_policy import CheckStatus, Node

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(filename):
    spec = importlib.util.spec_from_file_location(filename[:-3].replace("-", "_"), os.path.join(HERE, filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pentest_report_recent = _load("pentest-report-recent.py")

TODAY = date(2026, 9, 26)


def ago(days):
    return (TODAY - timedelta(days=days)).isoformat()


def pentest(*dates):
    return {"compliance": {"penetration_testing": {
        "reports": [{"date": d, "path": f"docs/pentests/{d}.md"} for d in dates],
    }}}


class PentestReportRecentTest(unittest.TestCase):
    def run_check(self, data, finished=True, max_days=None):
        node = Node.from_component_json(data, {"workflows_finished": finished})
        return pentest_report_recent.main(node, max_days_override=max_days, today=TODAY)

    def assertFailsWith(self, check, message):
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertEqual(check.failure_reasons, [message])

    def assertSkipped(self, check):
        # Check.status reports a skip as PASS; the result records the skip.
        self.assertEqual([r.result for r in check._results], [CheckStatus.SKIPPED])
        self.assertEqual(
            check._results[0].failure_message,
            "No pen-test data collected; the compliance-docs collector doesn't run on this component",
        )

    def test_recent_report_passes(self):
        self.assertEqual(self.run_check(pentest(ago(30))).status, CheckStatus.PASS)

    def test_report_exactly_at_the_limit_passes(self):
        self.assertEqual(self.run_check(pentest(ago(365))).status, CheckStatus.PASS)

    def test_report_one_day_past_the_limit_fails(self):
        self.assertFailsWith(
            self.run_check(pentest(ago(366))),
            f"Last pen-test report was 366 days ago on {ago(366)} (maximum allowed: 365)",
        )

    def test_newest_report_wins_regardless_of_order(self):
        # Two writers' arrays concatenate on merge, so order isn't guaranteed.
        self.assertEqual(self.run_check(pentest(ago(700), ago(10), ago(400))).status, CheckStatus.PASS)

    def test_max_days_override(self):
        self.assertFailsWith(
            self.run_check(pentest(ago(100)), max_days="90"),
            f"Last pen-test report was 100 days ago on {ago(100)} (maximum allowed: 90)",
        )

    def test_max_days_from_input(self):
        os.environ["LUNAR_VAR_max_days_since_pentest"] = "180"
        try:
            self.assertEqual(self.run_check(pentest(ago(170))).status, CheckStatus.PASS)
            self.assertEqual(self.run_check(pentest(ago(190))).status, CheckStatus.FAIL)
        finally:
            del os.environ["LUNAR_VAR_max_days_since_pentest"]

    def test_invalid_max_days_raises(self):
        for value in ("abc", "0", "-5", "1.5"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.run_check(pentest(ago(30)), max_days=value)

    # The collector writes `reports` wherever it runs, so no data at all means
    # the component is out of scope, while an empty list means no records.
    def test_no_pentest_data_skips_once_collection_finishes(self):
        self.assertSkipped(self.run_check({}))

    def test_no_pentest_data_pends_while_collection_runs(self):
        self.assertEqual(self.run_check({}, finished=False).status, CheckStatus.PENDING)

    def test_other_compliance_data_without_pentest_data_skips(self):
        self.assertSkipped(self.run_check({"compliance": {"regimes": ["soc2"]}}))

    def test_empty_reports_fails(self):
        self.assertFailsWith(self.run_check(pentest()), pentest_report_recent.NO_RECORDS)

    def test_empty_reports_fail_while_collection_runs(self):
        self.assertFailsWith(self.run_check(pentest(), finished=False), pentest_report_recent.NO_RECORDS)

    def test_reports_that_are_not_a_list_fail(self):
        for reports in ({"2026-09-01": {"date": "2026-09-01"}}, 3, "2026-09-01"):
            with self.subTest(reports=reports):
                data = {"compliance": {"penetration_testing": {"reports": reports}}}
                self.assertFailsWith(self.run_check(data), pentest_report_recent.NO_RECORDS)

    def test_undated_records_fail(self):
        data = {"compliance": {"penetration_testing": {"reports": [
            {"date": "not-a-date"}, {"date": "2026-02-30"}, {"path": "docs/pentests/x.md"},
        ]}}}
        self.assertFailsWith(self.run_check(data), pentest_report_recent.NO_RECORDS)

    def test_timestamp_dates_are_read_as_dates(self):
        data = {"compliance": {"penetration_testing": {"reports": [{"date": ago(20) + "T09:30:00Z"}]}}}
        self.assertEqual(self.run_check(data).status, CheckStatus.PASS)

    def test_only_future_records_fail(self):
        self.assertFailsWith(
            self.run_check(pentest("2027-01-15", "2062-03-14")),
            "Every pen-test report record is dated after today (earliest: 2027-01-15)",
        )

    def test_future_record_does_not_count_as_current(self):
        self.assertFailsWith(
            self.run_check(pentest("2062-03-14", ago(400))),
            f"Last pen-test report was 400 days ago on {ago(400)} "
            "(maximum allowed: 365; ignored 1 record(s) dated after today)",
        )

    def test_future_record_alongside_a_current_one_passes(self):
        self.assertEqual(self.run_check(pentest("2062-03-14", ago(5))).status, CheckStatus.PASS)

    def test_report_dated_today_passes(self):
        self.assertEqual(self.run_check(pentest(TODAY.isoformat())).status, CheckStatus.PASS)

    def test_report_dated_tomorrow_counts_as_today(self):
        # "Today" is UTC; a team east of UTC can already be on the next day.
        check = self.run_check(pentest(ago(-1)))
        self.assertEqual(check.status, CheckStatus.PASS)
        self.assertEqual(check._results[0].args, ["0"])

    def test_report_two_days_ahead_is_future(self):
        self.assertFailsWith(
            self.run_check(pentest(ago(-2))),
            f"Every pen-test report record is dated after today (earliest: {ago(-2)})",
        )


if __name__ == "__main__":
    unittest.main()

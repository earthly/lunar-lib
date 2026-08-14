"""Unit tests for the on-call policy checks.

The regression these guard (ENG-1537): the three on-call checks collapsed
three different states into one hard ``fail`` telling the user to go configure
something.

* **No on-call tool connected.** ``.oncall`` is absent entirely. The check does
  not apply and must ``skip`` -- the shape ``policies/observability/*`` already
  uses. Reporting "you have no on-call schedule" to a component that does not
  use PagerDuty or OpsGenie is noise.
* **The collector ran but bailed.** Both collectors ``exit 0`` on a missing
  token, an unresolved service, or an API error, and the pagerduty one does so
  *after* writing ``.oncall.source``. ``.oncall.summary`` is the final write on
  the success path, so its absence distinguishes "the collector could not
  report" from "the tool reports no schedule". This must fail against the
  collector, not against the user's on-call configuration.
* **The collector completed.** Evaluate the actual value.

The interim case matters too, and is the ENG-1114 shape: while collection is
still running (``workflows_finished=False``) a missing path raises NoDataError
out of ``.exists()``, which the Check context manager turns into PENDING. That
is why the gates use ``.exists()`` and not ``get_value_or_default``.
"""

import contextlib
import importlib.util
import io
import json
import sys
import unittest
from pathlib import Path

from lunar_policy import Node, CheckStatus


def load_policy(filename):
    policy_dir = Path(__file__).parent
    modname = filename.replace("-", "_")
    spec = importlib.util.spec_from_file_location(modname, policy_dir / f"{filename}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.main


def run(main, data, workflows_finished=True):
    """Run a policy and return (rollup status, emitted assertions).

    Check.status reports SKIPPED as PASS, so the assertions are needed to tell
    a skip from a genuine pass. The check prints its result JSON to stdout;
    capture rather than discard it.
    """
    node = Node.from_component_json(data, bundle_info={"workflows_finished": workflows_finished})
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        check = main(node)

    assertions = []
    for line in buf.getvalue().splitlines():
        try:
            assertions = json.loads(line).get("assertions", [])
        except json.JSONDecodeError:
            continue
    return check.status, assertions


def was_skipped(assertions):
    return any(a.get("result") == "skipped" for a in assertions)


def failure_messages(assertions):
    return " ".join(
        a.get("failure_message") or "" for a in assertions if a.get("result") == "fail"
    )


# Every check reads the same two gates, so the gate matrix is shared.
CHECKS = ["schedule_configured", "escalation_defined", "min_participants"]

# The collector ran to completion and the service is properly configured.
COMPLIANT = {
    "oncall": {
        "source": {"tool": "pagerduty", "integration": "api"},
        "service": {"id": "PXXXXXX", "name": "svc"},
        "escalation": {"exists": True, "levels": 2},
        "schedule": {"exists": True, "participants": 3, "rotation": "weekly"},
        "summary": {"has_oncall": True, "has_escalation": True, "min_participants": 3},
    }
}

# The collector ran to completion and the service genuinely has nothing set up.
NON_COMPLIANT = {
    "oncall": {
        "source": {"tool": "pagerduty", "integration": "api"},
        "service": {"id": "PXXXXXX", "name": "svc"},
        "escalation": {"exists": False, "levels": 0},
        "schedule": {"exists": False, "participants": 1, "rotation": ""},
        "summary": {"has_oncall": False, "has_escalation": False, "min_participants": 1},
    }
}

# What pagerduty's oncall.sh leaves behind when the API call fails: source is
# written at the top, then it exits 0 before anything else.
BAILED_COLLECTOR = {"oncall": {"source": {"tool": "pagerduty", "integration": "api"}}}


class TestOnCallGates(unittest.TestCase):
    def test_no_oncall_tool_skips(self):
        for name in CHECKS:
            with self.subTest(check=name):
                status, assertions = run(load_policy(name), {})
                self.assertTrue(
                    was_skipped(assertions),
                    f"{name} should skip when no on-call tool has written data",
                )
                self.assertNotEqual(status, CheckStatus.FAIL)

    def test_absent_data_pends_during_collection(self):
        # ENG-1114: the gate must not resolve terminally while collectors are
        # still running. get_value_or_default here would skip prematurely.
        for name in CHECKS:
            with self.subTest(check=name):
                status, _ = run(load_policy(name), {}, workflows_finished=False)
                self.assertEqual(status, CheckStatus.PENDING)

    def test_bailed_collector_fails_against_the_collector(self):
        for name in CHECKS:
            with self.subTest(check=name):
                status, assertions = run(load_policy(name), BAILED_COLLECTOR)
                self.assertEqual(status, CheckStatus.FAIL)
                self.assertFalse(
                    was_skipped(assertions),
                    f"{name} must not hide a broken collector behind a skip",
                )
                self.assertIn(
                    "collector did not finish",
                    failure_messages(assertions),
                    f"{name} should name the collector, not the user's on-call config",
                )

    def test_complete_and_compliant_passes(self):
        for name in CHECKS:
            with self.subTest(check=name):
                status, assertions = run(load_policy(name), COMPLIANT)
                self.assertEqual(status, CheckStatus.PASS)
                self.assertFalse(was_skipped(assertions))

    def test_complete_and_non_compliant_fails_against_the_service(self):
        # The real failure still reports, and still says what to configure --
        # the gates must not have swallowed it.
        expected = {
            "schedule_configured": "no on-call schedule configured",
            "escalation_defined": "no escalation policy configured",
            "min_participants": "participant(s)",
        }
        for name in CHECKS:
            with self.subTest(check=name):
                status, assertions = run(load_policy(name), NON_COMPLIANT)
                self.assertEqual(status, CheckStatus.FAIL)
                self.assertIn(expected[name], failure_messages(assertions))


if __name__ == "__main__":
    unittest.main()

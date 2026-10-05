#!/usr/bin/env python3
"""Tests for oncall.sh.

oncall.sh reads a team's Datadog On-Call routing rules, escalation policy and
schedule over the API and writes the tool-agnostic .oncall shape with
`lunar collect`. These tests run the real script with stub `curl` and `lunar`
executables on PATH. The stub curl answers from fixtures/, which hold API
responses in the JSON:API shapes of Datadog's published v2 OpenAPI spec.
"""

import copy
import json
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "oncall.sh")
FIXTURES = os.path.join(HERE, "fixtures")

TEAM_ID = "8f3b4c1e-6d2a-4b7e-9c1f-2a5d8e7b3c90"
POLICY_ID = "b7a1e2d4-3c5f-4e6a-8b9c-0d1e2f3a4b5c"
SCHEDULE_ID = "d4c3b2a1-9f8e-4d7c-a6b5-c4d3e2f1a0b9"

TEAMS = "/api/v2/team"
RULES = f"/api/v2/on-call/teams/{TEAM_ID}/routing-rules"
POLICY = f"/api/v2/on-call/escalation-policies/{POLICY_ID}"
SCHEDULE = f"/api/v2/on-call/schedules/{SCHEDULE_ID}"
OTHER_POLICY_ID = "0a0b0c0d-0e0f-4a1b-8c2d-000000000001"
OTHER_POLICY = f"/api/v2/on-call/escalation-policies/{OTHER_POLICY_ID}"

# Stub curl: logs each request, then answers from $MOCK_DIR/routes.json, keyed
# by URL path. A route is one response or a list consumed in order (the last
# repeats). Writes the body to the -o file and prints the status, the way
# `curl -o FILE -w '%{http_code}'` does. NETFAIL mimics a connection failure.
CURL_STUB = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    import json, os, sys, urllib.parse
    args, out, url, headers, i = sys.argv[1:], None, None, [], 0
    while i < len(args):
        a = args[i]
        if a == "-o":
            out = args[i + 1]; i += 2; continue
        if a == "-H":
            headers.append(args[i + 1]); i += 2; continue
        if a in ("-w", "--retry", "--retry-delay", "--retry-max-time", "--max-time"):
            i += 2; continue
        if a.startswith("https://") or a.startswith("http://"):
            url = a
        i += 1
    mock = os.environ["MOCK_DIR"]
    with open(os.path.join(mock, "requests.log"), "a") as f:
        f.write(json.dumps({"url": url, "headers": headers}) + "\\n")
    path = urllib.parse.urlsplit(url).path
    routes = json.load(open(os.path.join(mock, "routes.json")))
    entry = routes.get(path)
    if entry is None:
        sys.stderr.write("mock curl: no route for " + path + "\\n")
        sys.stdout.write("599")
        sys.exit(0)
    if isinstance(entry, list):
        counter = os.path.join(mock, "n" + path.replace("/", "_"))
        n = int(open(counter).read()) if os.path.exists(counter) else 0
        open(counter, "w").write(str(n + 1))
        entry = entry[min(n, len(entry) - 1)]
    if entry["status"] == "NETFAIL":
        sys.stderr.write("curl: (7) Failed to connect\\n")
        sys.stdout.write("000")
        sys.exit(7)
    body = entry.get("body", "")
    if "raw" in entry:
        body = entry["raw"]
    elif "json" in entry:
        body = json.dumps(entry["json"])
    elif body:
        body = open(os.path.join(os.environ["FIXTURES"], body)).read()
    with open(out, "w") as f:
        f.write(body)
    sys.stdout.write(str(entry["status"]))
    """
)

# Stub lunar: records each `lunar collect -j <path> -` write (path + parsed JSON).
LUNAR_STUB = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    import json, os, sys
    if sys.argv[1:3] == ["collect", "-j"] and sys.argv[4:] == ["-"]:
        value = json.loads(sys.stdin.read())
        with open(os.environ["LUNAR_CAPTURE"], "a") as f:
            f.write(json.dumps({"path": sys.argv[3], "value": value}) + "\\n")
    else:
        sys.stderr.write("unexpected lunar call: " + " ".join(sys.argv[1:]) + "\\n")
        sys.exit(2)
    """
)


def fixture(name):
    with open(os.path.join(FIXTURES, name)) as f:
        return json.load(f)


def ok(body):
    return {"status": 200, "body": body} if isinstance(body, str) else {"status": 200, "json": body}


NOT_FOUND = {"status": 404, "body": "not-found.json"}
FORBIDDEN = {"status": 403, "body": "forbidden.json"}


def happy_routes():
    return {
        TEAMS: ok("teams-search.json"),
        RULES: ok("routing-rules.json"),
        POLICY: ok("escalation-policy.json"),
        SCHEDULE: ok("schedule.json"),
    }


def merge(dst, src):
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            merge(dst[k], v)
        else:
            dst[k] = v


class Result:
    def __init__(self, proc, writes, requests):
        self.rc = proc.returncode
        self.stderr = proc.stderr
        self.writes = writes
        self.requests = requests
        self.json = {}
        for w in writes:
            node = {}
            cur = node
            keys = w["path"].lstrip(".").split(".")
            for k in keys[:-1]:
                cur[k] = {}
                cur = cur[k]
            cur[keys[-1]] = w["value"]
            merge(self.json, node)

    @property
    def oncall(self):
        return self.json.get("oncall", {})

    def paths_requested(self):
        return [urllib.parse.urlsplit(r["url"]).path for r in self.requests]


class OncallCollectorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="dd-oncall-test-")
        self.bin = os.path.join(self.tmp, "bin")
        self.mock = os.path.join(self.tmp, "mock")
        os.makedirs(self.bin)
        os.makedirs(self.mock)
        for name, body in (("curl", CURL_STUB), ("lunar", LUNAR_STUB)):
            path = os.path.join(self.bin, name)
            with open(path, "w") as f:
                f.write(body)
            os.chmod(path, 0o755)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_collector(self, routes=None, team="payments", secrets=True, **env_extra):
        with open(os.path.join(self.mock, "routes.json"), "w") as f:
            json.dump(happy_routes() if routes is None else routes, f)
        for name in ("requests.log", "collect.log"):
            path = os.path.join(self.mock, name)
            if os.path.exists(path):
                os.remove(path)
        # Built from scratch so nothing from the caller's environment
        # (LUNAR_*, DATADOG_SITE) leaks into a case.
        env = {
            "PATH": self.bin + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": self.tmp,
            "TMPDIR": self.tmp,
            "MOCK_DIR": self.mock,
            "FIXTURES": FIXTURES,
            "LUNAR_CAPTURE": os.path.join(self.mock, "collect.log"),
            "LUNAR_COMPONENT_ID": "github.com/acme/payment-api",
        }
        if team is not None:
            env["LUNAR_VAR_TEAM"] = team
        if secrets:
            env["LUNAR_SECRET_DATADOG_API_KEY"] = "test-api-key"
            env["LUNAR_SECRET_DATADOG_APP_KEY"] = "test-app-key"
        env.update(env_extra)
        proc = subprocess.run(["bash", SCRIPT], env=env, capture_output=True, text=True, timeout=60)

        def read_lines(name):
            path = os.path.join(self.mock, name)
            if not os.path.exists(path):
                return []
            with open(path) as f:
                return [json.loads(line) for line in f if line.strip()]

        return Result(proc, read_lines("collect.log"), read_lines("requests.log"))

    def assert_wrote_nothing(self, res):
        self.assertEqual(res.writes, [], f"unexpected writes: {res.writes}")

    # ---- not configured: exit 0, no API calls, no data ----

    def test_no_team_configured_writes_nothing(self):
        res = self.run_collector(team=None)
        self.assertEqual(res.rc, 0, res.stderr)
        self.assertEqual(res.requests, [])
        self.assert_wrote_nothing(res)
        self.assertIn("No Datadog team found", res.stderr)

    def test_missing_secrets_writes_nothing(self):
        res = self.run_collector(secrets=False)
        self.assertEqual(res.rc, 0, res.stderr)
        self.assertEqual(res.requests, [])
        self.assert_wrote_nothing(res)
        self.assertIn("requires DATADOG_API_KEY and DATADOG_APP_KEY", res.stderr)

    # ---- the full chain ----

    def test_handle_resolves_team_and_collects_the_chain(self):
        res = self.run_collector()
        self.assertEqual(res.rc, 0, res.stderr)
        self.assertEqual(res.paths_requested(), [TEAMS, RULES, POLICY, SCHEDULE])
        urls = [r["url"] for r in res.requests]
        self.assertTrue(urls[0].startswith("https://api.datadoghq.com/api/v2/team?"))
        self.assertIn("filter%5Bkeyword%5D=payments&", urls[0])
        self.assertTrue(urls[1].endswith("/routing-rules?include=rules"))
        self.assertTrue(urls[2].endswith("?include=teams,steps,steps.targets"))
        self.assertTrue(urls[3].endswith("?include=teams,layers,layers.members,layers.members.user"))

        oncall = res.oncall
        # The keyword search also returned payments-eu; only the exact handle counts.
        self.assertEqual(oncall["service"], {"id": TEAM_ID, "name": "Payments"})
        self.assertEqual(
            oncall["escalation"],
            {"exists": True, "levels": 2, "policy_name": "Payments escalation", "id": POLICY_ID},
        )
        # Ada and Grace. Ada twice in one layer counts once, Linus is
        # deactivated, and Ken is only in the layer that ended in 2025.
        self.assertEqual(
            oncall["schedule"],
            {"exists": True, "participants": 2, "rotation": "weekly",
             "id": SCHEDULE_ID, "name": "Payments primary"},
        )
        self.assertEqual(
            oncall["summary"],
            {"has_oncall": True, "has_escalation": True, "min_participants": 2},
        )
        native = oncall["native"]["datadog"]
        self.assertEqual(native["team"]["attributes"]["handle"], "payments")
        self.assertEqual(native["routing_rules"], fixture("routing-rules.json"))
        self.assertEqual(native["escalation_policy"], fixture("escalation-policy.json"))
        self.assertEqual(native["schedule"], fixture("schedule.json"))
        self.assertEqual(oncall["source"], {"tool": "datadog", "integration": "api"})
        self.assertEqual(res.writes[-1]["path"], ".oncall.source")

    def test_api_and_application_keys_sent_as_headers(self):
        res = self.run_collector()
        self.assertEqual(res.rc, 0, res.stderr)
        for r in res.requests:
            self.assertIn("DD-API-KEY: test-api-key", r["headers"])
            self.assertIn("DD-APPLICATION-KEY: test-app-key", r["headers"])

    def test_team_id_skips_the_teams_api(self):
        res = self.run_collector(team=TEAM_ID)
        self.assertEqual(res.rc, 0, res.stderr)
        self.assertEqual(res.paths_requested(), [RULES, POLICY, SCHEDULE])
        # Name comes from the escalation policy's included team instead.
        self.assertEqual(res.oncall["service"], {"id": TEAM_ID, "name": "Payments"})
        self.assertNotIn("team", res.oncall["native"]["datadog"])

    def test_meta_annotation_wins_over_input(self):
        res = self.run_collector(
            team="payments-eu",
            LUNAR_COMPONENT_META=json.dumps({"datadog/team": TEAM_ID}),
        )
        self.assertEqual(res.rc, 0, res.stderr)
        self.assertEqual(res.paths_requested(), [RULES, POLICY, SCHEDULE])
        self.assertEqual(res.oncall["service"]["id"], TEAM_ID)

    def test_site_input_selects_the_api_host(self):
        res = self.run_collector(LUNAR_VAR_DATADOG_SITE="us5.datadoghq.com")
        self.assertEqual(res.rc, 0, res.stderr)
        for r in res.requests:
            self.assertTrue(r["url"].startswith("https://api.us5.datadoghq.com/"), r["url"])

    def test_handle_is_uri_encoded(self):
        routes = happy_routes()
        routes[TEAMS] = ok({"data": [], "meta": {"pagination": {"offset": 0, "total": 0}}})
        res = self.run_collector(routes=routes, team="pay&ments x")
        self.assertIn("filter%5Bkeyword%5D=pay%26ments%20x&", res.requests[0]["url"])

    def test_teams_search_pages_until_the_handle_matches(self):
        page0 = fixture("teams-search.json")
        filler = page0["data"][0]
        page0["data"] = []
        for i in range(100):
            team = copy.deepcopy(filler)
            team["id"] = f"00000000-0000-4000-8000-{i:012d}"
            team["attributes"]["handle"] = f"payments-{i}"
            page0["data"].append(team)
        routes = happy_routes()
        routes[TEAMS] = [ok(page0), ok("teams-search.json")]
        res = self.run_collector(routes=routes)
        self.assertEqual(res.rc, 0, res.stderr)
        teams_urls = [r["url"] for r in res.requests if "/api/v2/team?" in r["url"]]
        self.assertEqual(len(teams_urls), 2)
        self.assertIn("page%5Bnumber%5D=0", teams_urls[0])
        self.assertIn("page%5Bnumber%5D=1", teams_urls[1])
        self.assertEqual(res.oncall["service"]["id"], TEAM_ID)

    # ---- which escalation policy ----

    def test_policy_named_by_an_escalation_policy_action(self):
        rules = fixture("routing-rules.json")
        rule = rules["included"][1]
        rule["relationships"]["policy"]["data"] = None
        rule["attributes"]["actions"] = [
            {"type": "escalation_policy", "policy_id": POLICY_ID, "urgency": "high"}
        ]
        routes = happy_routes()
        routes[RULES] = ok(rules)
        res = self.run_collector(routes=routes)
        self.assertEqual(res.rc, 0, res.stderr)
        self.assertIn(POLICY, res.paths_requested())
        self.assertEqual(res.oncall["escalation"]["id"], POLICY_ID)

    def test_fallback_rule_wins_over_an_earlier_narrow_rule(self):
        # Rule 1 is urgency:low in business hours; rule 2 is the fallback.
        # Giving rule 1 a policy of its own must not change what is graded.
        rules = fixture("routing-rules.json")
        rules["included"][0]["relationships"]["policy"]["data"] = {"id": OTHER_POLICY_ID, "type": "policies"}
        routes = happy_routes()
        routes[RULES] = ok(rules)
        res = self.run_collector(routes=routes)
        self.assertEqual(res.rc, 0, res.stderr)
        self.assertEqual(res.oncall["escalation"]["id"], POLICY_ID)
        self.assertNotIn(OTHER_POLICY, res.paths_requested())

    def test_first_policy_before_the_fallback_when_the_fallback_pages_none(self):
        rules = fixture("routing-rules.json")
        rules["included"][0]["relationships"]["policy"]["data"] = {"id": POLICY_ID, "type": "policies"}
        rules["included"][1]["relationships"]["policy"]["data"] = None
        routes = happy_routes()
        routes[RULES] = ok(rules)
        res = self.run_collector(routes=routes)
        self.assertEqual(res.rc, 0, res.stderr)
        self.assertEqual(res.oncall["escalation"]["id"], POLICY_ID)

    def test_rules_after_the_fallback_never_match(self):
        # Evaluation order is data.relationships.rules: a Slack-only fallback
        # first leaves the policy-paging rule behind it unreachable.
        rules = fixture("routing-rules.json")
        rules["included"][0]["relationships"]["policy"]["data"] = {"id": POLICY_ID, "type": "policies"}
        rules["included"][1]["relationships"]["policy"]["data"] = None
        rules["data"]["relationships"]["rules"]["data"].reverse()
        routes = happy_routes()
        routes[RULES] = ok(rules)
        res = self.run_collector(routes=routes)
        self.assertEqual(res.rc, 0, res.stderr)
        self.assertEqual(res.oncall["escalation"]["exists"], False)
        self.assertNotIn(POLICY, res.paths_requested())

    def test_a_rule_with_a_query_is_not_the_fallback(self):
        rules = fixture("routing-rules.json")
        narrow = rules["included"][0]
        narrow["attributes"].update(query="priority:1", time_restriction=None)
        narrow["relationships"]["policy"]["data"] = {"id": OTHER_POLICY_ID, "type": "policies"}
        routes = happy_routes()
        routes[RULES] = ok(rules)
        res = self.run_collector(routes=routes)
        self.assertEqual(res.rc, 0, res.stderr)
        self.assertEqual(res.oncall["escalation"]["id"], POLICY_ID)

    def test_a_time_restricted_rule_is_not_the_fallback(self):
        rules = fixture("routing-rules.json")
        narrow = rules["included"][0]
        narrow["attributes"]["query"] = ""   # every page, but business hours only
        narrow["relationships"]["policy"]["data"] = {"id": OTHER_POLICY_ID, "type": "policies"}
        routes = happy_routes()
        routes[RULES] = ok(rules)
        res = self.run_collector(routes=routes)
        self.assertEqual(res.rc, 0, res.stderr)
        self.assertEqual(res.oncall["escalation"]["id"], POLICY_ID)

    def test_without_a_fallback_rules_follow_evaluation_order(self):
        rules = fixture("routing-rules.json")
        rules["included"][0]["relationships"]["policy"]["data"] = {"id": OTHER_POLICY_ID, "type": "policies"}
        rules["included"][1]["attributes"]["query"] = "priority:1"
        # Evaluation order is data.relationships.rules, not included order.
        rules["data"]["relationships"]["rules"]["data"].reverse()
        routes = happy_routes()
        routes[RULES] = ok(rules)
        res = self.run_collector(routes=routes)
        self.assertEqual(res.rc, 0, res.stderr)
        self.assertEqual(res.oncall["escalation"]["id"], POLICY_ID)
        self.assertNotIn(OTHER_POLICY, res.paths_requested())

    def test_no_rule_pages_a_policy(self):
        rules = fixture("routing-rules.json")
        rules["included"][1]["relationships"]["policy"]["data"] = None
        routes = happy_routes()
        routes[RULES] = ok(rules)
        res = self.run_collector(routes=routes)
        self.assertEqual(res.rc, 0, res.stderr)
        self.assertEqual(res.paths_requested(), [TEAMS, RULES])
        self.assertEqual(res.oncall["escalation"], {"exists": False, "levels": 0, "policy_name": ""})
        self.assertEqual(res.oncall["schedule"], {"exists": False, "participants": 0, "rotation": "unknown"})
        self.assertEqual(
            res.oncall["summary"],
            {"has_oncall": False, "has_escalation": False, "min_participants": 0},
        )
        self.assertIn("routing_rules", res.oncall["native"]["datadog"])
        self.assertIn("pages an escalation policy", res.stderr)

    def test_routing_rules_404_records_no_escalation(self):
        routes = happy_routes()
        routes[RULES] = NOT_FOUND
        res = self.run_collector(routes=routes)
        self.assertEqual(res.rc, 0, res.stderr)
        self.assertEqual(res.oncall["escalation"]["exists"], False)
        self.assertEqual(res.oncall["schedule"]["exists"], False)
        self.assertNotIn("routing_rules", res.oncall["native"]["datadog"])

    def test_policy_404_records_no_escalation(self):
        routes = happy_routes()
        routes[POLICY] = NOT_FOUND
        res = self.run_collector(routes=routes)
        self.assertEqual(res.rc, 0, res.stderr)
        self.assertEqual(res.oncall["escalation"], {"exists": False, "levels": 0, "policy_name": ""})
        self.assertEqual(res.oncall["schedule"]["exists"], False)
        self.assertNotIn(SCHEDULE, res.paths_requested())

    # ---- which schedule ----

    def test_schedule_from_a_configured_schedule_target(self):
        policy = fixture("escalation-policy.json")
        step1 = policy["included"][1]
        step1["relationships"]["targets"]["data"] = [
            {"id": "a5b6c7d8-e9f0-4a1b-8c2d-3e4f5a6b7c8d", "type": "users"}
        ]
        routes = happy_routes()
        routes[POLICY] = ok(policy)
        res = self.run_collector(routes=routes)
        self.assertEqual(res.rc, 0, res.stderr)
        # Step 2's "<id>_previous" target resolves through its included object.
        self.assertEqual(res.paths_requested()[-1], SCHEDULE)
        self.assertEqual(res.oncall["schedule"]["id"], SCHEDULE_ID)

    def test_policy_that_targets_no_schedule(self):
        policy = fixture("escalation-policy.json")
        for step in (policy["included"][1], policy["included"][2]):
            step["relationships"]["targets"]["data"] = [
                {"id": "a5b6c7d8-e9f0-4a1b-8c2d-3e4f5a6b7c8d", "type": "users"},
                {"id": TEAM_ID, "type": "teams"},
            ]
        routes = happy_routes()
        routes[POLICY] = ok(policy)
        res = self.run_collector(routes=routes)
        self.assertEqual(res.rc, 0, res.stderr)
        self.assertNotIn(SCHEDULE, res.paths_requested())
        self.assertEqual(res.oncall["escalation"]["exists"], True)
        self.assertEqual(res.oncall["schedule"], {"exists": False, "participants": 0, "rotation": "unknown"})
        self.assertNotIn("schedule", res.oncall["native"]["datadog"])

    def test_schedule_404_records_no_schedule(self):
        routes = happy_routes()
        routes[SCHEDULE] = NOT_FOUND
        res = self.run_collector(routes=routes)
        self.assertEqual(res.rc, 0, res.stderr)
        self.assertEqual(res.oncall["escalation"]["exists"], True)
        self.assertEqual(res.oncall["schedule"], {"exists": False, "participants": 0, "rotation": "unknown"})

    def test_participants_count_a_layer_without_end_date_and_active_users(self):
        schedule = fixture("schedule.json")
        del schedule["included"][1]["attributes"]["end_date"]          # Ken's layer is live again
        schedule["included"][9]["attributes"]["status"] = "active"      # Linus too
        routes = happy_routes()
        routes[SCHEDULE] = ok(schedule)
        res = self.run_collector(routes=routes)
        self.assertEqual(res.rc, 0, res.stderr)
        self.assertEqual(res.oncall["schedule"]["participants"], 4)

    def test_users_without_a_status_still_count(self):
        # Only a user Datadog reports as deactivated is left out.
        schedule = fixture("schedule.json")
        for item in schedule["included"]:
            if item["type"] == "users":
                del item["attributes"]["status"]
        routes = happy_routes()
        routes[SCHEDULE] = ok(schedule)
        res = self.run_collector(routes=routes)
        self.assertEqual(res.rc, 0, res.stderr)
        self.assertEqual(res.oncall["schedule"]["participants"], 3)

    def test_team_name_from_the_schedule_when_the_policy_is_another_teams(self):
        policy = fixture("escalation-policy.json")
        policy["included"][0].update(
            id="2b3c4d5e-6f70-4812-93a4-b5c6d7e8f901",
            attributes={"avatar": "", "description": "", "handle": "sre", "name": "SRE"},
        )
        policy["data"]["relationships"]["teams"]["data"][0]["id"] = "2b3c4d5e-6f70-4812-93a4-b5c6d7e8f901"
        routes = happy_routes()
        routes[POLICY] = ok(policy)
        res = self.run_collector(routes=routes, team=TEAM_ID)
        self.assertEqual(res.rc, 0, res.stderr)
        self.assertEqual(res.oncall["service"], {"id": TEAM_ID, "name": "Payments"})

    def test_participants_count_a_layer_that_ends_in_the_future(self):
        schedule = fixture("schedule.json")
        schedule["included"][1]["attributes"]["end_date"] = "2099-12-31T00:00:00Z"
        routes = happy_routes()
        routes[SCHEDULE] = ok(schedule)
        res = self.run_collector(routes=routes)
        self.assertEqual(res.oncall["schedule"]["participants"], 3)

    def test_rotation_length(self):
        for interval, expected in (
            ({"days": 1}, "daily"),
            ({"days": 0, "seconds": 43200}, "daily"),
            ({"days": 7}, "weekly"),
            ({"days": 14}, "custom"),
            ({}, "unknown"),
        ):
            with self.subTest(interval=interval):
                schedule = fixture("schedule.json")
                schedule["included"][0]["attributes"]["interval"] = interval
                routes = happy_routes()
                routes[SCHEDULE] = ok(schedule)
                res = self.run_collector(routes=routes)
                self.assertEqual(res.rc, 0, res.stderr)
                self.assertEqual(res.oncall["schedule"]["rotation"], expected)

    # ---- errors: exit non-zero, write nothing ----

    def test_forbidden_on_on_call_api_names_the_scope(self):
        routes = happy_routes()
        routes[RULES] = FORBIDDEN
        res = self.run_collector(routes=routes)
        self.assertNotEqual(res.rc, 0)
        self.assert_wrote_nothing(res)
        self.assertIn("HTTP 403", res.stderr)
        self.assertIn("on_call_read", res.stderr)

    def test_forbidden_on_teams_api_names_the_scope(self):
        routes = happy_routes()
        routes[TEAMS] = FORBIDDEN
        res = self.run_collector(routes=routes)
        self.assertNotEqual(res.rc, 0)
        self.assert_wrote_nothing(res)
        self.assertIn("teams_read", res.stderr)

    def test_unknown_handle_errors(self):
        res = self.run_collector(team="platform")
        self.assertNotEqual(res.rc, 0)
        self.assert_wrote_nothing(res)
        self.assertIn("No Datadog team has the handle 'platform'", res.stderr)

    def test_outage_late_in_the_chain_writes_nothing(self):
        for failure in ({"status": 503, "json": {"errors": ["Service Unavailable"]}},
                        {"status": 429, "json": {"errors": ["Rate limit exceeded"]}},
                        {"status": "NETFAIL"}):
            with self.subTest(failure=failure["status"]):
                routes = happy_routes()
                routes[SCHEDULE] = failure
                res = self.run_collector(routes=routes)
                self.assertNotEqual(res.rc, 0)
                # Earlier calls succeeded; nothing may be written from them.
                self.assert_wrote_nothing(res)

    def test_non_json_success_body_errors(self):
        routes = happy_routes()
        routes[POLICY] = {"status": 200, "raw": "<html>maintenance</html>"}
        res = self.run_collector(routes=routes)
        self.assertNotEqual(res.rc, 0)
        self.assert_wrote_nothing(res)
        self.assertIn("without a JSON object body", res.stderr)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Tests for the codeql collector's monorepo-fanout sub-collector.

The whole value of this collector is the *attribution* step — which repo-wide
finding ends up on which subcomponent — so that is what these lock in:

  * a finding under `services/api/...` reaches the api subcomponent and no other
  * a shared file a subcomponent explicitly claims in `paths:` reaches every
    subcomponent that claims it, matching how a change to that file already
    re-evaluates all of them
  * a finding that matches nothing stays on the root (no subcomponent gets it)
  * a subcomponent with zero matches is still written, with total 0 — the
    positive "scanned, clean" signal that turns its SAST policy from
    "No SAST scanning data found" into a pass
  * `.sast.findings` / `.sast.summary` are recomputed per subcomponent, since
    those (not `.sast.issues`) are what the SAST policies read

Plus the cross-component-write guardrails that are easy to regress:
`--component` must be reached with LUNAR_COLLECT_STDOUT unset, a subcomponent
that already has its own scan is never overwritten, and a re-fire that would
duplicate an identical payload is skipped.

The `lunar` stub serves `component get-json` and `sql connection-string`, a
`psql` stub stands in for the Hub's SQL API (applying the LIKE prefix itself so
discovery is exercised as a genuinely scoped read), and every `collect` call is
logged with its piped stdin to $CAPTURE — so a test can assert both *which*
component was written and *what* was written.
"""

import json
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest

HERE = os.path.dirname(__file__)
COLLECTOR = os.path.abspath(os.path.join(HERE, ".."))

ROOT = "github.com/acme/repo"
SHA = "9dd3cf6a1b2c3d4e5f60718293a4b5c6d7e8f900"

API = f"{ROOT}/services/api"
WEB = f"{ROOT}/services/web"
JOB = f"{ROOT}/services/job"

# One finding per interesting case: inside a subcomponent, inside a second
# subcomponent, in a shared file two subcomponents claim, and at the repo root
# where nothing claims it.
ISSUES = [
    {"severity": "high", "rule": "a/sqli", "file": "services/api/src/db.go", "line": 12, "message": "sqli"},
    {"severity": "critical", "rule": "a/rce", "file": "services/api/src/exec.go", "line": 3, "message": "rce"},
    {"severity": "medium", "rule": "w/xss", "file": "services/web/app/page.tsx", "line": 40, "message": "xss"},
    {"severity": "low", "rule": "gha/pin", "file": ".github/workflows/ci.yml", "line": 7, "message": "unpinned"},
    {"severity": "high", "rule": "root/leak", "file": "tools/generate.py", "line": 9, "message": "unclaimed"},
]

# api and web claim the shared workflow file explicitly; job does not.
CATALOG = {
    "components": {
        ROOT: {"branch": "main"},
        API: {"paths": ["services/api/*", ".github/workflows/ci.yml"]},
        WEB: {"paths": ["services/web/*", ".github/workflows/ci.yml"]},
        JOB: {},  # no explicit paths — relies on the implicit "services/job/*"
        "github.com/acme/other-repo": {},  # different repo, must never be touched
    }
}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sast-fanout-test-")
        self.bin = os.path.join(self.tmp, "bin")
        os.makedirs(self.bin)
        self.capture = os.path.join(self.tmp, "collect.log")
        self.sql_log = os.path.join(self.tmp, "sql.log")
        self.getjson_log = os.path.join(self.tmp, "getjson.log")
        self.fixtures = os.path.join(self.tmp, "fixtures")
        os.makedirs(self.fixtures)
        self.set_component_json(ROOT, {"sast": {"issues": ISSUES, "source": {"tool": "codeql", "version": "2.26.3"}}})
        for name in (API, WEB, JOB):
            self.set_component_json(name, {"lang": {"go": {}}})
        self._write_lunar_stub()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _fixture_path(self, component):
        return os.path.join(self.fixtures, component.replace("/", "_") + ".json")

    def set_component_json(self, component, doc):
        with open(self._fixture_path(component), "w") as f:
            json.dump(doc, f)

    def _write_lunar_stub(self):
        # Serves reads from $FIXTURES and appends one JSON record per collect
        # call to $CAPTURE. `collect` deliberately echoes nothing, mirroring a
        # real submit, so a stray stdout write would show up as a test failure
        # rather than being masked.
        with open(os.path.join(self.bin, "lunar"), "w") as f:
            f.write(
                textwrap.dedent(
                    """\
                    #!/usr/bin/env python3
                    import json, os, sys

                    argv = sys.argv[1:]
                    cap = os.environ["CAPTURE"]
                    fixtures = os.environ["FIXTURES"]

                    if argv[:2] == ["component", "get-json"]:
                        name = argv[2]
                        fail = os.environ.get("FAIL_GETJSON")
                        if fail and name == os.environ["ROOT_NAME"]:
                            n = int(open(fail).read() or "0")
                            if n != 0:
                                if n > 0:
                                    open(fail, "w").write(str(n - 1))
                                sys.stderr.write("transient\\n")
                                sys.exit(1)
                        if os.environ.get("GETJSON_LOG"):
                            with open(os.environ["GETJSON_LOG"], "a") as g:
                                g.write(name + "\\n")
                        path = os.path.join(fixtures, name.replace("/", "_") + ".json")
                        if not os.path.exists(path):
                            sys.stderr.write("component not found\\n")
                            sys.exit(1)
                        sys.stdout.write(open(path).read())
                        sys.exit(0)

                    if argv[:2] == ["sql", "connection-string"]:
                        if os.environ.get("FAIL_SQL"):
                            sys.exit(1)
                        sys.stdout.write("postgres://stub/lunar")
                        sys.exit(0)

                    if argv[0] == "collect":
                        rec = {"argv": argv, "stdin": None,
                               "collect_stdout_env": os.environ.get("LUNAR_COLLECT_STDOUT")}
                        if argv[-1] == "-":
                            rec["stdin"] = json.loads(sys.stdin.read())
                        with open(cap, "a") as c:
                            c.write(json.dumps(rec) + "\\n")
                        sys.exit(0)

                    sys.stderr.write("unexpected lunar invocation: %r\\n" % argv)
                    sys.exit(2)
                    """
                )
            )
        os.chmod(os.path.join(self.bin, "lunar"), 0o755)

        # Stands in for the Hub's SQL API. It applies the LIKE prefix itself,
        # exactly as Postgres would, so these tests exercise a genuinely SCOPED
        # read rather than "fetch the whole catalog and filter client-side" —
        # which is the thing that blew the gRPC message cap (ENG-1648).
        with open(os.path.join(self.bin, "psql"), "w") as f:
            f.write(
                textwrap.dedent(
                    """\
                    #!/usr/bin/env python3
                    import json, os, re, sys
                    if os.environ.get("FAIL_PSQL"):
                        sys.stderr.write("connection refused\\n")
                        sys.exit(2)
                    q = sys.argv[-1]
                    if os.environ.get("SQL_LOG"):
                        with open(os.environ["SQL_LOG"], "a") as lg:
                            lg.write(" ".join(q.split()) + "\\n")
                    m = re.search(r"LIKE '(.+?)%'", q)
                    prefix = m.group(1) if m else ""
                    cat = json.load(open(os.path.join(os.environ["FIXTURES"], "_catalog.json")))
                    rows = []
                    for name, v in sorted((cat.get("components") or {}).items()):
                        if prefix and not name.startswith(prefix):
                            continue
                        rows.append(name + "\\t" + json.dumps(v.get("paths") or []))
                    sys.stdout.write("\\n".join(rows) + ("\\n" if rows else ""))
                    """
                )
            )
        os.chmod(os.path.join(self.bin, "psql"), 0o755)

        with open(os.path.join(self.fixtures, "_catalog.json"), "w") as f:
            json.dump(CATALOG, f)

    def run_script(self, env_overrides=None, component=ROOT, sha=SHA):
        env = dict(os.environ)
        env["PATH"] = self.bin + os.pathsep + env["PATH"]
        env["CAPTURE"] = self.capture
        env["SQL_LOG"] = self.sql_log
        env["GETJSON_LOG"] = self.getjson_log
        env["FIXTURES"] = self.fixtures
        env["LUNAR_COMPONENT_ID"] = component
        env["ROOT_NAME"] = ROOT
        env["LUNAR_COMPONENT_GIT_SHA"] = sha
        # The runtime always sets this for a collector; the script must unset it
        # for the cross-component writes or they land back on the root.
        env["LUNAR_COLLECT_STDOUT"] = "1"
        env.pop("LUNAR_COMPONENT_PR", None)
        for k in ("LUNAR_VAR_SUBCOMPONENTS", "LUNAR_VAR_MAX_SUBCOMPONENTS"):
            env.pop(k, None)
        # Production default is 300s; the suite would take that long on the
        # persistent-failure case. The retry BEHAVIOUR is what's under test, not
        # the wall-clock budget.
        env["LUNAR_VAR_READ_RETRY_SECONDS"] = "20"
        if env_overrides:
            for k, v in env_overrides.items():
                if v is None:
                    env.pop(k, None)
                else:
                    env[k] = v
        proc = subprocess.run(
            ["bash", os.path.join(COLLECTOR, "monorepo-fanout.sh")],
            env=env, capture_output=True, text=True,
        )
        return proc

    def writes(self):
        """Cross-component writes, keyed by target component name."""
        out = {}
        for line in self._records():
            argv = line["argv"]
            if "--component" in argv:
                out[argv[argv.index("--component") + 1]] = line
        return out

    def _records(self):
        if not os.path.exists(self.capture):
            return []
        with open(self.capture) as f:
            return [json.loads(x) for x in f if x.strip()]

    def self_writes(self):
        return [r for r in self._records() if "--component" not in r["argv"]]


class TestAttribution(Base):
    def test_findings_route_to_the_owning_subcomponent(self):
        # Inspecting individual findings means opting the slice back in; the
        # default payload carries only the counts (see TestPayload).
        proc = self.run_script(env_overrides={"LUNAR_VAR_INCLUDE_ISSUES": "true"})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        writes = self.writes()
        self.assertEqual(set(writes), {API, WEB, JOB})

        api_files = [i["file"] for i in writes[API]["stdin"]["issues"]]
        self.assertCountEqual(
            api_files,
            ["services/api/src/db.go", "services/api/src/exec.go", ".github/workflows/ci.yml"],
        )
        # web must NOT pick up api's findings
        web_files = [i["file"] for i in writes[WEB]["stdin"]["issues"]]
        self.assertCountEqual(web_files, ["services/web/app/page.tsx", ".github/workflows/ci.yml"])

    def test_shared_claimed_file_reaches_every_claimant_and_no_one_else(self):
        self.run_script(env_overrides={"LUNAR_VAR_INCLUDE_ISSUES": "true"})
        writes = self.writes()
        for name in (API, WEB):
            files = [i["file"] for i in writes[name]["stdin"]["issues"]]
            self.assertIn(".github/workflows/ci.yml", files)
        # job does not claim the workflow file, so it must not receive it
        job_files = [i["file"] for i in writes[JOB]["stdin"]["issues"]]
        self.assertNotIn(".github/workflows/ci.yml", job_files)

    def test_unclaimed_finding_reaches_no_subcomponent(self):
        self.run_script(env_overrides={"LUNAR_VAR_INCLUDE_ISSUES": "true"})
        for name, rec in self.writes().items():
            files = [i["file"] for i in rec["stdin"]["issues"]]
            self.assertNotIn("tools/generate.py", files, f"{name} should not own a repo-root file")

    def test_implicit_subdir_pattern_applies_without_explicit_paths(self):
        # job declares no `paths:`; the implicit "services/job/*" must still be
        # derived from its name, otherwise it would match nothing (or, worse,
        # inherit "empty matches everything" and take the whole repo).
        self.set_component_json(ROOT, {"sast": {"issues": [
            {"severity": "low", "rule": "j/x", "file": "services/job/main.rs", "line": 1, "message": "x"},
        ]}})
        self.run_script(env_overrides={"LUNAR_VAR_INCLUDE_ISSUES": "true"})
        writes = self.writes()
        self.assertEqual([i["file"] for i in writes[JOB]["stdin"]["issues"]], ["services/job/main.rs"])
        self.assertEqual(writes[API]["stdin"]["findings"]["total"], 0)

    def test_other_repos_are_never_touched(self):
        self.run_script()
        self.assertNotIn("github.com/acme/other-repo", self.writes())

    def test_root_is_never_written_to_as_a_target(self):
        self.run_script()
        self.assertNotIn(ROOT, self.writes())


class TestPayload(Base):
    def test_counts_and_summary_are_recomputed_per_subcomponent(self):
        # This is the attribution proof now that .issues is opt-in: the COUNTS
        # themselves differ per subcomponent, derived from path matching.
        self.run_script()
        api = self.writes()[API]["stdin"]
        # api owns: 1 high, 1 critical, 1 low (the shared workflow finding)
        self.assertEqual(api["findings"], {"critical": 1, "high": 1, "medium": 0, "low": 1, "total": 3})
        self.assertEqual(api["summary"], {"has_critical": True, "has_high": True})

        web = self.writes()[WEB]["stdin"]
        self.assertEqual(web["findings"], {"critical": 0, "high": 0, "medium": 1, "low": 1, "total": 2})
        self.assertEqual(web["summary"], {"has_critical": False, "has_high": False})

    def test_zero_match_subcomponent_is_still_written_with_total_zero(self):
        # "scanned and clean" is a real result: it is what turns the SAST policy
        # from "No SAST scanning data found" into a pass. Dropping the write
        # would leave exactly the gap this collector exists to close.
        self.run_script(env_overrides={"LUNAR_VAR_INCLUDE_ISSUES": "true"})
        job = self.writes()[JOB]["stdin"]
        self.assertEqual(job["issues"], [])
        self.assertEqual(job["findings"]["total"], 0)
        self.assertEqual(job["summary"], {"has_critical": False, "has_high": False})

    def test_source_is_carried_over_and_stamped_as_fanout(self):
        self.run_script()
        src = self.writes()[API]["stdin"]["source"]
        self.assertEqual(src["tool"], "codeql")
        self.assertEqual(src["version"], "2.26.3")
        self.assertEqual(src["integration"], "monorepo-fanout")

    def test_native_is_never_written_to_a_subcomponent(self):
        # The raw SARIF under .sast.native describes the WHOLE repository, so it
        # belongs to the root and nowhere else. Provenance lives under
        # .sast.source.fanout instead of inventing a .native entry on the target.
        self.run_script()

        def find_native(node, path="sast"):
            """Anywhere in the payload, not just the top level — the point is
            that no .native ever reaches a subcomponent, however it is nested."""
            hits = []
            if isinstance(node, dict):
                for k, v in node.items():
                    if k == "native":
                        hits.append(f"{path}.{k}")
                    hits += find_native(v, f"{path}.{k}")
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    hits += find_native(v, f"{path}[{i}]")
            return hits

        for name, rec in self.writes().items():
            hits = find_native(rec["stdin"])
            self.assertEqual(hits, [], f"{name} must not receive .native; found {hits}")

    def test_issues_are_omitted_by_default(self):
        # policies/sast reads .sast.summary.has_<sev> then .sast.findings.<sev>;
        # max_total reads .sast.findings.total. None read .sast.issues, so the
        # per-finding array is not shipped to every subcomponent by default.
        self.run_script()
        for name, rec in self.writes().items():
            self.assertNotIn("issues", rec["stdin"], f"{name} got .sast.issues without opt-in")
            self.assertIn("findings", rec["stdin"])
            self.assertIn("summary", rec["stdin"])

    def test_include_issues_opts_the_slice_back_in(self):
        self.run_script(env_overrides={"LUNAR_VAR_INCLUDE_ISSUES": "true"})
        api = self.writes()[API]["stdin"]
        self.assertCountEqual(
            [i["file"] for i in api["issues"]],
            ["services/api/src/db.go", "services/api/src/exec.go", ".github/workflows/ci.yml"],
        )
        # and the attributed slice is still per-subcomponent, not the whole set
        self.assertNotIn("tools/generate.py", [i["file"] for i in api["issues"]])

    def test_provenance_records_root_sha_and_patterns(self):
        self.run_script()
        native = self.writes()[API]["stdin"]["source"]["fanout"]
        self.assertEqual(native["root_component"], ROOT)
        self.assertEqual(native["root_git_sha"], SHA)
        self.assertEqual(native["matched"], 3)
        self.assertIn("services/api/*", native["paths"])
        self.assertTrue(native["fingerprint"])

    def test_breadcrumb_written_to_the_root(self):
        self.run_script()
        selfw = self.self_writes()
        self.assertEqual(len(selfw), 1)
        self.assertIn(".sast.native.monorepo_fanout", selfw[0]["argv"])
        targets = selfw[0]["stdin"]["targets"]
        self.assertEqual({t["component"] for t in targets}, {API, WEB, JOB})
        self.assertTrue(all(t["status"] == "written" for t in targets))

    def test_writes_are_pinned_to_the_settled_sha(self):
        self.run_script()
        argv = self.writes()[API]["argv"]
        self.assertEqual(argv[argv.index("--sha") + 1], SHA)
        self.assertNotIn("--pr", argv)

    def test_pr_dimension_is_threaded_through(self):
        self.run_script(env_overrides={"LUNAR_COMPONENT_PR": "43"})
        argv = self.writes()[API]["argv"]
        self.assertEqual(argv[argv.index("--pr") + 1], "43")


class TestDiscovery(Base):
    """Discovery must be a SCOPED read. Pulling the whole catalog to find a
    handful of names is what blew the gRPC message cap on a real hub
    (ResourceExhausted, 6264541 vs 4194304 — ENG-1648), and it wastes bandwidth
    proportional to the entire fleet rather than to this one repo."""

    def _queries(self):
        if not os.path.exists(self.sql_log):
            return []
        with open(self.sql_log) as f:
            return [l.strip() for l in f if l.strip()]

    def test_discovery_pushes_the_prefix_filter_to_the_server(self):
        self.run_script()
        qs = self._queries()
        self.assertTrue(qs, "no SQL query was issued — discovery did not use the SQL API")
        self.assertTrue(
            any(f"LIKE '{ROOT}/%'" in q for q in qs),
            f"prefix filter not pushed down to Postgres; queries were: {qs}",
        )

    def test_discovery_never_calls_the_whole_catalog_rpc(self):
        # `lunar cataloger get-json` returns the entire catalog in one gRPC
        # message. The stub exits 2 on any unexpected invocation, so reaching
        # for it would surface as a non-zero run.
        proc = self.run_script()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("cataloger", proc.stderr)

    def test_sql_connection_string_failure_fails_loudly(self):
        proc = self.run_script(env_overrides={"FAIL_SQL": "1"})
        self.assertEqual(proc.returncode, 1)
        self.assertIn("could not enumerate subcomponents", proc.stderr)
        self.assertEqual(self.writes(), {})

    def test_psql_failure_fails_loudly(self):
        proc = self.run_script(env_overrides={"FAIL_PSQL": "1"})
        self.assertEqual(proc.returncode, 1)
        self.assertIn("could not enumerate subcomponents", proc.stderr)
        self.assertEqual(self.writes(), {})

    def test_non_monorepo_component_exits_without_reading_its_own_json(self):
        """Targeting a component with no subcomponents must be CHEAP. Discovery
        runs first precisely so this costs one scoped query and an exit, not a
        get-json that can retry for READ_BUDGET_SECS before being thrown away."""
        proc = self.run_script(component="github.com/acme/other-repo")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.writes(), {})
        self.assertIn("no subcomponents", proc.stderr)
        self.assertNotIn("root carries", proc.stderr)
        # one scoped query, and no Component JSON read at all
        self.assertEqual(len(self._queries()), 1)
        self.assertFalse(os.path.exists(self.getjson_log),
                         "no Component JSON read should happen before discovery rules the component out")


class TestReadRetries(Base):
    """The wave is fire-once per (component, sha, pr), forever — a transient hub
    read must not be mistaken for "nothing to fan out", because no re-run can
    ever recover that commit. Observed live on cronos: `get-json` returned
    NotFound for a few seconds around a manifest publish (which re-keys the
    component's serving row), the collector exited 0, and the fan-out for that
    commit was permanently lost."""

    def _countdown(self, n):
        path = os.path.join(self.tmp, "fail_count")
        with open(path, "w") as f:
            f.write(str(n))
        return path

    def test_transient_read_failure_is_retried(self):
        proc = self.run_script(env_overrides={"FAIL_GETJSON": self._countdown(2)})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(set(self.writes()), {API, WEB, JOB})

    def test_persistent_read_failure_fails_loudly(self):
        # -1 = fail forever. Exiting 0 here would look identical to "no data".
        proc = self.run_script(env_overrides={"FAIL_GETJSON": self._countdown(-1)})
        self.assertEqual(proc.returncode, 1)
        self.assertIn("fire-once", proc.stderr)
        self.assertIn("not yet materialized", proc.stderr)
        self.assertEqual(self.writes(), {})
        self.assertEqual(self.self_writes(), [])


class TestGuardrails(Base):
    def test_collect_stdout_is_unset_for_cross_component_writes(self):
        # With LUNAR_COLLECT_STDOUT set, `lunar collect` prints instead of
        # submitting and --component is silently ignored — every subcomponent's
        # slice would land back on the root.
        self.run_script()
        for name, rec in self.writes().items():
            self.assertIsNone(rec["collect_stdout_env"], f"{name} written with stdout capture still on")

    def test_subcomponent_with_its_own_scan_is_not_overwritten(self):
        self.set_component_json(API, {"lang": {"go": {}}, "sast": {"source": {"tool": "semgrep", "integration": "code"}}})
        self.run_script()
        writes = self.writes()
        self.assertNotIn(API, writes)
        self.assertIn(WEB, writes)
        skipped = [t for t in self.self_writes()[0]["stdin"]["targets"] if t["component"] == API]
        self.assertEqual(skipped[0]["status"], "skipped")
        self.assertTrue(skipped[0]["reason"].startswith("own-scan:"))

    def test_identical_refire_is_skipped(self):
        # CollectExternal appends a record per call and the merge concatenates
        # arrays across records, so an unguarded second run would duplicate
        # every issue on the target.
        first = self.run_script()
        self.assertEqual(first.returncode, 0, first.stderr)
        fanned = self.writes()[API]["stdin"]
        # Simulate the write having landed, then re-run.
        self.set_component_json(API, {"lang": {"go": {}}, "sast": fanned})
        os.remove(self.capture)
        self.run_script()
        self.assertNotIn(API, self.writes())
        self.assertIn(WEB, self.writes())

    def test_changed_findings_do_rewrite(self):
        # The skip-guard must key on the payload, not merely on "a fan-out has
        # happened here" — a second language job landing late genuinely changes
        # the finding set at the same sha, and that has to reach the target.
        self.run_script()
        landed = self.writes()[API]["stdin"]
        self.set_component_json(API, {"lang": {"go": {}}, "sast": landed})

        extra = dict(ISSUES[0], rule="a/late", file="services/api/src/late.go")
        self.set_component_json(
            ROOT, {"sast": {"issues": ISSUES + [extra], "source": {"tool": "codeql", "version": "2.26.3"}}}
        )
        os.remove(self.capture)
        self.run_script()
        self.assertIn(API, self.writes(), "a changed finding set must not be treated as unchanged")
        self.assertEqual(self.writes()[API]["stdin"]["findings"]["total"], 4)

    def test_target_with_no_blob_at_this_sha_is_still_written(self):
        # A subcomponent is only evaluated at a commit whose changed paths
        # intersect its own, so a monorepo commit that touched nothing it owns
        # leaves it with no Component JSON to read back. That must not stop the
        # fan-out: the guard read is best-effort, and the write still has to
        # land (the sha is ingested for the repo either way).
        os.remove(self._fixture_path(JOB))
        proc = self.run_script()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(JOB, self.writes())
        self.assertEqual(self.writes()[JOB]["stdin"]["findings"]["total"], 0)

    def test_empty_self_reference_writes_nothing(self):
        proc = self.run_script(env_overrides={"LUNAR_COMPONENT_ID": ""})
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(self.writes(), {})
        self.assertEqual(self.self_writes(), [])

    def test_missing_sha_writes_nothing(self):
        proc = self.run_script(sha="")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(self.writes(), {})

    def test_absent_issues_writes_nothing(self):
        # .sast present but no issues key: the scanner ran commands but produced
        # no parsed findings, so there is nothing to distribute.
        self.set_component_json(ROOT, {"sast": {"native": {"codeql": {"cicd": {"cmds": []}}}}})
        proc = self.run_script()
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(self.writes(), {})

    def test_empty_issues_list_still_fans_out(self):
        # An empty list is "scanned, clean" and must reach the subcomponents.
        self.set_component_json(ROOT, {"sast": {"issues": [], "source": {"tool": "codeql"}}})
        self.run_script()
        writes = self.writes()
        self.assertEqual(set(writes), {API, WEB, JOB})
        self.assertEqual(writes[API]["stdin"]["findings"]["total"], 0)

    def test_max_subcomponents_truncates_loudly(self):
        proc = self.run_script(env_overrides={"LUNAR_VAR_MAX_SUBCOMPONENTS": "2"})
        self.assertEqual(len(self.writes()), 2)
        self.assertIn("SKIPPING the rest", proc.stderr)


if __name__ == "__main__":
    unittest.main()

"""Discovery tests for the terraform collector.

`main.sh` is bash. These tests build a repo on disk, stub `lunar` and
`hcl2json` on PATH, run the real script as a subprocess, and assert on which
files it collected — so the glob and the OpenTofu precedence rule are covered
by something other than reading them.
"""

import json
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN_SH = os.path.join(HERE, "..", "main.sh")


class DiscoveryTest(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp()
        self.bin = tempfile.mkdtemp()

        # `lunar collect -j <path> -` → append the payload to a capture file.
        self.capture = os.path.join(self.bin, "captured.jsonl")
        with open(os.path.join(self.bin, "lunar"), "w") as fh:
            fh.write(textwrap.dedent(f"""\
                #!/bin/bash
                [ "$1" = "collect" ] || exit 0
                shift; [ "$1" = "-j" ] && shift
                path="$1"
                payload=$(cat)
                printf '%s\\t%s\\n' "$path" "$(echo "$payload" | tr -d '\\n')" \\
                    >> {self.capture}
                """))

        # hcl2json must fail on JSON input, exactly as the real binary does —
        # otherwise the test would not notice the .json branch disappearing.
        with open(os.path.join(self.bin, "hcl2json"), "w") as fh:
            fh.write(textwrap.dedent("""\
                #!/bin/bash
                case "$1" in
                  *.json) echo "Failed to convert file: parse config" >&2; exit 1 ;;
                esac
                printf '{"resource":{"aws_s3_bucket":{"stub":[{}]}}}\\n'
                """))

        for f in ("lunar", "hcl2json"):
            os.chmod(os.path.join(self.bin, f), 0o755)

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)
        shutil.rmtree(self.bin, ignore_errors=True)

    def write(self, rel, body="resource \"aws_s3_bucket\" \"x\" { bucket = \"x\" }\n"):
        path = os.path.join(self.repo, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(body)

    def run_collector(self):
        env = dict(os.environ, PATH=self.bin + os.pathsep + os.environ["PATH"])
        proc = subprocess.run(["bash", MAIN_SH], cwd=self.repo, env=env,
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        if not os.path.exists(self.capture):
            return {}
        out = {}
        with open(self.capture) as fh:
            for line in fh:
                path, payload = line.rstrip("\n").split("\t", 1)
                out[path] = json.loads(payload)
        return out

    def collected_paths(self):
        written = self.run_collector()
        return sorted(f["path"] for f in written.get(".iac.files", []))

    def test_finds_all_four_extensions(self):
        self.write("a.tf")
        self.write("b.tofu")
        self.write("c.tf.json", '{"resource":{}}\n')
        self.write("d.tofu.json", '{"resource":{}}\n')
        self.assertEqual(self.collected_paths(),
                         ["a.tf", "b.tofu", "c.tf.json", "d.tofu.json"])

    def test_tofu_shadows_tf_of_the_same_base(self):
        # OpenTofu applies main.tofu and ignores main.tf — collecting the .tf
        # would evaluate configuration that is never applied.
        self.write("main.tf")
        self.write("main.tofu")
        self.assertEqual(self.collected_paths(), ["main.tofu"])

    def test_tofu_json_shadows_tf_json_of_the_same_base(self):
        self.write("conf.tf.json", '{"resource":{}}\n')
        self.write("conf.tofu.json", '{"resource":{}}\n')
        self.assertEqual(self.collected_paths(), ["conf.tofu.json"])

    def test_shadowing_is_per_directory_and_per_base(self):
        # main.tofu must not shadow another directory's main.tf, nor other.tf.
        self.write("main.tf")
        self.write("main.tofu")
        self.write("other.tf")
        self.write("mod/main.tf")
        self.assertEqual(self.collected_paths(),
                         ["main.tofu", "mod/main.tf", "other.tf"])

    def test_json_variants_are_valid_not_parse_errors(self):
        # hcl2json rejects JSON, so these must take the jq path.
        self.write("c.tf.json", '{"resource":{"aws_s3_bucket":{"j":{"bucket":"b"}}}}\n')
        written = self.run_collector()
        files = {f["path"]: f for f in written[".iac.files"]}
        self.assertTrue(files["c.tf.json"]["valid"], files["c.tf.json"])
        native = {f["path"]: f for f in written[".iac.native.terraform.files"]}
        self.assertIn("aws_s3_bucket", native["c.tf.json"]["hcl"]["resource"])

    def test_pure_terraform_repo_is_unchanged(self):
        self.write("main.tf")
        self.write("variables.tf")
        self.write("mod/iam.tf")
        self.assertEqual(self.collected_paths(),
                         ["main.tf", "mod/iam.tf", "variables.tf"])

    def test_no_configuration_writes_nothing(self):
        self.write("README.md", "# not terraform\n")
        self.assertEqual(self.run_collector(), {})


if __name__ == "__main__":
    unittest.main()

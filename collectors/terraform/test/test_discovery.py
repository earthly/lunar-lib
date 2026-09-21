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

        # hcl2json fails on JSON input, exactly as the real binary does. Nothing
        # should feed it a .json file today; if discovery ever widens to the
        # JSON variants without a parse path, these tests go red rather than
        # silently recording every such file as invalid.
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

    def test_finds_tf_and_tofu(self):
        self.write("a.tf")
        self.write("b.tofu")
        self.assertEqual(self.collected_paths(), ["a.tf", "b.tofu"])

    def test_json_variants_are_deliberately_not_collected(self):
        # They parse, but .iac.modules assumes hcl2json's list-shaped blocks
        # and JSON syntax gives objects — ENG-1860. Collecting them would make
        # is_lb_public throw and has_prevent_destroy silently wrong.
        self.write("a.tf")
        self.write("c.tf.json", '{"resource":{}}\n')
        self.write("d.tofu.json", '{"resource":{}}\n')
        self.assertEqual(self.collected_paths(), ["a.tf"])

    def test_tofu_shadows_tf_of_the_same_base(self):
        # OpenTofu applies main.tofu and ignores main.tf — collecting the .tf
        # would evaluate configuration that is never applied.
        self.write("main.tf")
        self.write("main.tofu")
        self.assertEqual(self.collected_paths(), ["main.tofu"])

    def test_shadowing_is_per_directory_and_per_base(self):
        # main.tofu must not shadow another directory's main.tf, nor other.tf.
        self.write("main.tf")
        self.write("main.tofu")
        self.write("other.tf")
        self.write("mod/main.tf")
        self.assertEqual(self.collected_paths(),
                         ["main.tofu", "mod/main.tf", "other.tf"])

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

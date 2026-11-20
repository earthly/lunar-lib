import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
PARSER = HERE / 'parse_pyproject.py'
COLLECTOR = HERE / 'dependencies.sh'


def project_text(dependencies):
    return '[project]\nname = "fixture"\nversion = "0.1"\ndependencies = ' + json.dumps(dependencies) + '\n'


class DependencyParsingTests(unittest.TestCase):
    def parse(self, dependencies):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'pyproject.toml').write_text(project_text(dependencies))
            return subprocess.check_output([sys.executable, str(PARSER)], cwd=directory, text=True).splitlines()

    def test_whitespace_before_extras_preserves_dependency(self):
        for space in [' ', '  ', '\t']:
            with self.subTest(space=space):
                self.assertEqual(self.parse([f'requests{space}[security]>=2.0']), ['requests==2.0'])

    def test_extras_with_markers_and_ranges(self):
        self.assertEqual(self.parse(['httpx [http2] >=0.28,<1; python_version >= "3.10"']), ['httpx==0.28'])

    def test_extras_with_direct_reference(self):
        self.assertEqual(self.parse(['sample [feature] @ https://example.invalid/sample.whl']), ['sample'])

    def test_unversioned_extras(self):
        self.assertEqual(self.parse(['requests [security]']), ['requests'])

    def test_compact_and_plain_requirements_unchanged(self):
        self.assertEqual(self.parse(['requests[security]>=2.0', 'httpx>=0.28', 'plain', 'demo; python_version < "4"']), ['requests==2.0', 'httpx==0.28', 'plain', 'demo'])

    def test_poetry_fallback_is_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'pyproject.toml').write_text('[tool.poetry.dependencies]\npython = "^3.10"\nrequests = "^2.0"\nhttpx = {version = "~0.28"}\n')
            output = subprocess.check_output([sys.executable, str(PARSER)], cwd=directory, text=True)
            self.assertEqual(output.splitlines(), ['requests==2.0', 'httpx==0.28'])

    def test_actual_collector_does_not_replace_manifest_with_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'pyproject.toml').write_text(project_text(['requests [security]>=2.0']))
            (root / 'requirements.txt').write_text('unrelated-fallback==9\n')
            bindir = root / 'bin'
            bindir.mkdir()
            sink = bindir / 'lunar'
            sink.write_text('#!/bin/sh\n[ "$1" = collect ] || exit 8\n[ "$2" = -j ] || exit 9\n[ "$3" = .lang.python.dependencies ] || exit 10\ncat\n')
            sink.chmod(0o755)
            environment = dict(os.environ, PATH=str(bindir) + os.pathsep + os.environ['PATH'])
            result = subprocess.run(['bash', str(COLLECTOR)], cwd=root, env=environment, text=True, capture_output=True, check=True)
            collected = json.loads(result.stdout)
            self.assertEqual(collected['direct'], [{'path': 'requests', 'version': '2.0', 'indirect': False}])
            self.assertEqual(collected['source'], {'tool': 'pip', 'integration': 'code'})


if __name__ == '__main__':
    unittest.main()

"""Unit tests for version_minimum.py, the module every language version check copies.

scripts/validate_shared_modules.py keeps the copies identical, so testing this
one covers them all. Each policy's own tests cover its release lines.
"""

import itertools
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "checks"))

from version_minimum import Runtime, compare_versions, parse_minimum  # noqa: E402

MINOR = Runtime("Python", line_length=2, forms="3.12, 3.12.8 or 3.13.0rc1")
MAJOR = Runtime("Node.js", line_length=1, forms="20 or 20.15.1")
BANDS = Runtime(".NET SDK", line_length=3, forms="8.0 or 8.0.404", feature_bands=True)


def v(text, runtime=MINOR):
    return runtime.parse(text)


class ParseVersionTest(unittest.TestCase):
    def test_forms(self):
        for text, numbers, pre in [
            ("20", (20,), None),
            ("v20.11.0", (20, 11, 0), None),
            (" 3.12.8 ", (3, 12, 8), None),
            ("3.13.0rc1", (3, 13, 0), "rc1"),
            ("3.14.0a1", (3, 14, 0), "a1"),
            ("1.23rc1", (1, 23), "rc1"),
            ("2.0.0-Beta1", (2, 0, 0), "Beta1"),
            ("24.0.0-rc.1", (24, 0, 0), "rc.1"),
            ("9.0.100-preview.7.24407.12", (9, 0, 100), "preview.7.24407.12"),
            ("3.3.1-RC1-bin-20230203-a0d9c64-NIGHTLY", (3, 3, 1), "RC1-bin-20230203-a0d9c64-NIGHTLY"),
            ("8.4.0RC1", (8, 4, 0), "RC1"),
            ("8.1.2-1ubuntu2.19", (8, 1, 2), None),  # distribution package revision
            ("8.3.12-1+ubuntu22.04.1+deb.sury.org+1", (8, 3, 12), None),
            ("3.12.0+", (3, 12, 0), None),  # local build
            (21, (21,), None),
        ]:
            with self.subTest(text=text):
                parsed = v(text)
                self.assertEqual((parsed.numbers, parsed.pre), (numbers, pre))
                self.assertEqual(parsed.text, str(text).strip())

    def test_rejects(self):
        for value in ["", "latest", "x", "^8.1", ">=3.9", "3..12", "3.x.1", "go1.22", "jruby-9.4.8.0", "devel", "1.2.3.", "-1", "+"]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError) as e:
                    v(value)
                self.assertIn("is not a recognized version format; expected a form like 3.12, 3.12.8 or 3.13.0rc1", str(e.exception))
        for value, kind in [(None, "null"), (True, "boolean"), ([3], "array"), ({}, "object")]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError) as e:
                    v(value)
                self.assertEqual(str(e.exception), f'must be a string such as "3.12", got {kind}')

    def test_trailing_wildcard_names_its_line(self):
        for text, numbers in [("20.x", (20,)), ("3.12.X", (3, 12)), ("8.0.x", (8, 0)), ("1.9.+", (1, 9)), ("1.9+", (1, 9)), ("1.9.*", (1, 9))]:
            with self.subTest(text=text):
                self.assertEqual(v(text), (text, numbers, None))

    def test_normalize(self):
        php = Runtime("PHP", 2, "8.3", normalize=lambda t: t.lstrip("^"))
        self.assertEqual(php.parse("^8.1"), ("^8.1", (8, 1), None))


class CompareVersionsTest(unittest.TestCase):
    def test_order(self):
        ordered = [
            "3.11.9", "3.12", "3.12.0+", "3.12.1", "3.12.8", "3.13.0a1", "3.13.0b2", "3.13.0rc1",
            "3.13.0rc2", "3.13.0rc10", "3.13.0", "3.13.1", "3.14",
        ]
        for a, b in itertools.combinations(ordered, 2):
            with self.subTest(a=a, b=b):
                if (a, b) in [("3.12", "3.12.0+")]:
                    self.assertEqual(compare_versions(v(a), v(b)), 0)
                else:
                    self.assertLess(compare_versions(v(a), v(b)), 0)
                    self.assertGreater(compare_versions(v(b), v(a)), 0)

    def test_equal(self):
        for a, b in [("3.12", "3.12.0"), ("3", "3.0.0.0"), ("v20.1.0", "20.1"), ("8.4.0RC1", "8.4.0rc1"), ("8.1.2-1ubuntu2.19", "8.1.2")]:
            with self.subTest(a=a, b=b):
                self.assertEqual(compare_versions(v(a), v(b)), 0)


class ParseMinimumTest(unittest.TestCase):
    def test_one_version(self):
        for value, text in [("3.12.8", "3.12.8"), (" 3.9 ", "3.9"), ("[3.9]", "3.9"), (3, "3")]:
            with self.subTest(value=value):
                minimum = parse_minimum(value, MINOR)
                self.assertEqual((minimum.text, minimum.describe()), (text, f"minimum {text}"))

    def test_list_forms(self):
        for value in [
            "3.12.8, 3.13.1, 3.14.0",
            "3.12.8 3.13.1 3.14.0",
            "3.14.0,3.12.8,3.13.1",  # any order
            "[3.12.8, 3.13.1, 3.14.0]",
            '["3.12.8", "3.13.1", "3.14.0"]',
            "3.12.8  # security fix\n3.13.1\n# 3.11 is out\n3.14.0\n",
        ]:
            with self.subTest(value=value):
                minimum = parse_minimum(value, MINOR)
                self.assertEqual(minimum.text, "3.12.8, 3.13.1, 3.14.0")
                self.assertEqual(minimum.describe(), "the minimum for its release line (3.12.8, 3.13.1, 3.14.0)")

    def test_invalid(self):
        for runtime, value, error in [
            (MINOR, "", '"" is not a recognized version format'),
            (MINOR, "[]", '"[]" is not a recognized version format'),
            (MINOR, "# none yet", '"# none yet" is not a recognized version format'),
            (MINOR, "3.12.8, latest", 'entry "latest" is not a recognized version format'),
            (MINOR, "3.12.8, 3.12.9", "lists Python 3.12 twice: 3.12.8 and 3.12.9"),
            (MINOR, "3, 3.12.8", "lists Python 3 twice: 3 and 3.12.8"),
            (MINOR, "3.12.8, 3", "lists Python 3 twice: 3.12.8 and 3"),
            (MAJOR, "20.15.1, 20.18.2", "lists Node.js 20 twice: 20.15.1 and 20.18.2"),
            (BANDS, "8.0.404, 8.0.410", "lists .NET SDK 8.0.4xx twice: 8.0.404 and 8.0.410"),
            (BANDS, "8.0, 8.0.404", "lists .NET SDK 8.0 twice: 8.0 and 8.0.404"),
        ]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError) as e:
                    parse_minimum(value, runtime)
                self.assertIn(error, str(e.exception))


class MatchTest(unittest.TestCase):
    def problems(self, value, versions, runtime=MINOR):
        minimum = parse_minimum(value, runtime)
        return {text: minimum.problem(runtime.parse(text)) for text in versions}

    def test_one_minimum_per_line(self):
        self.assertEqual(
            self.problems("3.10.16, 3.12.8, 3.13.1", ["3.9.21", "3.10.16", "3.11.11", "3.12.7", "3.12.8", "3.13.0", "3.14.0"]),
            {
                "3.9.21": "Python 3.9.21 is below minimum 3.10.16",  # older than every listed line
                "3.10.16": None,
                "3.11.11": "Python 3.11.11 is on release line 3.11, which has no listed minimum",
                "3.12.7": "Python 3.12.7 is below minimum 3.12.8",
                "3.12.8": None,
                "3.13.0": "Python 3.13.0 is below minimum 3.13.1",
                "3.14.0": None,  # newer than every listed line
            },
        )

    def test_entry_without_a_patch_covers_its_whole_line_or_major(self):
        self.assertEqual(
            self.problems("3, 4.2.1", ["2.7.18", "3.0.0", "3.13.1", "4.1.0", "4.2.0", "4.2.1", "5.0"]),
            {
                "2.7.18": "Python 2.7.18 is below minimum 3",
                "3.0.0": None,
                "3.13.1": None,
                "4.1.0": "Python 4.1.0 is on release line 4.1, which has no listed minimum",
                "4.2.0": "Python 4.2.0 is below minimum 4.2.1",
                "4.2.1": None,
                "5.0": None,
            },
        )

    def test_feature_bands(self):
        self.assertEqual(
            self.problems(
                "8.0.111, 8.0.307, 8.0.404",
                ["7.0.410", "8.0.110", "8.0.111", "8.0.207", "8.0.306", "8.0.410", "8.0.500", "9.0.100"],
                BANDS,
            ),
            {
                "7.0.410": ".NET SDK 7.0.410 is below minimum 8.0.111",
                "8.0.110": ".NET SDK 8.0.110 is below minimum 8.0.111",
                "8.0.111": None,
                "8.0.207": ".NET SDK 8.0.207 is on release line 8.0.2xx, which has no listed minimum",
                "8.0.306": ".NET SDK 8.0.306 is below minimum 8.0.307",
                "8.0.410": None,
                "8.0.500": None,  # newer than every listed band
                "9.0.100": None,
            },
        )
        self.assertEqual(
            self.problems("8.0, 10.0", ["8.0.416", "9.0.300", "10.0.100", "11.0.100"], BANDS),
            {
                "8.0.416": None,
                "9.0.300": ".NET SDK 9.0.300 is on release line 9.0, which has no listed minimum",
                "10.0.100": None,
                "11.0.100": None,
            },
        )

    def test_one_minimum_matches_a_plain_comparison(self):
        versions = ["2.7.18", "3.9", "3.11.9", "3.12", "3.12.0rc1", "3.12.7", "3.12.8", "3.13.0rc1", "3.13.0", "4.0"]
        for raw_min in ["3.9", "3.12", "3.12.8", "3.13.0rc1", "3", "4.0.1"]:
            minimum = parse_minimum(raw_min, MINOR)
            for raw in versions:
                with self.subTest(minimum=raw_min, version=raw):
                    meets = compare_versions(v(raw), v(raw_min)) >= 0
                    self.assertEqual(minimum.problem(v(raw)) is None, meets)
        for raw_min in ["8.0", "8.0.404", "9.0.100-rc.2.24474.11"]:
            minimum = parse_minimum(raw_min, BANDS)
            for raw in ["6.0.428", "8.0.111", "8.0.404", "8.0.410", "9.0.100-rc.1.1", "9.0.100", "10.0.100"]:
                with self.subTest(minimum=raw_min, version=raw):
                    meets = compare_versions(v(raw, BANDS), v(raw_min, BANDS)) >= 0
                    self.assertEqual(minimum.problem(v(raw, BANDS)) is None, meets)


if __name__ == "__main__":
    unittest.main()

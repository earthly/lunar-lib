"""Unit tests for the allowed-licenses check.

The fixtures under fixtures/ are real syft 1.51.1 output (CycloneDX 1.7 and
SPDX 2.3) for an npm lockfile, trimmed to the packages the tests name. They
pin how syft actually encodes each license shape, e.g. that it writes
"(Apache-2.0 WITH LLVM-exception)" to CycloneDX `license.name` and to an SPDX
LicenseRef rather than to an expression field.
"""

import importlib.util
import json
import os
import sys
import unittest
from contextlib import contextmanager

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(HERE)
sys.path.insert(0, PLUGIN_DIR)

from lunar_policy import CheckStatus, Node  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "allowed_licenses", os.path.join(PLUGIN_DIR, "allowed-licenses.py")
)
allowed_licenses = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(allowed_licenses)

PERMISSIVE = '["MIT", "ISC", "0BSD", "Apache-2.0", "BSD-3-Clause", "Python-2.0", "Zlib"]'


def fixture(name):
    with open(os.path.join(HERE, "fixtures", name)) as f:
        return json.load(f)


@contextmanager
def allowed(value):
    key = "LUNAR_VAR_allowed_licenses"
    saved = os.environ.get(key)
    if value is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = value
    try:
        yield
    finally:
        if saved is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = saved


def run(data, allowed_value, finished=True):
    with allowed(allowed_value):
        return allowed_licenses.main(
            Node.from_component_json(data, {"workflows_finished": finished})
        )


def cyclonedx(*components, prefix="auto"):
    return {"sbom": {prefix: {"cyclonedx": {"bomFormat": "CycloneDX", "components": list(components)}}}}


def component(name, *licenses, version="1.0.0"):
    entry = {"name": name, "version": version, "type": "library"}
    if licenses:
        entry["licenses"] = list(licenses)
    return entry


def lic_id(value):
    return {"license": {"id": value}}


def lic_name(value):
    return {"license": {"name": value}}


def expr(value):
    return {"expression": value}


def spdx_package(name, concluded="NOASSERTION", declared="NOASSERTION"):
    return {"name": name, "versionInfo": "1.0.0", "licenseConcluded": concluded, "licenseDeclared": declared}


def is_skipped(check):
    return any(r.result == CheckStatus.SKIPPED for r in check._results)


class RealSyftOutputTest(unittest.TestCase):
    """Verdicts on real syft output, in both SBOM formats syft emits."""

    def cyclonedx_json(self):
        return {"sbom": {"auto": {"cyclonedx": fixture("syft-npm.cyclonedx.json")}}}

    def spdx_json(self):
        return {"sbom": {"cicd": {"spdx": fixture("syft-npm.spdx.json")}}}

    def test_fixture_carries_every_license_shape(self):
        by_name = {c["name"]: c.get("licenses") for c in fixture("syft-npm.cyclonedx.json")["components"]}
        self.assertEqual(by_name["tslib"], [lic_id("0BSD")])
        self.assertEqual(by_name["ag-grid-enterprise"], [lic_name("Commercial")])
        self.assertEqual(by_name["@bytecodealliance/preview2-shim"], [lic_name("(Apache-2.0 WITH LLVM-exception)")])
        self.assertEqual(by_name["jszip"], [expr("MIT OR GPL-3.0-or-later")])
        self.assertEqual(by_name["pako"], [expr("MIT AND Zlib")])
        self.assertIsNone(by_name["/src/package-lock.json"])

        packages = {p["name"]: p for p in fixture("syft-npm.spdx.json")["packages"]}
        self.assertEqual(packages["ag-grid-enterprise"]["licenseDeclared"], "LicenseRef-Commercial")
        self.assertEqual(
            packages["@bytecodealliance/preview2-shim"]["licenseDeclared"],
            "LicenseRef--Apache-2.0-WITH-LLVM-exception-",
        )
        self.assertEqual(packages["pako"]["licenseDeclared"], "(MIT AND Zlib)")
        self.assertEqual(packages["pako"]["licenseConcluded"], "NOASSERTION")

    def test_permissive_list_fails_only_the_commercial_license(self):
        check = run(self.cyclonedx_json(), PERMISSIVE)
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertEqual(
            check.failure_reasons,
            ["License 'Commercial' is not in allowed_licenses: ag-grid-enterprise@36.2.0"],
        )

    def test_spdx_gives_the_same_verdict_and_names_the_licenseref(self):
        check = run(self.spdx_json(), PERMISSIVE)
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertEqual(
            check.failure_reasons,
            ["License 'LicenseRef-Commercial (Commercial)' is not in allowed_licenses: ag-grid-enterprise@36.2.0"],
        )

    def test_listing_the_name_admits_it_in_both_formats(self):
        permitted = PERMISSIVE[:-1] + ', "Commercial"]'
        self.assertEqual(run(self.cyclonedx_json(), permitted).status, CheckStatus.PASS)
        self.assertEqual(run(self.spdx_json(), permitted).status, CheckStatus.PASS)

    def test_and_needs_every_operand(self):
        without_zlib = '["MIT", "ISC", "0BSD", "Apache-2.0", "BSD-3-Clause", "Python-2.0", "Commercial"]'
        for data in (self.cyclonedx_json(), self.spdx_json()):
            self.assertEqual(
                run(data, without_zlib).failure_reasons,
                [f"License '{'MIT AND Zlib' if 'auto' in data['sbom'] else '(MIT AND Zlib)'}' "
                 "is not in allowed_licenses: pako@1.0.11"],
            )

    def test_with_exception_is_admitted_by_its_base_license(self):
        # Apache-2.0 alone admits syft's "(Apache-2.0 WITH LLVM-exception)" name
        # and the SPDX LicenseRef it resolves to; dropping it fails both packages
        # that carry Apache-2.0 without an alternative.
        without_apache = '["MIT", "ISC", "0BSD", "BSD-3-Clause", "Python-2.0", "Zlib", "Commercial"]'
        for data in (self.cyclonedx_json(), self.spdx_json()):
            reasons = run(data, without_apache).failure_reasons
            self.assertEqual(len(reasons), 2, reasons)
            self.assertIn("@bytecodealliance/preview2-shim@0.26.0", reasons[0] + reasons[1])
            self.assertIn("dompurify@3.4.16", reasons[0] + reasons[1])

    def test_unlicensed_components_are_not_failed_here(self):
        # The fixture's file component and the SPDX root packages carry no
        # license (NOASSERTION); a list that admits every licensed package passes.
        everything = PERMISSIVE[:-1] + ', "Commercial"]'
        spdx_roots = [p for p in fixture("syft-npm.spdx.json")["packages"]
                      if p["licenseDeclared"] == p["licenseConcluded"] == "NOASSERTION"]
        self.assertEqual(len(spdx_roots), 2)
        self.assertEqual(run(self.spdx_json(), everything).status, CheckStatus.PASS)


class ApplicabilityTest(unittest.TestCase):
    def test_unset_input_skips_without_reading_the_sbom(self):
        check = run({}, None, finished=False)
        self.assertTrue(is_skipped(check))
        self.assertIn("allowed_licenses", check._results[0].failure_message)

    def test_empty_input_skips(self):
        for value in ("", "  ", "[]", " , "):
            self.assertTrue(is_skipped(run(cyclonedx(component("a", lic_id("GPL-3.0-only"))), value)), value)

    def test_no_sbom_skips(self):
        check = run({"sbom": {"license_origins": {"packages": []}}}, "MIT")
        self.assertTrue(is_skipped(check))
        self.assertEqual(check._results[0].failure_message, "No SBOM data available")

    def test_no_sbom_is_pending_while_collectors_run(self):
        self.assertEqual(run({}, "MIT", finished=False).status, CheckStatus.PENDING)

    def test_sbom_without_components_skips(self):
        data = {"sbom": {"auto": {"source": {"tool": "syft", "integration": "code"}}}}
        check = run(data, "MIT")
        self.assertTrue(is_skipped(check))
        self.assertEqual(check._results[0].failure_message, "SBOM has no components")

    def test_components_without_license_data_skip(self):
        data = cyclonedx(component("a"), {"name": "/src/go.mod", "type": "file"})
        check = run(data, "MIT")
        self.assertTrue(is_skipped(check))
        self.assertEqual(check._results[0].failure_message, "No SBOM component carries license data")

    def test_unlicensed_components_beside_licensed_ones_are_ignored(self):
        data = cyclonedx(component("a", lic_id("MIT")), component("b"))
        self.assertEqual(run(data, "MIT").status, CheckStatus.PASS)


class MatchingTest(unittest.TestCase):
    def verdict(self, entry, allowed_value):
        return run(cyclonedx(component("dep", entry)), allowed_value).status

    def test_identifiers_match_case_insensitively(self):
        self.assertEqual(self.verdict(lic_id("MIT"), "mit"), CheckStatus.PASS)
        self.assertEqual(self.verdict(lic_id("apache-2.0"), "Apache-2.0"), CheckStatus.PASS)

    def test_entries_match_the_whole_identifier(self):
        self.assertEqual(self.verdict(lic_id("MIT-0"), "MIT"), CheckStatus.FAIL)
        self.assertEqual(self.verdict(lic_id("LGPL-2.1-only"), "GPL-2.1-only"), CheckStatus.FAIL)

    def test_entries_can_be_regexes(self):
        self.assertEqual(self.verdict(lic_id("BSD-2-Clause"), "BSD-.*-Clause"), CheckStatus.PASS)
        self.assertEqual(self.verdict(lic_id("BSD-2-Clause"), "bsd-.*-clause"), CheckStatus.PASS)
        self.assertEqual(self.verdict(lic_id("BSD-4-Clause-UC"), "BSD-.*-Clause"), CheckStatus.FAIL)

    def test_a_literal_entry_needs_no_regex_escaping(self):
        self.assertEqual(self.verdict(lic_name("GPL (>= 2)"), '["GPL (>= 2)"]'), CheckStatus.PASS)

    def test_json_array_and_comma_forms_agree(self):
        entry = expr("MIT OR Apache-2.0")
        self.assertEqual(self.verdict(entry, "BSD-3-Clause, Apache-2.0"), CheckStatus.PASS)
        self.assertEqual(self.verdict(entry, '["BSD-3-Clause", "Apache-2.0"]'), CheckStatus.PASS)

    def test_invalid_regex_is_an_error(self):
        with self.assertRaisesRegex(ValueError, "Invalid regex in allowed_licenses"):
            run(cyclonedx(component("dep", lic_id("MIT"))), '["MIT", "BSD-(2"]')

    def test_free_text_needs_an_exact_entry(self):
        self.assertEqual(self.verdict(lic_name("MIT License"), "MIT"), CheckStatus.FAIL)
        self.assertEqual(self.verdict(lic_name("MIT License"), "mit license"), CheckStatus.PASS)

    def test_a_pattern_cannot_stretch_across_a_second_license(self):
        # "MIT.*" matches identifiers starting with MIT; it must not match a
        # free-text string that also names a copyleft license.
        self.assertEqual(self.verdict(lic_name("MIT, GPL-3.0-only"), "MIT.*"), CheckStatus.FAIL)
        self.assertEqual(self.verdict(expr("MIT AND GPL-3.0-only"), "MIT.*"), CheckStatus.FAIL)
        self.assertEqual(self.verdict(lic_id("MIT-0"), "MIT.*"), CheckStatus.PASS)


class ExpressionTest(unittest.TestCase):
    def verdict(self, expression, allowed_value):
        return run(cyclonedx(component("dep", expr(expression))), allowed_value).status

    def test_or_passes_when_either_side_is_allowed(self):
        self.assertEqual(self.verdict("GPL-3.0-only OR MIT", "MIT"), CheckStatus.PASS)
        self.assertEqual(self.verdict("GPL-3.0-only OR LGPL-2.1-only", "MIT"), CheckStatus.FAIL)

    def test_and_binds_tighter_than_or(self):
        # MIT OR (Apache-2.0 AND GPL-3.0-only)
        self.assertEqual(self.verdict("MIT OR Apache-2.0 AND GPL-3.0-only", "MIT"), CheckStatus.PASS)
        self.assertEqual(self.verdict("MIT OR Apache-2.0 AND GPL-3.0-only", "Apache-2.0"), CheckStatus.FAIL)

    def test_parentheses_override_precedence(self):
        self.assertEqual(
            self.verdict("(MIT OR Apache-2.0) AND GPL-3.0-only", '["MIT", "Apache-2.0"]'), CheckStatus.FAIL
        )
        self.assertEqual(
            self.verdict("(MIT OR Apache-2.0) AND (BSD-3-Clause OR GPL-3.0-only)", '["Apache-2.0", "BSD-3-Clause"]'),
            CheckStatus.PASS,
        )

    def test_with_is_admitted_by_the_pair_or_the_base_license(self):
        classpath = "GPL-2.0-only WITH Classpath-exception-2.0"
        self.assertEqual(self.verdict(classpath, "MIT"), CheckStatus.FAIL)
        self.assertEqual(self.verdict(classpath, f'["{classpath}"]'), CheckStatus.PASS)
        self.assertEqual(self.verdict(classpath, '["gpl-2.0-only with classpath-exception-2.0"]'), CheckStatus.PASS)
        self.assertEqual(self.verdict(classpath, "GPL-2.0-only"), CheckStatus.PASS)
        # Inside a compound expression the pair entry still admits its operand.
        self.assertEqual(self.verdict(f"{classpath} AND MIT", f'["{classpath}", "MIT"]'), CheckStatus.PASS)
        # The pair entry admits only that exception, not the bare license.
        self.assertEqual(
            run(cyclonedx(component("dep", lic_id("GPL-2.0-only"))), f'["{classpath}"]').status, CheckStatus.FAIL
        )

    def test_with_binds_tighter_than_and(self):
        self.assertEqual(
            self.verdict("Apache-2.0 WITH LLVM-exception AND MIT", '["Apache-2.0", "MIT"]'), CheckStatus.PASS
        )

    def test_or_later_is_admitted_by_its_base_version(self):
        self.assertEqual(self.verdict("LGPL-2.1+", "LGPL-2.1"), CheckStatus.PASS)
        self.assertEqual(self.verdict("LGPL-2.1+", '["LGPL-2.1+"]'), CheckStatus.PASS)
        self.assertEqual(self.verdict("LGPL-2.1+", "LGPL-3.0"), CheckStatus.FAIL)

    def test_operators_are_case_insensitive(self):
        self.assertEqual(self.verdict("GPL-3.0-only or MIT", "MIT"), CheckStatus.PASS)

    def test_an_identifier_field_holding_an_expression_is_parsed(self):
        # The syft collector writes a Rust crate's "X WITH E" to license.id.
        entry = lic_id("Apache-2.0 WITH LLVM-exception")
        self.assertEqual(run(cyclonedx(component("dep", entry)), "Apache-2.0").status, CheckStatus.PASS)

    def test_malformed_expressions_fail_unless_listed_exactly(self):
        for malformed in ("MIT OR", "(MIT", "MIT)", "MIT Apache-2.0", "WITH MIT", "MIT WITH", "()"):
            self.assertEqual(self.verdict(malformed, '["MIT", "Apache-2.0"]'), CheckStatus.FAIL, malformed)
        self.assertEqual(self.verdict("MIT OR", '["MIT OR"]'), CheckStatus.PASS)

    def test_parse_tree(self):
        parse = allowed_licenses.parse_expression
        self.assertEqual(parse("MIT"), ("license", "MIT", None))
        self.assertEqual(
            parse("A OR B AND C WITH X"),
            ("or", [("license", "A", None), ("and", [("license", "B", None), ("license", "C", "X")])]),
        )
        self.assertEqual(
            parse("(A OR B) AND C"),
            ("and", [("or", [("license", "A", None), ("license", "B", None)]), ("license", "C", None)]),
        )

    def test_deep_nesting_is_treated_as_malformed(self):
        deep = "(" * 5000 + "MIT" + ")" * 5000
        self.assertEqual(self.verdict(deep, "MIT"), CheckStatus.FAIL)


class ComponentShapeTest(unittest.TestCase):
    def test_every_separately_listed_license_must_be_allowed(self):
        data = cyclonedx(component("dual", lic_id("MIT"), lic_id("GPL-3.0-only")))
        check = run(data, "MIT")
        self.assertEqual(check.failure_reasons, ["License 'GPL-3.0-only' is not in allowed_licenses: dual@1.0.0"])

    def test_spdx_concluded_license_wins_over_declared(self):
        data = {"sbom": {"cicd": {"spdx": {"packages": [spdx_package("p", concluded="MIT", declared="GPL-3.0-only")]}}}}
        self.assertEqual(run(data, "MIT").status, CheckStatus.PASS)
        self.assertEqual(run(data, "GPL-3.0-only").status, CheckStatus.FAIL)

    def test_spdx_falls_back_to_declared_and_ignores_no_license_values(self):
        packages = [
            spdx_package("declared", declared="GPL-3.0-only"),
            spdx_package("none", concluded="NONE", declared="NONE"),
            spdx_package("unknown"),
        ]
        check = run({"sbom": {"cicd": {"spdx": {"packages": packages}}}}, "MIT")
        self.assertEqual(check.failure_reasons, ["License 'GPL-3.0-only' is not in allowed_licenses: declared@1.0.0"])

    def test_spdx_package_with_no_license_data_skips(self):
        data = {"sbom": {"cicd": {"spdx": {"packages": [spdx_package("root")]}}}}
        self.assertTrue(is_skipped(run(data, "MIT")))

    def test_a_component_in_both_sboms_is_reported_once(self):
        dep = component("copyleft", lic_id("GPL-3.0-only"))
        data = cyclonedx(dep)
        data["sbom"]["cicd"] = cyclonedx(dep, prefix="cicd")["sbom"]["cicd"]
        self.assertEqual(
            run(data, "MIT").failure_reasons,
            ["License 'GPL-3.0-only' is not in allowed_licenses: copyleft@1.0.0"],
        )

    def test_one_failure_per_license_with_a_capped_component_list(self):
        deps = [component(f"lib{i}", lic_id("GPL-3.0-only")) for i in range(7)]
        deps.append(component("other", lic_name("Commercial")))
        check = run(cyclonedx(*deps), "MIT")
        self.assertEqual(
            check.failure_reasons,
            [
                "License 'Commercial' is not in allowed_licenses: other@1.0.0",
                "License 'GPL-3.0-only' is not in allowed_licenses: "
                "lib0@1.0.0, lib1@1.0.0, lib2@1.0.0, lib3@1.0.0, lib4@1.0.0, +2 more",
            ],
        )

    def test_malformed_entries_are_ignored(self):
        data = cyclonedx(
            {"name": "odd", "licenses": ["MIT", {"license": {}}, {"license": {"id": ""}}, {"expression": 7}]},
            component("ok", lic_id("MIT")),
        )
        self.assertEqual(run(data, "MIT").status, CheckStatus.PASS)


if __name__ == "__main__":
    unittest.main()

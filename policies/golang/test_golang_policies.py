"""Unit tests for the golang policies."""

import unittest
from lunar_policy import Node, CheckStatus

from go_mod_exists import check_go_mod_exists
from go_sum_exists import check_go_sum_exists
from min_go_version import check_min_go_version
from min_go_version_cicd import check_min_go_version_cicd
from tests_recursive import check_tests_recursive
from vendoring import check_vendoring


class TestGoModExistsPolicy(unittest.TestCase):
    """Tests for the go-mod-exists policy."""

    def test_go_mod_exists_passes(self):
        """Project with go.mod should pass."""
        data = {
            "lang": {
                "go": {
                    "native": {
                        "go_mod": {"exists": True}
                    }
                }
            }
        }
        node = Node.from_component_json(data)
        check = check_go_mod_exists(node=node)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_go_mod_missing_fails(self):
        """Project without go.mod should fail."""
        data = {
            "lang": {
                "go": {
                    "native": {
                        "go_mod": {"exists": False}
                    }
                }
            }
        }
        node = Node.from_component_json(data)
        check = check_go_mod_exists(node=node)
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("go.mod not found", check.failure_reasons[0])

    def test_not_go_project_does_not_pass(self):
        """Non-Go project should not pass (skip or pending)."""
        data = {"lang": {"python": {}}}
        node = Node.from_component_json(data)
        check = check_go_mod_exists(node=node)
        # Should either skip or be pending, but definitely not pass or fail
        self.assertIn(check.status, [CheckStatus.SKIPPED, CheckStatus.PENDING])

    def test_empty_data_does_not_pass(self):
        """Empty component JSON should not pass."""
        data = {}
        node = Node.from_component_json(data)
        check = check_go_mod_exists(node=node)
        # Should either skip or be pending
        self.assertIn(check.status, [CheckStatus.SKIPPED, CheckStatus.PENDING])

    def test_go_project_without_native_data_skips(self):
        """Go project without native data should skip gracefully."""
        data = {"lang": {"go": {"version": "1.21"}}}
        node = Node.from_component_json(data)
        check = check_go_mod_exists(node=node)
        self.assertEqual(check.status, CheckStatus.SKIPPED)
        self.assertIn("Go module data not available", check.skip_reason)


class TestGoSumExistsPolicy(unittest.TestCase):
    """Tests for the go-sum-exists policy."""

    def test_go_sum_exists_passes(self):
        """Project with go.sum should pass."""
        data = {
            "lang": {
                "go": {
                    "native": {
                        "go_sum": {"exists": True}
                    }
                }
            }
        }
        node = Node.from_component_json(data)
        check = check_go_sum_exists(node=node)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_go_sum_missing_fails(self):
        """Project without go.sum should fail."""
        data = {
            "lang": {
                "go": {
                    "native": {
                        "go_sum": {"exists": False}
                    }
                }
            }
        }
        node = Node.from_component_json(data)
        check = check_go_sum_exists(node=node)
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("go.sum not found", check.failure_reasons[0])

    def test_not_go_project_does_not_pass(self):
        """Non-Go project should not pass."""
        data = {"lang": {"nodejs": {}}}
        node = Node.from_component_json(data)
        check = check_go_sum_exists(node=node)
        self.assertIn(check.status, [CheckStatus.SKIPPED, CheckStatus.PENDING])

    def test_empty_data_does_not_pass(self):
        """Empty component JSON should not pass."""
        data = {}
        node = Node.from_component_json(data)
        check = check_go_sum_exists(node=node)
        self.assertIn(check.status, [CheckStatus.SKIPPED, CheckStatus.PENDING])

    def test_go_project_without_native_data_skips(self):
        """Go project without native data should skip gracefully."""
        data = {"lang": {"go": {"version": "1.21"}}}
        node = Node.from_component_json(data)
        check = check_go_sum_exists(node=node)
        self.assertEqual(check.status, CheckStatus.SKIPPED)
        self.assertIn("Go module data not available", check.skip_reason)


class TestMinGoVersionPolicy(unittest.TestCase):
    """Tests for the min-go-version policy."""

    def test_version_meets_minimum_passes(self):
        """Go version at minimum should pass."""
        data = {"lang": {"go": {"version": "1.21"}}}
        node = Node.from_component_json(data)
        check = check_min_go_version(min_version="1.21", node=node)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_version_exceeds_minimum_passes(self):
        """Go version above minimum should pass."""
        data = {"lang": {"go": {"version": "1.22"}}}
        node = Node.from_component_json(data)
        check = check_min_go_version(min_version="1.21", node=node)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_version_below_minimum_fails(self):
        """Go version below minimum should fail."""
        data = {"lang": {"go": {"version": "1.19"}}}
        node = Node.from_component_json(data)
        check = check_min_go_version(min_version="1.21", node=node)
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("below minimum", check.failure_reasons[0])

    def test_major_version_comparison(self):
        """Major version 2.x should pass for 1.x minimum."""
        data = {"lang": {"go": {"version": "2.0"}}}
        node = Node.from_component_json(data)
        check = check_min_go_version(min_version="1.21", node=node)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_major_version_below_fails(self):
        """Major version 1.x should fail for 2.x minimum."""
        data = {"lang": {"go": {"version": "1.99"}}}
        node = Node.from_component_json(data)
        check = check_min_go_version(min_version="2.0", node=node)
        self.assertEqual(check.status, CheckStatus.FAIL)

    def test_patch_version_ignored(self):
        """Patch versions should be ignored in comparison."""
        data = {"lang": {"go": {"version": "1.21.5"}}}
        node = Node.from_component_json(data)
        check = check_min_go_version(min_version="1.21", node=node)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_not_go_project_does_not_pass(self):
        """Non-Go project should not pass."""
        data = {"lang": {"java": {"version": "17"}}}
        node = Node.from_component_json(data)
        check = check_min_go_version(min_version="1.21", node=node)
        self.assertIn(check.status, [CheckStatus.SKIPPED, CheckStatus.PENDING])

    def test_no_version_data_does_not_pass_or_fail(self):
        """Go project without version should not pass or fail."""
        data = {"lang": {"go": {"native": {"go_mod": {"exists": True}}}}}
        node = Node.from_component_json(data)
        check = check_min_go_version(min_version="1.21", node=node)
        self.assertIn(check.status, [CheckStatus.SKIPPED, CheckStatus.PENDING])

    def test_empty_data_does_not_pass(self):
        """Empty component JSON should not pass."""
        data = {}
        node = Node.from_component_json(data)
        check = check_min_go_version(min_version="1.21", node=node)
        self.assertIn(check.status, [CheckStatus.SKIPPED, CheckStatus.PENDING])

    def test_version_as_float_handled(self):
        """Version stored as float should be handled."""
        data = {"lang": {"go": {"version": 1.21}}}
        node = Node.from_component_json(data)
        check = check_min_go_version(min_version="1.21", node=node)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_version_with_extra_parts(self):
        """Version with extra parts like 1.21.0-rc1 should work."""
        data = {"lang": {"go": {"version": "1.22.0"}}}
        node = Node.from_component_json(data)
        check = check_min_go_version(min_version="1.21.5", node=node)
        self.assertEqual(check.status, CheckStatus.PASS)


class TestMinGoVersionCicdPolicy(unittest.TestCase):
    """Tests for the min-go-version-cicd policy."""

    def test_version_meets_minimum_passes(self):
        """CI/CD Go version at minimum should pass."""
        data = {
            "lang": {
                "go": {
                    "cicd": {
                        "cmds": [{"cmd": "go test ./...", "version": "1.21.5"}]
                    }
                }
            }
        }
        node = Node.from_component_json(data)
        check = check_min_go_version_cicd(min_version="1.21", node=node)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_version_exceeds_minimum_passes(self):
        """CI/CD Go version above minimum should pass."""
        data = {
            "lang": {
                "go": {
                    "cicd": {
                        "cmds": [{"cmd": "go build", "version": "1.22.0"}]
                    }
                }
            }
        }
        node = Node.from_component_json(data)
        check = check_min_go_version_cicd(min_version="1.21", node=node)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_version_below_minimum_fails(self):
        """CI/CD Go version below minimum should fail."""
        data = {
            "lang": {
                "go": {
                    "cicd": {
                        "cmds": [{"cmd": "go test ./...", "version": "1.19.5"}]
                    }
                }
            }
        }
        node = Node.from_component_json(data)
        check = check_min_go_version_cicd(min_version="1.21", node=node)
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("below", check.failure_reasons[0])

    def test_multiple_commands_one_fails(self):
        """Multiple commands with one below minimum should fail."""
        data = {
            "lang": {
                "go": {
                    "cicd": {
                        "cmds": [
                            {"cmd": "go test ./...", "version": "1.22.0"},
                            {"cmd": "go build", "version": "1.19.0"}
                        ]
                    }
                }
            }
        }
        node = Node.from_component_json(data)
        check = check_min_go_version_cicd(min_version="1.21", node=node)
        self.assertEqual(check.status, CheckStatus.FAIL)

    def test_not_go_project_skips(self):
        """Non-Go project should skip."""
        data = {"lang": {"python": {}}}
        node = Node.from_component_json(data)
        check = check_min_go_version_cicd(min_version="1.21", node=node)
        self.assertIn(check.status, [CheckStatus.SKIPPED, CheckStatus.PENDING])

    def test_no_cicd_data_skips(self):
        """Go project without CI/CD data should skip."""
        data = {"lang": {"go": {"version": "1.21"}}}
        node = Node.from_component_json(data)
        check = check_min_go_version_cicd(min_version="1.21", node=node)
        self.assertIn(check.status, [CheckStatus.SKIPPED, CheckStatus.PENDING])

    def test_empty_data_skips(self):
        """Empty component JSON should skip."""
        data = {}
        node = Node.from_component_json(data)
        check = check_min_go_version_cicd(min_version="1.21", node=node)
        self.assertIn(check.status, [CheckStatus.SKIPPED, CheckStatus.PENDING])


class TestTestsRecursivePolicy(unittest.TestCase):
    """Tests for the tests-recursive policy."""

    def test_recursive_scope_passes(self):
        """Tests with recursive scope should pass."""
        data = {"lang": {"go": {"tests": {"scope": "recursive"}}}}
        node = Node.from_component_json(data)
        check = check_tests_recursive(node=node)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_package_scope_fails(self):
        """Tests with package scope should fail."""
        data = {"lang": {"go": {"tests": {"scope": "package"}}}}
        node = Node.from_component_json(data)
        check = check_tests_recursive(node=node)
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("instead of 'recursive'", check.failure_reasons[0])

    def test_single_scope_fails(self):
        """Tests with single scope should fail."""
        data = {"lang": {"go": {"tests": {"scope": "single"}}}}
        node = Node.from_component_json(data)
        check = check_tests_recursive(node=node)
        self.assertEqual(check.status, CheckStatus.FAIL)

    def test_not_go_project_does_not_pass(self):
        """Non-Go project should not pass."""
        data = {"lang": {"rust": {}}}
        node = Node.from_component_json(data)
        check = check_tests_recursive(node=node)
        self.assertIn(check.status, [CheckStatus.SKIPPED, CheckStatus.PENDING])

    def test_no_test_scope_data_does_not_pass_or_fail(self):
        """Go project without test scope data should not pass or fail."""
        data = {"lang": {"go": {"version": "1.21"}}}
        node = Node.from_component_json(data)
        check = check_tests_recursive(node=node)
        self.assertIn(check.status, [CheckStatus.SKIPPED, CheckStatus.PENDING])

    def test_empty_tests_object_does_not_pass_or_fail(self):
        """Go project with empty tests object should not pass or fail."""
        data = {"lang": {"go": {"tests": {}}}}
        node = Node.from_component_json(data)
        check = check_tests_recursive(node=node)
        self.assertIn(check.status, [CheckStatus.SKIPPED, CheckStatus.PENDING])

    def test_empty_data_does_not_pass(self):
        """Empty component JSON should not pass."""
        data = {}
        node = Node.from_component_json(data)
        check = check_tests_recursive(node=node)
        self.assertIn(check.status, [CheckStatus.SKIPPED, CheckStatus.PENDING])


class TestVendoringPolicy(unittest.TestCase):
    """Tests for the vendoring policy."""

    def test_mode_none_does_not_fail(self):
        """Vendoring mode 'none' should not fail (skip or pass)."""
        data = {"lang": {"go": {"native": {"vendor": {"exists": True}}}}}
        node = Node.from_component_json(data)
        check = check_vendoring(mode="none", node=node)
        # Mode "none" means skip the check - it should either skip or pass
        self.assertIn(check.status, [CheckStatus.SKIPPED, CheckStatus.PASS])

    def test_mode_required_vendor_exists_passes(self):
        """Required mode with vendor directory should pass."""
        data = {"lang": {"go": {"native": {"vendor": {"exists": True}}}}}
        node = Node.from_component_json(data)
        check = check_vendoring(mode="required", node=node)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_mode_required_vendor_missing_fails(self):
        """Required mode without vendor directory should fail."""
        data = {"lang": {"go": {"native": {"vendor": {"exists": False}}}}}
        node = Node.from_component_json(data)
        check = check_vendoring(mode="required", node=node)
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("required but not found", check.failure_reasons[0])

    def test_mode_forbidden_vendor_exists_fails(self):
        """Forbidden mode with vendor directory should fail."""
        data = {"lang": {"go": {"native": {"vendor": {"exists": True}}}}}
        node = Node.from_component_json(data)
        check = check_vendoring(mode="forbidden", node=node)
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("forbidden", check.failure_reasons[0])

    def test_mode_forbidden_vendor_missing_passes(self):
        """Forbidden mode without vendor directory should pass."""
        data = {"lang": {"go": {"native": {"vendor": {"exists": False}}}}}
        node = Node.from_component_json(data)
        check = check_vendoring(mode="forbidden", node=node)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_invalid_mode_fails(self):
        """Invalid vendoring mode should fail."""
        data = {"lang": {"go": {"native": {"vendor": {"exists": False}}}}}
        node = Node.from_component_json(data)
        check = check_vendoring(mode="invalid", node=node)
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("Invalid vendoring_mode", check.failure_reasons[0])

    def test_not_go_project_does_not_pass(self):
        """Non-Go project should not pass."""
        data = {"lang": {"python": {}}}
        node = Node.from_component_json(data)
        check = check_vendoring(mode="required", node=node)
        self.assertIn(check.status, [CheckStatus.SKIPPED, CheckStatus.PENDING])

    def test_empty_data_does_not_pass(self):
        """Empty component JSON should not pass."""
        data = {}
        node = Node.from_component_json(data)
        check = check_vendoring(mode="required", node=node)
        self.assertIn(check.status, [CheckStatus.SKIPPED, CheckStatus.PENDING])

    def test_no_vendor_data_required_mode_fails(self):
        """Missing vendor data in required mode should fail (defaults to False)."""
        data = {"lang": {"go": {"native": {}}}}
        node = Node.from_component_json(data)
        check = check_vendoring(mode="required", node=node)
        self.assertEqual(check.status, CheckStatus.FAIL)

    def test_no_vendor_data_forbidden_mode_passes(self):
        """Missing vendor data in forbidden mode should pass (defaults to False)."""
        data = {"lang": {"go": {"native": {}}}}
        node = Node.from_component_json(data)
        check = check_vendoring(mode="forbidden", node=node)
        self.assertEqual(check.status, CheckStatus.PASS)


class TestCompleteGoProject(unittest.TestCase):
    """Tests for a complete Go project."""

    def test_complete_go_project_all_pass(self):
        """A complete, compliant Go project should pass all checks."""
        data = {
            "lang": {
                "go": {
                    "module": "github.com/example/app",
                    "version": "1.22",
                    "native": {
                        "go_mod": {"exists": True, "version": "1.22"},
                        "go_sum": {"exists": True},
                        "vendor": {"exists": False}
                    },
                    "tests": {
                        "scope": "recursive",
                        "coverage": {"percentage": 85.5}
                    }
                }
            }
        }
        node = Node.from_component_json(data)

        self.assertEqual(check_go_mod_exists(node=node).status, CheckStatus.PASS)
        self.assertEqual(check_go_sum_exists(node=node).status, CheckStatus.PASS)
        self.assertEqual(check_min_go_version(min_version="1.21", node=node).status, CheckStatus.PASS)
        self.assertEqual(check_tests_recursive(node=node).status, CheckStatus.PASS)
        self.assertEqual(check_vendoring(mode="forbidden", node=node).status, CheckStatus.PASS)


class TestMultipleLanguagesProject(unittest.TestCase):
    """Tests for projects with multiple languages."""

    def test_go_checks_ignore_other_languages(self):
        """Go checks should only look at Go data, ignoring other languages."""
        data = {
            "lang": {
                "go": {
                    "version": "1.22",
                    "native": {
                        "go_mod": {"exists": True},
                        "go_sum": {"exists": True},
                        "vendor": {"exists": False}
                    },
                    "tests": {"scope": "recursive"}
                },
                "python": {
                    "version": "3.11"
                },
                "nodejs": {
                    "version": "20.0.0"
                }
            }
        }
        node = Node.from_component_json(data)

        # All Go checks should still work
        self.assertEqual(check_go_mod_exists(node=node).status, CheckStatus.PASS)
        self.assertEqual(check_go_sum_exists(node=node).status, CheckStatus.PASS)
        self.assertEqual(check_min_go_version(min_version="1.21", node=node).status, CheckStatus.PASS)
        self.assertEqual(check_tests_recursive(node=node).status, CheckStatus.PASS)
        self.assertEqual(check_vendoring(mode="forbidden", node=node).status, CheckStatus.PASS)


if __name__ == "__main__":
    unittest.main()

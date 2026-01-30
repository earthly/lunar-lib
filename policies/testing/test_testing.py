"""Unit tests for the testing policy."""

import unittest
from lunar_policy import Node, CheckStatus

from executed import check_executed
from passing import check_passing


class TestExecutedPolicy(unittest.TestCase):
    """Tests for the 'executed' check."""

    def test_testing_exists_passes(self):
        """When .testing exists, check should pass."""
        data = {
            "testing": {
                "source": {
                    "framework": "go test",
                    "integration": "ci"
                }
            }
        }
        node = Node.from_component_json(data)
        check = check_executed(node=node)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_testing_with_full_results_passes(self):
        """When .testing exists with full results, check should pass."""
        data = {
            "testing": {
                "source": {
                    "framework": "pytest",
                    "integration": "ci"
                },
                "results": {
                    "total": 100,
                    "passed": 98,
                    "failed": 2,
                    "skipped": 0
                },
                "all_passing": False
            }
        }
        node = Node.from_component_json(data)
        check = check_executed(node=node)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_empty_testing_object_passes(self):
        """When .testing exists but is empty, check should still pass."""
        data = {"testing": {}}
        node = Node.from_component_json(data)
        check = check_executed(node=node)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_no_testing_data_fails(self):
        """When .testing doesn't exist, check should fail."""
        data = {}
        node = Node.from_component_json(data)
        check = check_executed(node=node)
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("No test execution data found", check.failure_reasons[0])

    def test_other_data_but_no_testing_fails(self):
        """When other data exists but not .testing, check should fail."""
        data = {
            "repo": {"readme_exists": True},
            "lang": {"go": {"version": "1.21"}}
        }
        node = Node.from_component_json(data)
        check = check_executed(node=node)
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("No test execution data found", check.failure_reasons[0])

    def test_testing_null_fails(self):
        """When .testing is explicitly null, check should fail."""
        data = {"testing": None}
        node = Node.from_component_json(data)
        check = check_executed(node=node)
        self.assertEqual(check.status, CheckStatus.FAIL)


class TestPassingPolicy(unittest.TestCase):
    """Tests for the 'passing' check."""

    def test_all_passing_true_passes(self):
        """When .testing.all_passing is true, check should pass."""
        data = {
            "testing": {
                "source": {
                    "framework": "go test",
                    "integration": "ci"
                },
                "results": {
                    "total": 100,
                    "passed": 100,
                    "failed": 0,
                    "skipped": 0
                },
                "all_passing": True
            }
        }
        node = Node.from_component_json(data)
        check = check_passing(node=node)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_all_passing_false_fails(self):
        """When .testing.all_passing is false, check should fail."""
        data = {
            "testing": {
                "source": {
                    "framework": "pytest",
                    "integration": "ci"
                },
                "results": {
                    "total": 100,
                    "passed": 95,
                    "failed": 5,
                    "skipped": 0
                },
                "all_passing": False
            }
        }
        node = Node.from_component_json(data)
        check = check_passing(node=node)
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("Tests are failing", check.failure_reasons[0])

    def test_no_testing_data_skips(self):
        """When .testing doesn't exist, check should skip."""
        data = {}
        node = Node.from_component_json(data)
        check = check_passing(node=node)
        self.assertEqual(check.status, CheckStatus.SKIPPED)
        self.assertIn("No test execution data found", check.skip_reason)

    def test_testing_exists_but_no_all_passing_skips(self):
        """When .testing exists but .all_passing doesn't, check should skip."""
        data = {
            "testing": {
                "source": {
                    "framework": "go test",
                    "integration": "ci"
                }
            }
        }
        node = Node.from_component_json(data)
        check = check_passing(node=node)
        self.assertEqual(check.status, CheckStatus.SKIPPED)
        self.assertIn("Test pass/fail data not available", check.skip_reason)

    def test_testing_with_results_but_no_all_passing_skips(self):
        """When .testing has results but no .all_passing, check should skip."""
        data = {
            "testing": {
                "source": {
                    "framework": "jest",
                    "integration": "ci"
                },
                "results": {
                    "total": 50,
                    "passed": 50,
                    "failed": 0
                }
                # Note: no all_passing field
            }
        }
        node = Node.from_component_json(data)
        check = check_passing(node=node)
        self.assertEqual(check.status, CheckStatus.SKIPPED)
        self.assertIn("Test pass/fail data not available", check.skip_reason)

    def test_empty_testing_object_skips(self):
        """When .testing is empty, check should skip (no all_passing)."""
        data = {"testing": {}}
        node = Node.from_component_json(data)
        check = check_passing(node=node)
        self.assertEqual(check.status, CheckStatus.SKIPPED)

    def test_all_passing_null_skips(self):
        """When .testing.all_passing is null, check should skip."""
        data = {
            "testing": {
                "all_passing": None
            }
        }
        node = Node.from_component_json(data)
        check = check_passing(node=node)
        self.assertEqual(check.status, CheckStatus.SKIPPED)

    def test_other_data_but_no_testing_skips(self):
        """When other data exists but not .testing, check should skip."""
        data = {
            "repo": {"readme_exists": True},
            "coverage": {"percentage": 85.5}
        }
        node = Node.from_component_json(data)
        check = check_passing(node=node)
        self.assertEqual(check.status, CheckStatus.SKIPPED)
        self.assertIn("No test execution data found", check.skip_reason)


class TestPassingPolicyEdgeCases(unittest.TestCase):
    """Edge case tests for the 'passing' check."""

    def test_all_passing_with_zero_tests_passes(self):
        """When all_passing is true with zero tests, check should pass."""
        data = {
            "testing": {
                "results": {
                    "total": 0,
                    "passed": 0,
                    "failed": 0
                },
                "all_passing": True
            }
        }
        node = Node.from_component_json(data)
        check = check_passing(node=node)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_all_passing_with_only_skipped_tests_passes(self):
        """When all_passing is true with only skipped tests, check should pass."""
        data = {
            "testing": {
                "results": {
                    "total": 10,
                    "passed": 0,
                    "failed": 0,
                    "skipped": 10
                },
                "all_passing": True
            }
        }
        node = Node.from_component_json(data)
        check = check_passing(node=node)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_failures_array_present_but_all_passing_true(self):
        """When failures array exists but all_passing is true, should pass."""
        data = {
            "testing": {
                "results": {
                    "total": 100,
                    "passed": 100,
                    "failed": 0
                },
                "failures": [],
                "all_passing": True
            }
        }
        node = Node.from_component_json(data)
        check = check_passing(node=node)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_failures_array_with_items_and_all_passing_false(self):
        """When failures array has items and all_passing is false, should fail."""
        data = {
            "testing": {
                "results": {
                    "total": 100,
                    "passed": 98,
                    "failed": 2
                },
                "failures": [
                    {
                        "name": "TestPaymentValidation",
                        "file": "payment_test.go",
                        "message": "expected 200, got 400"
                    },
                    {
                        "name": "TestUserAuth",
                        "file": "auth_test.go",
                        "message": "timeout"
                    }
                ],
                "all_passing": False
            }
        }
        node = Node.from_component_json(data)
        check = check_passing(node=node)
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("Tests are failing", check.failure_reasons[0])

    def test_different_frameworks_with_all_passing(self):
        """Test with different framework sources."""
        frameworks = [
            {"framework": "go test", "integration": "ci"},
            {"framework": "pytest", "integration": "github-actions"},
            {"framework": "jest", "integration": "buildkite"},
            {"framework": "junit", "integration": "ci"},
        ]
        
        for source in frameworks:
            data = {
                "testing": {
                    "source": source,
                    "all_passing": True
                }
            }
            node = Node.from_component_json(data)
            check = check_passing(node=node)
            self.assertEqual(
                check.status, CheckStatus.PASS,
                f"Failed for framework: {source['framework']}"
            )


class TestCoverageDataPresent(unittest.TestCase):
    """Tests when coverage data is also present."""

    def test_testing_and_coverage_both_present_executed_passes(self):
        """When both testing and coverage exist, executed should pass."""
        data = {
            "testing": {
                "source": {
                    "framework": "go test",
                    "integration": "ci"
                },
                "coverage": {
                    "percentage": 85.5
                }
            }
        }
        node = Node.from_component_json(data)
        check = check_executed(node=node)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_testing_with_coverage_and_all_passing_passes(self):
        """When testing has coverage and all_passing, passing should pass."""
        data = {
            "testing": {
                "source": {
                    "framework": "go test",
                    "integration": "ci"
                },
                "results": {
                    "total": 100,
                    "passed": 100,
                    "failed": 0
                },
                "all_passing": True,
                "coverage": {
                    "percentage": 85.5
                }
            }
        }
        node = Node.from_component_json(data)
        check = check_passing(node=node)
        self.assertEqual(check.status, CheckStatus.PASS)


if __name__ == "__main__":
    unittest.main()

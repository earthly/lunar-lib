"""Unit tests for the min-versions policy."""

import unittest
from lunar_policy import Node, CheckStatus

from min_versions import check_min_versions


class TestMinVersionsPolicy(unittest.TestCase):
    """Tests for semantic version comparison logic."""

    def test_version_meets_minimum_passes(self):
        """Dependency at exactly minimum version should pass."""
        data = {
            "lang": {
                "go": {
                    "dependencies": {
                        "direct": [
                            {"path": "github.com/example/lib", "version": "v1.2.0"}
                        ]
                    }
                }
            }
        }
        node = Node.from_component_json(data)
        min_versions = {"github.com/example/lib": "1.2.0"}
        
        check = check_min_versions("go", min_versions, node=node)
        
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_version_exceeds_minimum_passes(self):
        """Dependency above minimum version should pass."""
        data = {
            "lang": {
                "go": {
                    "dependencies": {
                        "direct": [
                            {"path": "github.com/example/lib", "version": "v2.0.0"}
                        ]
                    }
                }
            }
        }
        node = Node.from_component_json(data)
        min_versions = {"github.com/example/lib": "1.2.0"}
        
        check = check_min_versions("go", min_versions, node=node)
        
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_version_below_minimum_fails(self):
        """Dependency below minimum version should fail."""
        data = {
            "lang": {
                "go": {
                    "dependencies": {
                        "direct": [
                            {"path": "github.com/example/lib", "version": "v1.0.0"}
                        ]
                    }
                }
            }
        }
        node = Node.from_component_json(data)
        min_versions = {"github.com/example/lib": "1.2.0"}
        
        check = check_min_versions("go", min_versions, node=node)
        
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("below minimum safe version", check.failure_reasons[0])

    def test_v_prefix_handled(self):
        """Version with 'v' prefix should be parsed correctly."""
        data = {
            "lang": {
                "go": {
                    "dependencies": {
                        "direct": [
                            {"path": "github.com/example/lib", "version": "v1.2.3"}
                        ]
                    }
                }
            }
        }
        node = Node.from_component_json(data)
        # Min version without v prefix
        min_versions = {"github.com/example/lib": "1.2.0"}
        
        check = check_min_versions("go", min_versions, node=node)
        
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_min_version_with_v_prefix_handled(self):
        """Min version with 'v' prefix should be parsed correctly."""
        data = {
            "lang": {
                "go": {
                    "dependencies": {
                        "direct": [
                            {"path": "github.com/example/lib", "version": "1.2.3"}
                        ]
                    }
                }
            }
        }
        node = Node.from_component_json(data)
        # Min version with v prefix
        min_versions = {"github.com/example/lib": "v1.2.0"}
        
        check = check_min_versions("go", min_versions, node=node)
        
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_patch_version_comparison(self):
        """Patch version differences should be compared correctly."""
        data = {
            "lang": {
                "go": {
                    "dependencies": {
                        "direct": [
                            {"path": "github.com/example/lib", "version": "v1.2.3"}
                        ]
                    }
                }
            }
        }
        node = Node.from_component_json(data)
        min_versions = {"github.com/example/lib": "1.2.4"}
        
        check = check_min_versions("go", min_versions, node=node)
        
        self.assertEqual(check.status, CheckStatus.FAIL)

    def test_minor_version_comparison(self):
        """Minor version differences should be compared correctly."""
        data = {
            "lang": {
                "go": {
                    "dependencies": {
                        "direct": [
                            {"path": "github.com/example/lib", "version": "v1.3.0"}
                        ]
                    }
                }
            }
        }
        node = Node.from_component_json(data)
        min_versions = {"github.com/example/lib": "1.2.0"}
        
        check = check_min_versions("go", min_versions, node=node)
        
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_major_version_comparison(self):
        """Major version differences should be compared correctly."""
        data = {
            "lang": {
                "go": {
                    "dependencies": {
                        "direct": [
                            {"path": "github.com/example/lib", "version": "v1.9.9"}
                        ]
                    }
                }
            }
        }
        node = Node.from_component_json(data)
        min_versions = {"github.com/example/lib": "2.0.0"}
        
        check = check_min_versions("go", min_versions, node=node)
        
        self.assertEqual(check.status, CheckStatus.FAIL)

    def test_pseudo_version_comparison(self):
        """Go pseudo-versions (v0.0.0-timestamp-hash) are parsed as prerelease and compared."""
        data = {
            "lang": {
                "go": {
                    "dependencies": {
                        "direct": [
                            {"path": "github.com/example/lib", "version": "v0.0.0-20240101120000-abcdef123456"}
                        ]
                    }
                }
            }
        }
        node = Node.from_component_json(data)
        min_versions = {"github.com/example/lib": "1.0.0"}
        
        check = check_min_versions("go", min_versions, node=node)
        
        # Pseudo-versions are parsed as semver prereleases (0.0.0-...) which are < 1.0.0
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("below minimum safe version", check.failure_reasons[0])

    def test_truly_invalid_version_fails(self):
        """Truly non-semver versions should fail with parse error."""
        data = {
            "lang": {
                "go": {
                    "dependencies": {
                        "direct": [
                            {"path": "github.com/example/lib", "version": "not-a-version"}
                        ]
                    }
                }
            }
        }
        node = Node.from_component_json(data)
        min_versions = {"github.com/example/lib": "1.0.0"}
        
        check = check_min_versions("go", min_versions, node=node)
        
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("Cannot parse version", check.failure_reasons[0])
        self.assertIn("semver format", check.failure_reasons[0])

    def test_empty_min_versions_passes(self):
        """Empty min_versions dict should pass (no requirements)."""
        data = {
            "lang": {
                "go": {
                    "dependencies": {
                        "direct": [
                            {"path": "github.com/example/lib", "version": "v1.0.0"}
                        ]
                    }
                }
            }
        }
        node = Node.from_component_json(data)
        min_versions = {}
        
        check = check_min_versions("go", min_versions, node=node)
        
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_unlisted_dependency_ignored(self):
        """Dependencies not in min_versions should be ignored."""
        data = {
            "lang": {
                "go": {
                    "dependencies": {
                        "direct": [
                            {"path": "github.com/other/lib", "version": "v0.1.0"}
                        ]
                    }
                }
            }
        }
        node = Node.from_component_json(data)
        min_versions = {"github.com/example/lib": "1.0.0"}
        
        check = check_min_versions("go", min_versions, node=node)
        
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_multiple_dependencies_all_pass(self):
        """Multiple dependencies all meeting requirements should pass."""
        data = {
            "lang": {
                "go": {
                    "dependencies": {
                        "direct": [
                            {"path": "github.com/example/lib-a", "version": "v1.5.0"},
                            {"path": "github.com/example/lib-b", "version": "v2.0.0"}
                        ]
                    }
                }
            }
        }
        node = Node.from_component_json(data)
        min_versions = {
            "github.com/example/lib-a": "1.0.0",
            "github.com/example/lib-b": "2.0.0"
        }
        
        check = check_min_versions("go", min_versions, node=node)
        
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_multiple_dependencies_one_fails(self):
        """If any dependency fails, the check should fail."""
        data = {
            "lang": {
                "go": {
                    "dependencies": {
                        "direct": [
                            {"path": "github.com/example/lib-a", "version": "v1.5.0"},
                            {"path": "github.com/example/lib-b", "version": "v1.0.0"}
                        ]
                    }
                }
            }
        }
        node = Node.from_component_json(data)
        min_versions = {
            "github.com/example/lib-a": "1.0.0",
            "github.com/example/lib-b": "2.0.0"
        }
        
        check = check_min_versions("go", min_versions, node=node)
        
        self.assertEqual(check.status, CheckStatus.FAIL)

    def test_indirect_dependencies_when_enabled(self):
        """Indirect dependencies should be checked when include_indirect=True."""
        data = {
            "lang": {
                "go": {
                    "dependencies": {
                        "direct": [],
                        "indirect": [
                            {"path": "github.com/example/lib", "version": "v1.0.0"}
                        ]
                    }
                }
            }
        }
        node = Node.from_component_json(data)
        min_versions = {"github.com/example/lib": "2.0.0"}
        
        check = check_min_versions("go", min_versions, include_indirect=True, node=node)
        
        self.assertEqual(check.status, CheckStatus.FAIL)

    def test_indirect_dependencies_ignored_by_default(self):
        """Indirect dependencies should be ignored when include_indirect=False."""
        data = {
            "lang": {
                "go": {
                    "dependencies": {
                        "direct": [],
                        "indirect": [
                            {"path": "github.com/example/lib", "version": "v1.0.0"}
                        ]
                    }
                }
            }
        }
        node = Node.from_component_json(data)
        min_versions = {"github.com/example/lib": "2.0.0"}
        
        check = check_min_versions("go", min_versions, include_indirect=False, node=node)
        
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_java_language(self):
        """Policy should work with Java dependencies."""
        data = {
            "lang": {
                "java": {
                    "dependencies": {
                        "direct": [
                            {"path": "org.apache.commons:commons-text", "version": "1.10.0"}
                        ]
                    }
                }
            }
        }
        node = Node.from_component_json(data)
        min_versions = {"org.apache.commons:commons-text": "1.10.0"}
        
        check = check_min_versions("java", min_versions, node=node)
        
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_prerelease_version(self):
        """Prerelease versions should be compared correctly (lower than release)."""
        data = {
            "lang": {
                "go": {
                    "dependencies": {
                        "direct": [
                            {"path": "github.com/example/lib", "version": "v1.0.0-alpha"}
                        ]
                    }
                }
            }
        }
        node = Node.from_component_json(data)
        min_versions = {"github.com/example/lib": "1.0.0"}
        
        check = check_min_versions("go", min_versions, node=node)
        
        # Prerelease (1.0.0-alpha) is less than release (1.0.0)
        self.assertEqual(check.status, CheckStatus.FAIL)

    def test_language_exists_but_no_matching_deps_passes(self):
        """Policy should pass when language exists but has no matching dependencies."""
        data = {
            "lang": {
                "go": {
                    "dependencies": {
                        "direct": [
                            {"path": "github.com/other/lib", "version": "v1.0.0"}
                        ]
                    }
                }
            }
        }
        node = Node.from_component_json(data)
        min_versions = {"github.com/example/lib": "1.0.0"}
        
        check = check_min_versions("go", min_versions, node=node)
        
        # No matching deps to check, so should pass
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_language_with_empty_deps_passes(self):
        """Policy should pass when language exists but has empty dependencies."""
        data = {
            "lang": {
                "go": {
                    "dependencies": {
                        "direct": []
                    }
                }
            }
        }
        node = Node.from_component_json(data)
        min_versions = {"github.com/example/lib": "1.0.0"}
        
        check = check_min_versions("go", min_versions, node=node)
        
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_version_without_v_prefix(self):
        """Version without 'v' prefix should be parsed correctly."""
        data = {
            "lang": {
                "java": {
                    "dependencies": {
                        "direct": [
                            {"path": "org.apache.commons:commons-text", "version": "1.10.0"}
                        ]
                    }
                }
            }
        }
        node = Node.from_component_json(data)
        min_versions = {"org.apache.commons:commons-text": "1.9.0"}
        
        check = check_min_versions("java", min_versions, node=node)
        
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_version_without_v_prefix_fails(self):
        """Version without 'v' prefix below minimum should fail."""
        data = {
            "lang": {
                "java": {
                    "dependencies": {
                        "direct": [
                            {"path": "org.apache.commons:commons-text", "version": "1.8.0"}
                        ]
                    }
                }
            }
        }
        node = Node.from_component_json(data)
        min_versions = {"org.apache.commons:commons-text": "1.9.0"}
        
        check = check_min_versions("java", min_versions, node=node)
        
        self.assertEqual(check.status, CheckStatus.FAIL)

    def test_snapshot_version(self):
        """SNAPSHOT versions should be parsed as prerelease (less than release)."""
        data = {
            "lang": {
                "java": {
                    "dependencies": {
                        "direct": [
                            {"path": "com.example:mylib", "version": "2.0.0-SNAPSHOT"}
                        ]
                    }
                }
            }
        }
        node = Node.from_component_json(data)
        min_versions = {"com.example:mylib": "2.0.0"}
        
        check = check_min_versions("java", min_versions, node=node)
        
        # SNAPSHOT (2.0.0-SNAPSHOT) is less than release (2.0.0)
        self.assertEqual(check.status, CheckStatus.FAIL)

    def test_snapshot_version_meets_snapshot_minimum(self):
        """SNAPSHOT version should pass when minimum is also SNAPSHOT."""
        data = {
            "lang": {
                "java": {
                    "dependencies": {
                        "direct": [
                            {"path": "com.example:mylib", "version": "2.0.0-SNAPSHOT"}
                        ]
                    }
                }
            }
        }
        node = Node.from_component_json(data)
        min_versions = {"com.example:mylib": "2.0.0-SNAPSHOT"}
        
        check = check_min_versions("java", min_versions, node=node)
        
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_rc_version(self):
        """Release candidate versions should be parsed as prerelease."""
        data = {
            "lang": {
                "java": {
                    "dependencies": {
                        "direct": [
                            {"path": "com.example:mylib", "version": "1.0.0-rc1"}
                        ]
                    }
                }
            }
        }
        node = Node.from_component_json(data)
        min_versions = {"com.example:mylib": "1.0.0"}
        
        check = check_min_versions("java", min_versions, node=node)
        
        # rc1 (1.0.0-rc1) is less than release (1.0.0)
        self.assertEqual(check.status, CheckStatus.FAIL)

    def test_beta_version(self):
        """Beta versions should be parsed as prerelease."""
        data = {
            "lang": {
                "nodejs": {
                    "dependencies": {
                        "direct": [
                            {"path": "lodash", "version": "5.0.0-beta.2"}
                        ]
                    }
                }
            }
        }
        node = Node.from_component_json(data)
        min_versions = {"lodash": "5.0.0"}
        
        check = check_min_versions("nodejs", min_versions, node=node)
        
        # beta.2 is less than release
        self.assertEqual(check.status, CheckStatus.FAIL)

    def test_mixed_v_prefix_dep_has_v_min_does_not(self):
        """Dependency with v prefix, minimum without v prefix should work."""
        data = {
            "lang": {
                "go": {
                    "dependencies": {
                        "direct": [
                            {"path": "github.com/example/lib", "version": "v1.5.0"}
                        ]
                    }
                }
            }
        }
        node = Node.from_component_json(data)
        min_versions = {"github.com/example/lib": "1.2.0"}
        
        check = check_min_versions("go", min_versions, node=node)
        
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_mixed_v_prefix_dep_no_v_min_has_v(self):
        """Dependency without v prefix, minimum with v prefix should work."""
        data = {
            "lang": {
                "java": {
                    "dependencies": {
                        "direct": [
                            {"path": "com.example:mylib", "version": "1.5.0"}
                        ]
                    }
                }
            }
        }
        node = Node.from_component_json(data)
        min_versions = {"com.example:mylib": "v1.2.0"}
        
        check = check_min_versions("java", min_versions, node=node)
        
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_build_metadata_version(self):
        """Version with build metadata should be parsed correctly."""
        data = {
            "lang": {
                "java": {
                    "dependencies": {
                        "direct": [
                            {"path": "com.example:mylib", "version": "1.0.0+build.123"}
                        ]
                    }
                }
            }
        }
        node = Node.from_component_json(data)
        min_versions = {"com.example:mylib": "1.0.0"}
        
        check = check_min_versions("java", min_versions, node=node)
        
        # Build metadata is ignored in semver comparison, so 1.0.0+build.123 == 1.0.0
        self.assertEqual(check.status, CheckStatus.PASS)


if __name__ == "__main__":
    unittest.main()

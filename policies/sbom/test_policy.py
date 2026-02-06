"""Temporary unit tests for SBOM policy checks."""
import pytest
from lunar_policy.testing import PolicyTestCase


SAMPLE_SBOM_AUTO = {
    "sbom": {
        "auto": {
            "source": {"tool": "syft", "integration": "code", "version": "1.19.0"},
            "cyclonedx": {
                "bomFormat": "CycloneDX",
                "specVersion": "1.5",
                "components": [
                    {
                        "name": "github.com/sirupsen/logrus",
                        "version": "v1.9.3",
                        "licenses": [{"license": {"id": "MIT"}}],
                    },
                    {
                        "name": "github.com/stretchr/testify",
                        "version": "v1.8.4",
                        "licenses": [{"license": {"id": "MIT"}}],
                    },
                ],
            },
        }
    }
}

SAMPLE_SBOM_CICD = {
    "sbom": {
        "cicd": {
            "source": {"tool": "syft", "integration": "ci", "version": "1.19.0"},
            "cyclonedx": {
                "bomFormat": "CycloneDX",
                "specVersion": "1.5",
                "components": [
                    {
                        "name": "express",
                        "version": "4.18.2",
                        "licenses": [{"license": {"id": "MIT"}}],
                    },
                ],
            },
        }
    }
}


class TestSbomExists(PolicyTestCase):
    policy_path = "policies/sbom"
    policy_name = "sbom-exists"

    def test_pass_with_auto_sbom(self):
        self.set_component_json(SAMPLE_SBOM_AUTO)
        self.assert_pass()

    def test_pass_with_cicd_sbom(self):
        self.set_component_json(SAMPLE_SBOM_CICD)
        self.assert_pass()

    def test_fail_no_sbom(self):
        self.set_component_json({})
        self.assert_fail()


class TestHasLicenses(PolicyTestCase):
    policy_path = "policies/sbom"
    policy_name = "has-licenses"

    def test_pass_all_have_licenses(self):
        self.set_component_json(SAMPLE_SBOM_AUTO)
        self.assert_pass()

    def test_fail_low_coverage(self):
        data = {
            "sbom": {
                "auto": {
                    "cyclonedx": {
                        "components": [
                            {"name": "lib-a", "licenses": [{"license": {"id": "MIT"}}]},
                            {"name": "lib-b"},
                            {"name": "lib-c"},
                            {"name": "lib-d"},
                            {"name": "lib-e"},
                        ]
                    }
                }
            }
        }
        self.set_component_json(data)
        self.assert_fail()

    def test_skip_no_sbom(self):
        self.set_component_json({})
        self.assert_skip()


class TestDisallowedLicenses(PolicyTestCase):
    policy_path = "policies/sbom"
    policy_name = "disallowed-licenses"

    def test_pass_no_patterns_configured(self):
        self.set_component_json(SAMPLE_SBOM_AUTO)
        self.assert_pass()

    def test_pass_no_disallowed(self):
        self.set_component_json(SAMPLE_SBOM_AUTO)
        self.set_variable("disallowed_licenses", "GPL.*,AGPL.*")
        self.assert_pass()

    def test_fail_gpl_found(self):
        data = {
            "sbom": {
                "auto": {
                    "cyclonedx": {
                        "components": [
                            {
                                "name": "gpl-lib",
                                "licenses": [{"license": {"id": "GPL-3.0"}}],
                            }
                        ]
                    }
                }
            }
        }
        self.set_component_json(data)
        self.set_variable("disallowed_licenses", "GPL.*,AGPL.*")
        self.assert_fail()

    def test_skip_no_sbom(self):
        self.set_component_json({})
        self.set_variable("disallowed_licenses", "GPL.*")
        self.assert_skip()


class TestMinComponents(PolicyTestCase):
    policy_path = "policies/sbom"
    policy_name = "min-components"

    def test_pass_enough_components(self):
        self.set_component_json(SAMPLE_SBOM_AUTO)
        self.assert_pass()

    def test_fail_too_few(self):
        data = {
            "sbom": {
                "auto": {
                    "cyclonedx": {
                        "components": []
                    }
                }
            }
        }
        self.set_component_json(data)
        self.set_variable("min_components", "5")
        self.assert_fail()

    def test_skip_no_sbom(self):
        self.set_component_json({})
        self.assert_skip()


class TestStandardFormat(PolicyTestCase):
    policy_path = "policies/sbom"
    policy_name = "standard-format"

    def test_pass_no_restriction(self):
        self.set_component_json(SAMPLE_SBOM_AUTO)
        self.assert_pass()

    def test_pass_allowed_format(self):
        self.set_component_json(SAMPLE_SBOM_AUTO)
        self.set_variable("allowed_formats", "cyclonedx,spdx")
        self.assert_pass()

    def test_fail_wrong_format(self):
        self.set_component_json(SAMPLE_SBOM_AUTO)
        self.set_variable("allowed_formats", "spdx")
        self.assert_fail()

    def test_skip_no_sbom(self):
        self.set_component_json({})
        self.set_variable("allowed_formats", "cyclonedx")
        self.assert_skip()

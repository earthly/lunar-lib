import unittest
import json
from main import check_latest_tag
from lunar_policy import Node, CheckStatus


class TestCheckLatestTag(unittest.TestCase):
    """Test cases for the check_latest_tag function."""

    def test_no_dockerfile_data(self):
        """Test when no dockerfile.imgs data exists."""
        component_json = {}
        root = Node.from_component_json(component_json)
        
        check = check_latest_tag(root)
        
        # Check should have PENDING status when no dockerfile data exists
        self.assertEqual(check.status, CheckStatus.PENDING)

    def test_explicit_latest_tag_fails(self):
        """Test that explicit 'latest' tag causes failure."""
        component_json = {
            "dockerfile": {
                "images_summary": [
                    {
                        "path": "Dockerfile",
                        "images": ["alpine:latest"]
                    }
                ]
            }
        }
        root = Node.from_component_json(component_json)
        
        check = check_latest_tag(root)
        
        # Verify the check failed because of latest tag
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("uses the 'latest' tag", check.failure_reasons[0])
        self.assertIn("alpine:latest", check.failure_reasons[0])

    def test_implicit_latest_tag_fails(self):
        """Test that implicit 'latest' tag (no tag specified) causes failure."""
        component_json = {
            "dockerfile": {
                "images_summary": [
                    {
                        "path": "Dockerfile",
                        "images": ["ubuntu"]
                    }
                ]
            }
        }
        root = Node.from_component_json(component_json)
        
        check = check_latest_tag(root)
        
        # Verify the check failed because of implicit latest tag
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("uses the 'latest' tag", check.failure_reasons[0])
        self.assertIn("ubuntu", check.failure_reasons[0])

    def test_specific_tag_passes(self):
        """Test that specific version tags pass."""
        component_json = {
            "dockerfile": {
                "images_summary": [
                    {
                        "path": "Dockerfile", 
                        "images": ["alpine:3.14", "node:18-alpine"]
                    }
                ]
            }
        }
        root = Node.from_component_json(component_json)
        
        check = check_latest_tag(root)
        
        # Should pass with specific tags
        self.assertEqual(check.status, CheckStatus.PASS)
        self.assertEqual(len(check.failure_reasons), 0)

    def test_scratch_image_allowed(self):
        """Test that scratch image is allowed (special case)."""
        component_json = {
            "dockerfile": {
                "images_summary": [
                    {
                        "path": "Dockerfile",
                        "images": ["scratch"]
                    }
                ]
            }
        }
        root = Node.from_component_json(component_json)
        
        check = check_latest_tag(root)
        
        # Should pass for scratch image
        self.assertEqual(check.status, CheckStatus.PASS)
        self.assertEqual(len(check.failure_reasons), 0)

    def test_registry_with_latest_tag_fails(self):
        """Test that registry with latest tag fails."""
        component_json = {
            "dockerfile": {
                "images_summary": [
                    {
                        "path": "Dockerfile",
                        "images": ["docker.io/library/alpine:latest"]
                    }
                ]
            }
        }
        root = Node.from_component_json(component_json)
        
        check = check_latest_tag(root)
        
        # Should fail with registry and latest tag
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("uses the 'latest' tag", check.failure_reasons[0])
        self.assertIn("docker.io/library/alpine:latest", check.failure_reasons[0])

    def test_registry_with_specific_tag_passes(self):
        """Test that registry with specific tag passes."""
        component_json = {
            "dockerfile": {
                "images_summary": [
                    {
                        "path": "Dockerfile",
                        "images": ["gcr.io/my-project/my-app:v1.2.3"]
                    }
                ]
            }
        }
        root = Node.from_component_json(component_json)
        
        check = check_latest_tag(root)
        
        # Should pass with specific tag
        self.assertEqual(check.status, CheckStatus.PASS)
        self.assertEqual(len(check.failure_reasons), 0)

    def test_sha_digest_passes(self):
        """Test that SHA digest tags pass."""
        component_json = {
            "dockerfile": {
                "images_summary": [
                    {
                        "path": "Dockerfile",
                        "images": ["alpine@sha256:abcd1234ef567890"]
                    }
                ]
            }
        }
        root = Node.from_component_json(component_json)
        
        check = check_latest_tag(root)
        
        # Should pass with SHA digest
        self.assertEqual(check.status, CheckStatus.PASS)
        self.assertEqual(len(check.failure_reasons), 0)

    def test_multiple_dockerfiles_mixed(self):
        """Test multiple Dockerfiles with mixed tags (some pass, some fail)."""
        component_json = {
            "dockerfile": {
                "images_summary": [
                    {
                        "path": "Dockerfile",
                        "images": ["alpine:3.14", "node:latest"]
                    },
                    {
                        "path": "app/Dockerfile",
                        "images": ["ubuntu:20.04"]
                    }
                ]
            }
        }
        root = Node.from_component_json(component_json)
        
        check = check_latest_tag(root)
        
        # Should fail because one image uses latest
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("node:latest", check.failure_reasons[0])
        self.assertIn("uses the 'latest' tag", check.failure_reasons[0])

    def test_empty_images_list(self):
        """Test when images list is empty."""
        component_json = {
            "dockerfile": {
                "images_summary": [
                    {
                        "path": "Dockerfile",
                        "images": []
                    }
                ]
            }
        }
        root = Node.from_component_json(component_json)
        
        check = check_latest_tag(root)
        
        # Should pass when no images to check
        self.assertEqual(check.status, CheckStatus.PASS)
        self.assertEqual(len(check.failure_reasons), 0)

    def test_complex_image_tags(self):
        """Test complex image tag formats."""
        component_json = {
            "dockerfile": {
                "images_summary": [
                    {
                        "path": "Dockerfile",
                        "images": [
                            "myregistry.azurecr.io/myapp:v2.0-beta",
                            "localhost:5000/myapp:dev",
                            "123456789012.dkr.ecr.us-west-2.amazonaws.com/my-app:prod-1.0"
                        ]
                    }
                ]
            }
        }
        root = Node.from_component_json(component_json)
        
        check = check_latest_tag(root)
        
        # Should pass with specific complex tags
        self.assertEqual(check.status, CheckStatus.PASS)
        self.assertEqual(len(check.failure_reasons), 0)

    def test_whitespace_in_image_tag(self):
        """Test image tags with whitespace."""
        component_json = {
            "dockerfile": {
                "images_summary": [
                    {
                        "path": "Dockerfile",
                        "images": ["  alpine:latest  "]
                    }
                ]
            }
        }
        root = Node.from_component_json(component_json)
        
        check = check_latest_tag(root)
        
        # Should fail even with whitespace around latest tag
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("uses the 'latest' tag", check.failure_reasons[0])
        self.assertIn("alpine:latest", check.failure_reasons[0])

if __name__ == "__main__":
    unittest.main()
import unittest
from parse_image import parse_docker_image_tag


class TestParseDockerImageTag(unittest.TestCase):
    """Test cases for the parse_docker_image_tag function."""

    def test_repository_only(self):
        """Test parsing image with repository name only (implicit latest tag)."""
        registry, repository, tag = parse_docker_image_tag("alpine")
        self.assertIsNone(registry)
        self.assertEqual(repository, "alpine")
        self.assertEqual(tag, "latest")

    def test_repository_with_tag(self):
        """Test parsing image with repository and explicit tag."""
        registry, repository, tag = parse_docker_image_tag("alpine:3.14")
        self.assertIsNone(registry)
        self.assertEqual(repository, "alpine")
        self.assertEqual(tag, "3.14")

    def test_repository_with_latest_tag(self):
        """Test parsing image with repository and explicit latest tag."""
        registry, repository, tag = parse_docker_image_tag("alpine:latest")
        self.assertIsNone(registry)
        self.assertEqual(repository, "alpine")
        self.assertEqual(tag, "latest")

    def test_registry_with_repository_and_tag(self):
        """Test parsing image with registry, repository, and tag."""
        registry, repository, tag = parse_docker_image_tag("foo.com/alpine:latest")
        self.assertEqual(registry, "foo.com")
        self.assertEqual(repository, "alpine")
        self.assertEqual(tag, "latest")

    def test_registry_with_repository_no_tag(self):
        """Test parsing image with registry and repository but no tag."""
        registry, repository, tag = parse_docker_image_tag("foo.com/alpine")
        self.assertEqual(registry, "foo.com")
        self.assertEqual(repository, "alpine")
        self.assertEqual(tag, "latest")

    def test_registry_with_port(self):
        """Test parsing image with registry containing port number."""
        registry, repository, tag = parse_docker_image_tag("localhost:5000/myapp:dev")
        self.assertEqual(registry, "localhost:5000")
        self.assertEqual(repository, "myapp")
        self.assertEqual(tag, "dev")

    def test_localhost_registry(self):
        """Test parsing image with localhost registry."""
        registry, repository, tag = parse_docker_image_tag("localhost/myapp:latest")
        self.assertEqual(registry, "localhost")
        self.assertEqual(repository, "myapp")
        self.assertEqual(tag, "latest")

    def test_docker_hub_registry(self):
        """Test parsing image with explicit docker.io registry."""
        registry, repository, tag = parse_docker_image_tag("docker.io/library/alpine:3.14")
        self.assertEqual(registry, "docker.io")
        self.assertEqual(repository, "library/alpine")
        self.assertEqual(tag, "3.14")

    def test_namespace_repository(self):
        """Test parsing image with namespace/repository format (no registry)."""
        registry, repository, tag = parse_docker_image_tag("mycompany/myapp:v1.0")
        self.assertIsNone(registry)
        self.assertEqual(repository, "mycompany/myapp")
        self.assertEqual(tag, "v1.0")

    def test_deep_namespace_repository(self):
        """Test parsing image with deep namespace/repository format."""
        registry, repository, tag = parse_docker_image_tag("mycompany/team/myapp:v1.0")
        self.assertIsNone(registry)
        self.assertEqual(repository, "mycompany/team/myapp")
        self.assertEqual(tag, "v1.0")

    def test_registry_with_deep_namespace(self):
        """Test parsing image with registry and deep namespace."""
        registry, repository, tag = parse_docker_image_tag("registry.example.com/mycompany/team/myapp:v1.0")
        self.assertEqual(registry, "registry.example.com")
        self.assertEqual(repository, "mycompany/team/myapp")
        self.assertEqual(tag, "v1.0")

    def test_complex_tag_with_colon(self):
        """Test parsing image where tag might contain complex characters."""
        registry, repository, tag = parse_docker_image_tag("alpine:v1.0-beta")
        self.assertIsNone(registry)
        self.assertEqual(repository, "alpine")
        self.assertEqual(tag, "v1.0-beta")

    def test_whitespace_handling(self):
        """Test parsing image with whitespace that should be stripped."""
        registry, repository, tag = parse_docker_image_tag("  alpine:latest  ")
        self.assertIsNone(registry)
        self.assertEqual(repository, "alpine")
        self.assertEqual(tag, "latest")

    def test_gcr_registry(self):
        """Test parsing image from Google Container Registry."""
        registry, repository, tag = parse_docker_image_tag("gcr.io/my-project/my-app:v1.2.3")
        self.assertEqual(registry, "gcr.io")
        self.assertEqual(repository, "my-project/my-app")
        self.assertEqual(tag, "v1.2.3")

    def test_aws_ecr_registry(self):
        """Test parsing image from AWS ECR."""
        registry, repository, tag = parse_docker_image_tag("123456789012.dkr.ecr.us-west-2.amazonaws.com/my-app:latest")
        self.assertEqual(registry, "123456789012.dkr.ecr.us-west-2.amazonaws.com")
        self.assertEqual(repository, "my-app")
        self.assertEqual(tag, "latest")

    def test_azure_registry(self):
        """Test parsing image from Azure Container Registry."""
        registry, repository, tag = parse_docker_image_tag("myregistry.azurecr.io/myapp:v2.0")
        self.assertEqual(registry, "myregistry.azurecr.io")
        self.assertEqual(repository, "myapp")
        self.assertEqual(tag, "v2.0")

    def test_sha_digest_as_tag(self):
        """Test parsing image with SHA digest as tag."""
        registry, repository, tag = parse_docker_image_tag("alpine@sha256:abcd1234")
        self.assertIsNone(registry)
        self.assertEqual(repository, "alpine")
        self.assertEqual(tag, "sha256:abcd1234")

    def test_registry_with_sha_digest(self):
        """Test parsing image with registry and SHA digest."""
        registry, repository, tag = parse_docker_image_tag("foo.com/alpine@sha256:abcd1234")
        self.assertEqual(registry, "foo.com")
        self.assertEqual(repository, "alpine")
        self.assertEqual(tag, "sha256:abcd1234")


if __name__ == "__main__":
    unittest.main()

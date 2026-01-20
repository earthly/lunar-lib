# Category: `.containers`

Container images and Dockerfiles. Tool-agnostic (works with Docker, Podman, Buildah, etc.).

```json
{
  "containers": {
    "definitions": [
      {
        "path": "Dockerfile",
        "valid": true,
        "base_images": [
          {
            "reference": "golang:1.21-alpine",
            "image": "golang",
            "tag": "1.21-alpine"
          },
          {
            "reference": "gcr.io/distroless/static-debian12:nonroot-amd64",
            "image": "gcr.io/distroless/static-debian12",
            "tag": "nonroot-amd64"
          }
        ],
        "final_stage": {
          "base_name": "runtime",
          "base_image": "gcr.io/distroless/static-debian12:nonroot-amd64",
          "user": "nonroot",
          "has_healthcheck": false
        },
        "labels": {
          "org.opencontainers.image.source": "https://github.com/acme/api"
        }
      }
    ],
    "builds": [
      {
        "image": "gcr.io/acme/payment-api:v1.2.3",
        "registry": "gcr.io",
        "tag": "v1.2.3",
        "has_git_sha_label": true,
        "signed": true
      }
    ],
    "registries_used": ["docker.io", "gcr.io"]
  }
}
```

## Key Policy Paths

- `.containers.definitions[].valid` — Dockerfile valid
- `.containers.definitions[].final_stage.user` — User instruction value
- `.containers.definitions[].base_images[].tag` — Tag value (check for `null` or `"latest"`)
- `.containers.builds[].signed` — Image signed
- `.containers.registries_used` — Registries for allowlist checking

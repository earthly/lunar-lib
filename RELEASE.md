# Releasing lunar-lib

## Quick reference

From the repo root, on `main`, with a clean working tree:

```bash
./scripts/release.sh v1.1.0
```

This creates a branch + tag, rewrites all manifests and starter packs to pin the version, pushes to origin, and CI publishes Docker images.

## Full guide

See [`.ai-implementation/releasing.md`](.ai-implementation/releasing.md) for the complete release process including:

- Pre-flight checks and version numbering
- What the release script does internally
- CI workflow and image verification
- GitHub Release creation with categorized release notes
- Post-release notifications and cronos updates
- Troubleshooting common failures

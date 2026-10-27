"""Shared helpers for container policies."""


def parse_image_reference(reference: str) -> tuple[str | None, str, str | None]:
    """
    Parse a Docker image reference into (registry, repository, tag).
    
    Examples:
    - alpine -> (None, alpine, None)
    - alpine:3.18 -> (None, alpine, 3.18)
    - gcr.io/distroless/static:nonroot -> (gcr.io, distroless/static, nonroot)
    - alpine@sha256:abc123 -> (None, alpine, sha256:abc123)
    """
    reference = reference.strip()
    
    # Handle digest format (@sha256:...)
    if '@' in reference:
        image_part, tag = reference.rsplit('@', 1)
    elif ':' in reference:
        # Check if the colon is in a port number (registry:port/repo)
        # or in the tag (repo:tag)
        parts = reference.split('/')
        if ':' in parts[-1]:
            # Tag is in the last part
            last_part = parts[-1]
            repo_name, tag = last_part.rsplit(':', 1)
            parts[-1] = repo_name
            image_part = '/'.join(parts)
        else:
            image_part = reference
            tag = None
    else:
        image_part = reference
        tag = None
    
    # Parse registry from image_part
    parts = image_part.split('/')
    
    if len(parts) == 1:
        # Just repository (e.g., "alpine")
        return None, parts[0], tag
    
    # Check if first part looks like a registry (has dot, colon, or is localhost)
    first_part = parts[0]
    if '.' in first_part or ':' in first_part or first_part == 'localhost':
        return first_part, '/'.join(parts[1:]), tag
    
    # No registry, all parts are namespace/repo
    return None, image_part, tag


def image_digest(reference: str) -> str | None:
    """
    Return the digest an image reference is pinned to, or None.

    Read it from the full reference: the docker collector splits on ":", so its
    tag for "alpine@sha256:<hex>" is just "<hex>".

    Examples:
    - alpine@sha256:abc123 -> sha256:abc123
    - node:20@sha256:abc123 -> sha256:abc123
    - node:20.11.1 -> None
    """
    _, _, tag = parse_image_reference(reference)
    if tag and tag.startswith(("sha256:", "sha512:")):
        return tag
    return None

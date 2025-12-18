
def parse_docker_image_tag(image_tag):
    """
    Parse a Docker image tag into registry, repository, and tag components.
    
    Handles these formats:
    - registry.com/repository:tag -> (registry.com, repository, tag)
    - repository:tag -> (None, repository, tag)
    - repository -> (None, repository, latest)
    - registry.com/namespace/repository:tag -> (registry.com, namespace/repository, tag)
    - repository@sha256:digest -> (None, repository, sha256:digest)
    - registry.com/repository@sha256:digest -> (registry.com, repository, sha256:digest)
    """
    # Remove any whitespace
    image_tag = image_tag.strip()
    
    # Handle SHA digests (using @) vs regular tags (using :)
    if '@' in image_tag:
        # SHA digest format: alpine@sha256:abcd1234
        image_part, tag = image_tag.rsplit('@', 1)
    elif ':' in image_tag:
        # Regular tag format: alpine:latest
        image_part, tag = image_tag.rsplit(':', 1)
    else:
        # No tag specified, default to latest
        image_part = image_tag
        tag = "latest"
    
    # Now parse the image_part to extract registry and repository
    # Registry typically contains a '.' or ':' (for port) or is localhost
    parts = image_part.split('/')
    
    if len(parts) == 1:
        # Just repository name (e.g., "alpine")
        registry = None
        repository = parts[0]
    elif len(parts) >= 2:
        # Check if first part looks like a registry
        first_part = parts[0]
        if ('.' in first_part or ':' in first_part or 
            first_part == 'localhost' or first_part.lower() in ['docker.io']):
            # First part is registry
            registry = first_part
            repository = '/'.join(parts[1:])
        else:
            # No registry, all parts are repository/namespace
            registry = None
            repository = image_part
    
    return registry, repository, tag

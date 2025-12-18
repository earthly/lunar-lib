from lunar_policy import Check, variable_or_default
from parse_image import parse_docker_image_tag

def main():
    check_latest_tag()
    check_labels()
    check_allowed_registries()

def check_latest_tag(node=None):
    c = Check("dockerfile-no-latest", "Dockerfiles should not use the latest tag", node=node)
    with c:
        imgs = c.get_node(".dockerfile.images_summary")
        if not imgs.exists():
            return c
        for img in imgs:
            img_tags = img.get_value(".images")
            path = img.get_value(".path")
            for img_tag in img_tags:
                # Parse the Docker image tag into registry, repository, and tag
                registry, repository, tag = parse_docker_image_tag(img_tag)
                
                # Allow scratch image (special case - no versioning available)
                if repository == "scratch":
                    continue
                
                # Check if the tag is 'latest' (either explicitly or implicitly)
                if tag == "latest":
                    c.fail(f"Dockerfile '{path}' uses the 'latest' tag when referencing base image '{img_tag}'")
    return c

def check_labels(node=None):
    c = Check("dockerfile-labels", "Dockerfiles should have required labels", node=node)
    with c:
        dockerfiles_with_labels = c.get_node(".dockerfile.labels_summary")
        if not dockerfiles_with_labels.exists():
            return c
        
        # Get required labels from configuration
        required_labels_str = variable_or_default("requiredLabels", "")
        required_labels = [label.strip() for label in required_labels_str.split(",") if label.strip()]
        if not required_labels:
            return c

        for dockerfile_data in dockerfiles_with_labels:
            stages = dockerfile_data.get_node(".stages")
            path = dockerfile_data.get_value(".path")
            for stage_idx, stage in enumerate(stages):
                labels = stage.get_value(".labels")
                if not labels:
                    labels = {}
                base_name = stage.get_value(".base_name")
                
                missing_labels = []
                for required_label in required_labels:
                    if required_label not in labels:
                        missing_labels.append(required_label)
                        
                if missing_labels:
                    c.fail(f"Dockerfile '{path}' stage {stage_idx} (base: {base_name}) is missing required labels: {', '.join(missing_labels)}")
                else:
                    print(f"✓ Dockerfile '{path}' stage {stage_idx} (base: {base_name}) has all required labels")
    return c

def check_allowed_registries(node=None):
    c = Check("dockerfile-allowed-registries", "Dockerfiles should only use images from allowed registries", node=node)
    with c:
        imgs = c.get_node(".dockerfile.images_summary")
        if not imgs.exists():
            return c
        
        # Get allowed registries from configuration
        allowed_registries_str = variable_or_default("allowedRegistries", "docker.io")
        allowed_registries = [registry.strip() for registry in allowed_registries_str.split(",") if registry.strip()]
        
        for img in imgs:
            img_tags = img.get_value(".images")
            path = img.get_value(".path")
            for img_tag in img_tags:
                # Parse the Docker image tag into registry, repository, and tag
                registry, repository, tag = parse_docker_image_tag(img_tag)
                
                # Allow scratch image (special case - no registry)
                if repository == "scratch":
                    continue
                
                # If no registry is specified, default to docker.io (Docker Hub)
                if registry is None:
                    registry = "docker.io"

                # Check if the registry is in the allowed list
                if registry not in allowed_registries:
                    c.fail(f"Dockerfile '{path}' uses image '{img_tag}' from registry '{registry}' which is not in the allowed registries: {', '.join(allowed_registries)}")
                else:
                    print(f"✓ Dockerfile '{path}' image '{img_tag}' uses allowed registry '{registry}'")
    return c

if __name__ == "__main__":
    main()

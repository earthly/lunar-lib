"""Check that container definitions use allowed registries."""

from lunar_policy import Check, variable_or_default
from helpers import parse_image_reference


def main():
    with Check("allowed-registries", "Container definitions should use allowed registries") as c:
        allowed_str = variable_or_default("allowed_registries", "docker.io")
        allowed = [r.strip() for r in allowed_str.split(",") if r.strip()]
        
        if not allowed:
            raise ValueError(
                "Policy misconfiguration: 'allowed_registries' is empty. "
                "An allow-list must contain at least one entry. "
                "Configure allowed registries or exclude this check."
            )
        
        definitions = c.get_node(".containers.definitions")
        if not definitions.exists():
            return
        
        for definition in definitions:
            if not definition.get_value_or_default(".valid", False):
                continue
            
            path = definition.get_value(".path")
            base_images = definition.get_node(".base_images")
            
            if not base_images.exists():
                continue
            
            for img in base_images:
                reference = img.get_value(".reference")
                image = img.get_value_or_default(".image", reference)
                
                # Skip scratch image
                if image == "scratch":
                    continue
                
                # Parse to get registry
                registry, _, _ = parse_image_reference(reference)
                
                # Default to docker.io if no registry specified
                if registry is None:
                    registry = "docker.io"
                
                if registry not in allowed:
                    c.fail(
                        f"'{path}' uses image '{reference}' from registry '{registry}' "
                        f"which is not in allowed registries: {', '.join(allowed)}"
                    )


if __name__ == "__main__":
    main()

"""Check that container definitions use stable tags."""

import re
from lunar_policy import Check


def main():
    with Check("stable-tags", "Container definitions should use stable tags") as c:
        definitions = c.get_node(".containers.definitions")
        if not definitions.exists():
            return
        
        # Pattern for full semantic version (major.minor.patch with optional suffix)
        semver_pattern = r'^v?\d+\.\d+\.\d+(-[a-zA-Z0-9._-]+)?$'
        
        for definition in definitions:
            if not definition.get_value_or_default(".valid", False):
                continue
            
            path = definition.get_value(".path")
            base_images = definition.get_node(".base_images")
            
            if not base_images.exists():
                continue
            
            for img in base_images:
                reference = img.get_value(".reference")
                tag = img.get_value_or_default(".tag", None)
                image = img.get_value_or_default(".image", reference)
                
                # Skip scratch image
                if image == "scratch":
                    continue
                
                # No tag means implicit :latest (unstable)
                if tag is None:
                    c.fail(f"'{path}' uses implicit :latest tag for '{reference}' (unstable)")
                    continue
                
                # Digests are stable
                if tag.startswith("sha256:") or tag.startswith("sha512:"):
                    continue
                
                # Full semantic versions are stable
                if re.match(semver_pattern, tag):
                    continue
                
                # Everything else is unstable
                c.fail(
                    f"'{path}' uses unstable tag '{tag}' in '{reference}'. "
                    f"Use a digest (@sha256:...) or full semantic version (e.g., :1.2.3)"
                )


if __name__ == "__main__":
    main()

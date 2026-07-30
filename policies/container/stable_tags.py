"""Check that container definitions use stable tags."""

import re
from lunar_policy import Check


def main():
    with Check("stable-tags", "Container definitions should use stable tags") as c:
        definitions = c.get_node(".containers.definitions")
        if not definitions.exists():
            return
        
        # A tag is stable if it *contains* a full semantic version
        # (major.minor.patch) anywhere in the tag. This accepts registry- or
        # vendor-specific prefixes and suffixes (e.g. "v4-bpl-3.24.0",
        # "9.6.1-jdk25-alpine", "26.0.1_8-jre-alpine"), while partial versions
        # like "20" or "16.1" — which can still move — are rejected.
        semver_pattern = r'\d+\.\d+\.\d+'
        
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
                
                # Tags containing a full semantic version are stable
                if re.search(semver_pattern, tag):
                    continue
                
                # Everything else is unstable
                c.fail(
                    f"'{path}' uses unstable tag '{tag}' in '{reference}'. "
                    f"Use a digest (@sha256:...) or a tag containing a full "
                    f"semantic version (e.g., :1.2.3)"
                )


if __name__ == "__main__":
    main()

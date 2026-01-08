"""Check that container definitions don't use the :latest tag."""

from lunar_policy import Check


def main():
    with Check("no-latest", "Container definitions should not use the :latest tag") as c:
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
                tag = img.get_value_or_default(".tag", None)
                image = img.get_value_or_default(".image", reference)
                
                # Skip scratch image
                if image == "scratch":
                    continue
                
                # No tag means implicit :latest
                if tag is None:
                    c.fail(f"'{path}' uses implicit :latest tag for image '{reference}'")
                elif tag == "latest":
                    c.fail(f"'{path}' uses explicit :latest tag for image '{reference}'")


if __name__ == "__main__":
    main()

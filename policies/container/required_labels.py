"""Check that container definitions have required labels."""

from lunar_policy import Check, variable_or_default


def main():
    with Check("required-labels", "Container definitions should have required labels") as c:
        required_str = variable_or_default("required_labels", "")
        required = [l.strip() for l in required_str.split(",") if l.strip()]
        
        if not required:
            return
        
        definitions = c.get_node(".containers.definitions")
        if not definitions.exists():
            return
        
        for definition in definitions:
            if not definition.get_value_or_default(".valid", False):
                continue
            
            path = definition.get_value(".path")
            labels = definition.get_value_or_default(".labels", {})
            
            missing = [l for l in required if l not in labels]
            
            if missing:
                c.fail(f"'{path}' is missing required labels: {', '.join(missing)}")


if __name__ == "__main__":
    main()

"""Check that container definitions specify USER instruction."""

from lunar_policy import Check


def main(node=None):
    c = Check("user", "Container definitions should specify USER", node=node)
    with c:
        definitions = c.get_node(".containers.definitions")
        if not definitions.exists():
            return c
        
        for definition in definitions:
            if not definition.get_value_or_default(".valid", False):
                continue
            
            path = definition.get_value(".path")
            user = definition.get_value_or_default(".final_stage.user", None)
            
            if user is None:
                c.fail(f"'{path}' is missing USER instruction in final stage")
    
    return c


if __name__ == "__main__":
    main()

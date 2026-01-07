"""Check that container definitions have HEALTHCHECK instruction."""

from lunar_policy import Check


def main(node=None):
    c = Check("healthcheck", "Container definitions should have HEALTHCHECK", node=node)
    with c:
        definitions = c.get_node(".containers.definitions")
        if not definitions.exists():
            return c
        
        for definition in definitions:
            if not definition.get_value_or_default(".valid", False):
                continue
            
            path = definition.get_value(".path")
            has_healthcheck = definition.get_value_or_default(".final_stage.has_healthcheck", False)
            
            if not has_healthcheck:
                c.fail(f"'{path}' is missing HEALTHCHECK instruction in final stage")
    
    return c


if __name__ == "__main__":
    main()

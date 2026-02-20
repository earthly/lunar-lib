"""Validate all IaC configuration files are syntactically correct."""

from lunar_policy import Check


def main(node=None):
    c = Check("valid", "IaC configuration files are valid", node=node)
    with c:
        files = c.get_node(".iac.files")
        if not files.exists():
            c.skip("No IaC files found")

        for f in files:
            if not f.get_value_or_default(".valid", True):
                path = f.get_value_or_default(".path", "unknown")
                error = f.get_value_or_default(".error", "syntax error")
                c.fail(f"{path}: {error}")
    return c


if __name__ == "__main__":
    main()

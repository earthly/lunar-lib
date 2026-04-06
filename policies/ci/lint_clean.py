from lunar_policy import Check


def main(node=None):
    c = Check("lint-clean", "No lint errors across CI configuration files", node=node)
    with c:
        lint_node = c.get_node(".ci.lint")
        if not lint_node.exists():
            c.skip("No CI lint data found — ensure a CI collector is configured")

        error_count_node = lint_node.get_node(".error_count")
        if not error_count_node.exists():
            c.skip("No lint error count available")

        error_count = error_count_node.get_value()

        if error_count > 0:
            # Build detail message from individual errors if available
            errors_node = lint_node.get_node(".errors")
            detail = ""
            if errors_node.exists():
                errors = errors_node.get_value()
                if isinstance(errors, list):
                    samples = errors[:5]
                    details = []
                    for e in samples:
                        f = e.get("file", "?")
                        ln = e.get("line", "?")
                        msg = e.get("message", "?")
                        details.append(f"  {f}:{ln}: {msg}")
                    detail = "\n" + "\n".join(details)
                    if len(errors) > 5:
                        detail += f"\n  ... and {len(errors) - 5} more"

            c.fail(
                f"{error_count} lint error(s) found across CI configuration files{detail}"
            )

    return c


if __name__ == "__main__":
    main()

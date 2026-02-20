from lunar_policy import Check, variable_or_default


def check_max_unsafe_blocks(max_unsafe=None, node=None):
    """Check that unsafe block count is within limits."""
    if max_unsafe is None:
        max_unsafe = int(variable_or_default("max_unsafe_blocks", "0"))
    else:
        max_unsafe = int(max_unsafe)

    c = Check("max-unsafe-blocks", "Ensures unsafe block count is within limits", node=node)
    with c:
        rust = c.get_node(".lang.rust")
        if not rust.exists():
            c.skip("Not a Rust project")

        unsafe_blocks = rust.get_node(".unsafe_blocks")
        if not unsafe_blocks.exists():
            c.skip("Unsafe block data not collected")

        count_node = unsafe_blocks.get_node(".count")
        count = count_node.get_value() if count_node.exists() else 0

        if count > max_unsafe:
            # Build location summary
            loc_summary = ""
            locations = unsafe_blocks.get_node(".locations")
            if locations.exists() and locations.get_value():
                locs = locations.get_value()[:5]
                loc_strs = [f"{l.get('file', '?')}:{l.get('line', '?')}" for l in locs]
                loc_summary = f" Found in: {', '.join(loc_strs)}"
                if count > 5:
                    loc_summary += f" (and {count - 5} more)"

            c.fail(
                f"{count} unsafe blocks found, maximum allowed is {max_unsafe}.{loc_summary} "
                f"Reduce unsafe usage or increase the max_unsafe_blocks threshold."
            )
    return c


if __name__ == "__main__":
    check_max_unsafe_blocks()

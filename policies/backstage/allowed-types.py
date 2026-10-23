from lunar_policy import Check

from allowed_values import check_allowed_value


def main(node=None):
    c = Check(
        "allowed-types",
        "catalog-info.yaml spec.type should be one of the allowed types",
        node=node,
    )
    with c:
        # No other check covers a missing spec.type, so it fails here.
        check_allowed_value(c, "type", "allowed_types")
    return c


if __name__ == "__main__":
    main()

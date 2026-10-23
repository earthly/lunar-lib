from lunar_policy import Check

from allowed_values import check_allowed_value


def main(node=None):
    c = Check(
        "allowed-lifecycles",
        "catalog-info.yaml spec.lifecycle should be one of the allowed lifecycles",
        node=node,
    )
    with c:
        # lifecycle-set fails a missing spec.lifecycle; skip so it's reported once.
        check_allowed_value(
            c, "lifecycle", "allowed_lifecycles", presence_check="lifecycle-set"
        )
    return c


if __name__ == "__main__":
    main()

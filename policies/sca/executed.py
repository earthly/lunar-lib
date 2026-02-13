"""Verify SCA scanning was executed."""

from lunar_policy import Check


def main(node=None):
    c = Check("executed", "SCA scan must be executed", node=node)
    with c:
        c.assert_exists(
            ".sca",
            "No SCA scanning data found. Ensure a scanner (Snyk, Semgrep, etc.) is configured.",
        )
    return c


if __name__ == "__main__":
    main()

"""Verify SAST scanning was executed."""

from lunar_policy import Check


def main(node=None):
    c = Check("executed", "SAST scan must be executed", node=node)
    with c:
        c.assert_exists(
            ".sast",
            "No SAST scanning data found. Ensure a scanner (Semgrep, CodeQL, etc.) is configured.",
        )
    return c


if __name__ == "__main__":
    main()

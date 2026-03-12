"""Verify secret scanning was executed."""

from lunar_policy import Check


def main(node=None):
    c = Check("executed", "Secret scan must be executed", node=node)
    with c:
        c.assert_exists(
            ".secrets",
            "No secret scanning data found. Ensure a scanner (Gitleaks, TruffleHog, etc.) is configured.",
        )
    return c


if __name__ == "__main__":
    main()

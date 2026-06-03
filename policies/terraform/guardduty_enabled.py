"""Require Amazon GuardDuty to be enabled."""

from lunar_policy import Check
from helpers import iter_resources, truthy


def main(node=None):
    c = Check("guardduty-enabled", "GuardDuty detector is enabled", node=node)
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        detectors = list(iter_resources(native, "aws_guardduty_detector"))
        if not detectors:
            # Account-scoped control: absence IS the violation. Apply this check
            # to the component that owns the account baseline.
            c.fail(
                "No aws_guardduty_detector found. Enable GuardDuty for continuous "
                "threat detection."
            )
            return c

        # `enable` defaults to true when omitted.
        if not any(truthy(cfg.get("enable", True)) for _, _, cfg in detectors):
            c.fail("Every aws_guardduty_detector has enable = false. Set enable = true.")
    return c


if __name__ == "__main__":
    main()

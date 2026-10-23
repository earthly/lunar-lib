"""Require OpenTofu state encryption to be configured and enforced.

State holds every resource attribute in plaintext, including generated
secrets, so an unencrypted state file is a credential store. OpenTofu's
`encryption` block is the only in-band fix; `enforced = true` is what stops it
silently falling back to plaintext when a key provider is unavailable.
"""

from lunar_policy import Check
from helpers import as_blocks, truthy


def _terraform_blocks(native):
    for f in native:
        hcl = f.get_node(".hcl")
        if not hcl.exists():
            continue
        raw = hcl.get_value()
        if not isinstance(raw, dict):
            continue
        for tf in as_blocks(raw.get("terraform")):
            yield tf


def main(node=None):
    c = Check(
        "opentofu-state-encryption",
        "OpenTofu state encryption is configured and enforced",
        node=node,
    )
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        encryption = []
        saw_terraform_block = False
        for tf in _terraform_blocks(native):
            saw_terraform_block = True
            encryption.extend(as_blocks(tf.get("encryption")))

        if not saw_terraform_block:
            # No terraform {} block at all — nothing says this is OpenTofu.
            c.skip("No Terraform configuration block found")

        if not encryption:
            # Literal braces, so string concatenation rather than .format().
            c.fail(
                "No terraform { encryption { ... } } block. OpenTofu state "
                "holds every resource attribute in plaintext, including "
                "secrets - configure a key provider and a state method."
            )

        problems = []
        for enc in encryption:
            if not as_blocks(enc.get("key_provider")):
                problems.append("no key_provider")
            states = as_blocks(enc.get("state"))
            if not states:
                problems.append("no state block")
                continue
            for state in states:
                if not state.get("method"):
                    problems.append("state has no method")
                if not truthy(state.get("enforced", False)):
                    problems.append("state.enforced is not true")

        if problems:
            c.fail(
                "OpenTofu state encryption is incomplete: {}. Without "
                "enforced = true it falls back to plaintext rather than "
                "failing.".format(", ".join(sorted(set(problems))))
            )
    return c


if __name__ == "__main__":
    main()

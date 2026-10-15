"""Shared logic for the allowed-types and allowed-lifecycles checks."""

from lunar_policy import variable_or_default

from catalog_presence import skip_if_no_catalog


def check_allowed_value(c, field, input_name, presence_check=None):
    """Fail `c` unless `spec.<field>` is one of the values in `input_name`.

    Matching is exact and case-sensitive. A missing value fails, unless
    `presence_check` names a check that already reports it; then this skips,
    so a missing field is reported once.
    """
    raw = variable_or_default(input_name, "")
    allowed = list(dict.fromkeys(v.strip() for v in raw.split(",") if v.strip()))
    if not allowed:
        # Opt-in check: with nothing configured there is nothing to enforce.
        c.skip(
            f"No {input_name} configured. Set the `{input_name}` input to "
            f"restrict spec.{field} to a list of values."
        )

    skip_if_no_catalog(c)

    noun = input_name.replace("_", " ")
    listing = ", ".join(allowed)
    if not c.exists(".catalog.native.backstage"):
        c.fail(
            f"No catalog-info.yaml found, so spec.{field} cannot be verified. "
            f"Add a catalog-info.yaml whose spec.{field} is one of the {noun}: "
            f"{listing}."
        )
        return

    value = c.get_value_or_default(f".catalog.native.backstage.spec.{field}", "")
    if not isinstance(value, str) or not value.strip():
        if presence_check:
            c.skip(
                f"spec.{field} is not set, so there is no value to check; "
                f"`{presence_check}` reports a missing spec.{field}."
            )
        c.fail(
            f"spec.{field} is not set in catalog-info.yaml. Set it to one of "
            f"the {noun}: {listing}."
        )
        return

    if value.strip() not in allowed:
        c.fail(
            f"catalog-info.yaml spec.{field} '{value.strip()}' is not one of "
            f"the {noun}: {listing}."
        )

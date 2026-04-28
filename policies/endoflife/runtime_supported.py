from lunar_policy import Check


def _format_failure(lang, eol):
    product = eol.get("product", lang)
    cycle = eol.get("cycle", "?")
    detected = eol.get("detected_version", cycle)
    support_until = eol.get("support_until")
    eol_date = eol.get("eol_date")
    is_eol = bool(eol.get("is_eol"))

    if support_until and not is_eol:
        return (
            f"{lang} cycle {cycle} (detected {detected}) is out of active "
            f"support since {support_until} (security-only maintenance "
            f"until {eol_date or 'EOL'}). Bump to a still-supported cycle "
            f"(see https://endoflife.date/{product})."
        )

    if is_eol and eol_date and not support_until:
        # Products with no separate support phase (e.g. Go) — the only
        # date the user has is eol_date, and "out of support" coincides
        # with EOL.
        product_label = (product or lang).capitalize()
        return (
            f"{lang} cycle {cycle} (detected {detected}) is out of active "
            f"support and reached end-of-life on {eol_date} "
            f"({product_label} has no separate active-support phase). "
            f"Bump to a still-supported cycle "
            f"(see https://endoflife.date/{product})."
        )

    return (
        f"{lang} cycle {cycle} (detected {detected}) is out of active support. "
        f"Bump to a still-supported cycle (see https://endoflife.date/{product})."
    )


def main(node=None):
    c = Check(
        "runtime-supported",
        "All detected runtimes are still in active (non-security-only) support",
        node=node,
    )
    with c:
        lang_node = c.get_node(".lang")
        if not lang_node.exists():
            c.skip("No language data present for this component")

        lang_data = lang_node.get_value()
        if not isinstance(lang_data, dict):
            c.skip("Unexpected .lang shape")

        eol_entries = []
        for lang, sub in lang_data.items():
            if not isinstance(sub, dict):
                continue
            eol = sub.get("eol")
            if isinstance(eol, dict):
                eol_entries.append((lang, eol))

        if not eol_entries:
            c.skip(
                "No runtime EOL data present (endoflife collector did not run, "
                "or no detectable runtime pin)"
            )

        failures = [
            _format_failure(lang, eol)
            for lang, eol in eol_entries
            if not eol.get("is_supported", True)
        ]

        if failures:
            c.fail(" ".join(failures))

    return c


if __name__ == "__main__":
    main()

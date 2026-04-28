from lunar_policy import Check


def main(node=None):
    c = Check(
        "runtime-not-eol",
        "No detected runtime is past its end-of-life date",
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

        failures = []
        for lang, eol in eol_entries:
            if not eol.get("is_eol"):
                continue
            product = eol.get("product", lang)
            cycle = eol.get("cycle", "?")
            detected = eol.get("detected_version", cycle)
            eol_date = eol.get("eol_date") or "an unknown date"
            failures.append(
                f"{lang} cycle {cycle} (detected {detected}) reached "
                f"end-of-life on {eol_date}. Move to a supported cycle "
                f"(current latest: see https://endoflife.date/{product})."
            )

        if failures:
            c.fail(" ".join(failures))

    return c


if __name__ == "__main__":
    main()

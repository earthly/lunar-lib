from lunar_policy import Check


def main(node=None):
    c = Check("config-exists", "CodeRabbit configuration file should exist", node=node)
    with c:
        coderabbit = c.get_node(".ai.native.coderabbit")
        coderabbit_data = coderabbit.get_value_or_default(".", None)
        if coderabbit_data is None:
            c.skip("No CodeRabbit data found — enable the coderabbit collector")
            return c

        config_exists = coderabbit.get_value_or_default(".config_exists", False)
        c.assert_true(
            config_exists,
            "No CodeRabbit configuration file found (.coderabbit.yaml or .coderabbit.yml). "
            "A config file lets you customize review behavior, set path filters, and add review instructions."
        )
    return c


if __name__ == "__main__":
    main()

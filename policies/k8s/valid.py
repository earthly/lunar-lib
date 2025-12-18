from lunar_policy import Check

def check_valid(data=None):
    with Check("k8s-valid-config", "Valid k8s Config") as c:
        descriptors = c.get_node(".k8s.descriptors")
        if not descriptors.exists():
            return 
        for desc in descriptors:
            fname = desc.get_value_or_default(".k8s_file_location", "<file>")
            valid = desc.get_value_or_default(".valid", False)
            validation_error = desc.get_value_or_default(".validation_error", "<unknown>")
            c.assert_true(
                valid,
                f"{fname}: validation failed: {validation_error}")

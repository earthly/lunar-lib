from lunar_policy import Check

def check_valid(data=None):
    with Check("terraform-valid", "Terraform configuration is valid") as c:
        files_node = c.get_node(".terraform.files")
        if files_node.exists():
            for file in files_node:
                if not file.get_value_or_default('.valid', False):
                    file_location = file.get_value_or_default('.terraform_file_location', 'unknown')
                    error = file.get_value_or_default('.error', 'Unknown error')
                    c.fail(f"Terraform file {file_location} is invalid: {error}")

def check_has_waf(data=None):
    with Check("terraform-has-waf", "Services deployed to the internet should have WAF protection") as c:
        tf = c.get_node(".terraform")
        internet_acc = tf.get_value_or_default(".is_internet_accessible", False)
        if internet_acc:
            waf = tf.get_value_or_default(".has_waf_protection", False)
            c.assert_true(waf, "Service is internet accessible with no WAF protection")

def check_has_datastore_protection(data=None):
    with Check("terraform-has-delete-protection", "Terraform services with datastores should have delete protection") as c:
        tf = c.get_node(".terraform")
        if tf.get_value_or_default(".has_datastores", False):
            if not tf.get_value_or_default(".has_datastore_protection", False):
                unprotected = tf.get_value(".unprotected_datastores")
                c.fail(f"Service has datastores without delete protection: {unprotected}. " +
                    "Add 'lifecycle.prevent_destroy = true' to these resources to prevent accidental deletion.")

def main():
    check_valid()
    check_has_waf()
    check_has_datastore_protection()

if __name__ == "__main__":
    main()
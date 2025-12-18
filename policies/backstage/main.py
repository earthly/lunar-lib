from lunar_policy import Check

def main():
    check_catalog_exists()
    check_catalogs_valid()

def check_catalog_exists():
    with Check("backstage-catalog-info-exists", "Backstage Config Exists") as c:
        cats = c.get_node(".backstage.catalogs")
        if cats.exists():
            c.assert_greater(len(cats.get_value()), 0, "No Backstage catalog found")

def check_catalogs_valid():
    with Check("backstage-catalog-info-valid", "Backstage Config is Valid") as c:
        cats = c.get_node(".backstage.catalogs")
        if cats.exists():
            for cat in cats:
                is_valid = bool(cat.get_value_or_default(".valid", False))
                if not is_valid:
                    loc = cat.get_value_or_default(".catalog_location", "<unknown>")
                    err = cat.get_value_or_default(".validation_error", "Invalid catalog")
                    c.assert_true(is_valid, f"Backstage catalog {loc} is invalid: {err}")

if __name__ == "__main__":
    main()

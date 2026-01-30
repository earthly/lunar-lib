from lunar_policy import Check


def main(node=None):
    c = Check("require-private", "Repository must be private", node=node)
    with c:
        c.assert_exists(".vcs.visibility", 
            "VCS data not found. Ensure the github collector is configured and has run.")
        
        visibility = c.get_value(".vcs.visibility")
        c.assert_equals(visibility, "private", f"Repository visibility is '{visibility}', but policy requires 'private'")
    return c


if __name__ == "__main__":
    main()

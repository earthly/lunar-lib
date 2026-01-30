from lunar_policy import Check


def main():
    with Check("require-private", "Repository must be private") as c:
        c.assert_exists(".vcs.visibility", 
            "VCS data not found. Ensure the github collector is configured and has run.")
        
        visibility = c.get_value(".vcs.visibility")
        c.assert_equal(visibility, "private", f"Repository visibility is '{visibility}', but policy requires 'private'")


if __name__ == "__main__":
    main()

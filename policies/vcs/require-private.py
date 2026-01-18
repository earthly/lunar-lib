from lunar_policy import Check


def main():
    with Check("require-private", "Repository must be private") as c:
        vcs = c.get_node(".vcs")

        if not vcs.exists():
            c.skip("No VCS data collected")

        visibility = vcs.get_value_or_default(".visibility", None)
        if visibility and visibility != "private":
            c.fail(f"Repository visibility is '{visibility}', but policy requires 'private'")


if __name__ == "__main__":
    main()

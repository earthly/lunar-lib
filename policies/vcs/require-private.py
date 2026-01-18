from lunar_policy import Check


def main():
    with Check("require-private", "Repository must be private") as c:
        visibility = c.get_value(".vcs.visibility")
        if visibility != "private":
            c.fail(f"Repository visibility is '{visibility}', but policy requires 'private'")


if __name__ == "__main__":
    main()

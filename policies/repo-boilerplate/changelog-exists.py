from lunar_policy import Check

with Check("changelog-exists", "Repository should have a CHANGELOG file") as c:
    node = c.get_node(".repo.changelog.exists")
    c.assert_true(
        node.exists() and bool(node.get_value()),
        "No CHANGELOG file found. Add a CHANGELOG.md to record notable changes per release (see https://keepachangelog.com/).",
    )

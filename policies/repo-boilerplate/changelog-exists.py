from lunar_policy import Check

with Check("changelog-exists", "Repository should have a CHANGELOG file") as c:
    c.assert_true(
        c.get_value(".repo.changelog.exists"),
        "No CHANGELOG file found. Add a CHANGELOG.md to record notable changes per release (see https://keepachangelog.com/).",
    )

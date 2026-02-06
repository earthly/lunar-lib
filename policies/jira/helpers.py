"""Shared helpers for Jira policy checks."""

import os


def is_pr_context():
    """Return True if running in a PR context."""
    return bool(os.environ.get("LUNAR_COMPONENT_PR", ""))

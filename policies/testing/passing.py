from lunar_policy import Check, variable_or_default


def failed_runs(runs):
    """Describe the failed builds in .testing.runs.

    The `.testing.all_passing` scalar keeps only the last build to finish at a
    commit, so a passing job could overwrite a failing one. `.testing.runs` keeps
    every build. A re-run replaces its own earlier attempt (same run, job and
    step) but never stands in for a different job or step.
    """
    entries = [r for r in runs if isinstance(r, dict)]

    def key(r):
        return (r.get("run_id"), r.get("job"), r.get("step"))

    latest = {}
    for r in entries:
        latest[key(r)] = max(latest.get(key(r), 0), r.get("attempt") or 0)
    failed = set()
    for r in entries:
        if r.get("all_passing") is False and (r.get("attempt") or 0) == latest[key(r)]:
            where = " / ".join(str(p) for p in (r.get("pipeline"), r.get("job")) if p) or "CI"
            failed.add(f"{where} ({r.get('failed', '?')} of {r.get('total', '?')} failed)")
    return sorted(failed)


def check_passing(node=None):
    """Check that all tests pass.
    
    Args:
        node: Optional Node for testing. If None, loads from environment.
    
    Returns:
        Check object with result.
    """
    c = Check("passing", "Ensures all tests pass", node=node)
    with c:
        # Get required languages from input
        required_langs_str = variable_or_default("required_languages", "")
        required_langs = [lang.strip() for lang in required_langs_str.split(",") if lang.strip()]
        
        # Check if component has a language project
        # Use get_node().exists() to get a boolean without raising NoDataError
        if required_langs:
            # Check for specific languages
            detected_langs = []
            for lang in required_langs:
                if c.get_node(f".lang.{lang}").exists():
                    detected_langs.append(lang)
            
            if not detected_langs:
                c.skip(f"No project detected for required languages: {', '.join(required_langs)}")
        else:
            # No specific languages required - check if ANY language project exists
            if not c.get_node(".lang").exists():
                c.skip("No language project detected")
        
        # Use exists() to check for test pass/fail data:
        # - Before collectors finish: exists() raises NoDataError -> pending
        # - After collectors finish, no data: exists() returns False -> fail
        # - After collectors finish, has data: exists() returns True -> use real value
        runs = c.get_node(".testing.runs")
        all_passing = c.get_node(".testing.all_passing")
        if runs.exists() and isinstance(runs.get_value(), list):
            failed = failed_runs(runs.get_value())
            c.assert_true(
                not failed,
                f"Tests are failing in {'; '.join(failed)}. Check CI logs for test failure details."
            )
        elif all_passing.exists():
            c.assert_true(
                all_passing.get_value(),
                "Tests are failing. Check CI logs for test failure details."
            )
        else:
            c.fail("Test pass/fail data not available. Configure your test runner to report results.")
    return c


if __name__ == "__main__":
    check_passing()

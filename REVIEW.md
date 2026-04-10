# Code Review Guidelines

## Always check
- Shell scripts use Alpine/BusyBox-compatible commands (no GNU grep `-P`, no gawk)
- Policy checks call `exists()` before `get_value()` on Component JSON nodes
- No dead code after `c.skip()` (it raises SkippedError, so `return c` after it is unreachable)
- Collectors write nothing when no data is found (no empty arrays or placeholder objects)
- CI collectors avoid dependencies like `jq` or `python` that may not exist on user runners

## Skip
- Files under `ai-context/` (documentation only)
- Files under `.ai-implementation/` (agent playbooks)
- Files under `test-results/` (test evidence screenshots)

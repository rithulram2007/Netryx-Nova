# Feature Task Specification Template

Use this template for every new work item. Copy to `docs/4-features/<feature>/tasks/task-NNN-name.md`.

```markdown
# Task NNN: <Short Title>

## Target Files

- `path/to/target.py` (new/modified)
- `tests/test_target.py` (new)

## Description

<2-3 sentence description of what this task accomplishes and why it matters.>

## Dependencies

- Task MMM: <prerequisite>
- Requires: <library, model file, API key>

## Checklist

- [ ] <Step 1>
- [ ] <Step 2>
- [ ] <Step 3>
- [ ] Error handling for <edge case>
- [ ] Logging for <key operation>

## Verification

```bash
<pytest or manual verification command>
```

## Notes

<Any gotchas, design decisions, or references to existing code.>
```

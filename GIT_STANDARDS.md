# GIT STANDARDS — Commit Rules & PR Guidelines

## Branch Strategy

- `main` — production-ready, reviewed code only.
- `feat/<name>` — new features (e.g., `feat/faiss-engine`, `feat/web-ui`).
- `fix/<name>` — bug fixes.
- `refactor/<name>` — code restructuring without behavior change.
- `docs/<name>` — documentation-only changes.

## Commit Message Format (Conventional Commits)

```
<type>(<scope>): <description>

[optional body]
[optional footer]
```

### Types

| Type | Usage |
|---|---|
| `feat` | New feature implementation |
| `fix` | Bug fix |
| `refactor` | Code restructuring (no behavior change) |
| `perf` | Performance improvement |
| `docs` | Documentation changes |
| `test` | Adding or modifying tests |
| `chore` | Build, CI, dependencies |
| `revert` | Reverting a previous commit |

### Scopes (current project)

`retrieval`, `matching`, `consensus`, `engine`, `pipeline`, `web-ui`, `loader`, `tile`, `config`, `ci`, `docs`, `frontend`

### Examples

```
feat(retrieval): add on-the-fly FAISS IndexFlatIP builder
fix(matching): handle MPS non-contiguous tensor in MASt3R crop
refactor(engine): abstract engine selection behind EngineBase class
docs(loader): document .netryx bundle schema
```

## PR Guidelines

1. PR title must match commit message format.
2. Include a summary of changes and testing evidence in the PR body.
3. Every PR must pass lint (`ruff`), type check (`mypy`), and unit tests (`pytest`).
4. Squash merge preferred for feature branches.
5. No force-push to `main`.

## Pre-Commit Checklist

- [ ] Code follows CODING_STANDARDS.md conventions
- [ ] Type annotations on all public functions
- [ ] No print/debug statements (use proper logging)
- [ ] Updated docs if API or behavior changed
- [ ] `pytest` passes
- [ ] `ruff check .` passes
- [ ] PROGRESS.md updated if this is the final commit of a session

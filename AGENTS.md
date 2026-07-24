# AGENTS.md — AI Execution Rules & Document Router

You are an AI engineering agent working on **Netryx Astra V2 (Refactored / Hybrid Edition)** — an open-source image geolocation system.

## Core Rules

1. Read this file first on every session start.
2. Consult the **Document Router Table** below to locate the correct context file for your task.
3. Never write code that is not specified in the PRD or an active feature task.
4. Always verify your work: run lint, type checks, and the specific test command for the module you edited.
5. Update `docs/PROGRESS.md` at the end of every session with status changes and blockers.
6. Follow `AI_GLOBAL_RULES.md` constitutional laws for engineering decisions, style, and anti-patterns.

## Document Router Table

| If your task involves... | Read this file first |
|---|---|
| Project overview, system flow, executive summary | `PROJECT_OVERVIEW.md` |
| Tech stack, coding conventions, patterns | `CODING_STANDARDS.md` |
| Git commit rules, PR guidelines | `GIT_STANDARDS.md` |
| Implementation sequence, batch ordering | `docs/ROADMAP.md` |
| Session state, blockers, progress log | `docs/PROGRESS.md` |
| Component architecture, system diagrams | `docs/1-architecture/system-design.md` |
| Database schemas, .netryx bundle format, FAISS index structure | `docs/1-architecture/database-schema.md` |
| Architecture Decision Records (why a choice was made) | `docs/2-decisions/ADR-*.md` |
| API endpoints, request/response contracts | `docs/3-api/api-spec-template.md` |
| Pipeline orchestration, job model, async execution | `docs/4-features/02-pipeline-controller/OVERVIEW.md` |
| Feature-specific business logic | `docs/4-features/<feature>/OVERVIEW.md` |
| Granular task specs with checklists | `docs/4-features/<feature>/tasks/task-*.md` |
| Task template for new work items | `docs/templates/feature-task-spec.md` |

## Session Lifecycle

1. **Start**: Read AGENTS.md router, then load PROJECT_OVERVIEW.md + ROADMAP.md + PROGRESS.md.
2. **Work**: Load the specific context for your task from the router table.
3. **Verify**: Run validation commands specified in the task spec.
4. **Log**: Update PROGRESS.md with what was done and what is blocked.
5. **Commit**: Only when explicitly asked. Use conventional commits matching GIT_STANDARDS.md.

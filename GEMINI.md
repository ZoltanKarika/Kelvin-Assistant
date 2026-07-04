# Kelvin Assistant — Gemini Instructions

You are assisting with the Kelvin Assistant repository.

Always follow these rules:

1. Do not work directly on `main`.
2. Before making changes, run `git status` and explain the current state.
3. Do not rebase, force-push, delete branches, or modify Git history unless explicitly instructed.
4. Prefer small, reviewable changes.
5. Do not mix unrelated changes in one commit.
6. Before editing code, inspect the relevant files first.
7. After changes, summarize:
   - files changed
   - what changed
   - tests/checks run
   - suggested commit message
8. If uncertain, ask before modifying files.

## Quality checks

After every code change, run these commands and ensure they all pass:

```bash
uv run pytest tests/ -q
uv run ruff check backend tests scripts
uv run ruff format --check backend tests scripts
uv run mypy backend/src tests scripts
```

## Imported instruction modules

@./docs/ai/roadmap-status.md
@./docs/ai/task-planning.md
@./docs/ai/git-workflow.md
@./docs/ai/implementation-rules.md
@./docs/ai/pr-review.md
@./docs/ai/v07-guide.md

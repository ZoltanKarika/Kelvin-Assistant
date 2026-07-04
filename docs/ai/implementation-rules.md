# Implementation Rules

Use this file when you are asked to implement a selected task from a todo
list, roadmap, issue, or user request.

The goal is to make one small, safe, reviewable change at a time.

---

## Core Principle

Implement exactly one task at a time.

Do not combine planning, refactoring, cleanup, formatting, dependency
upgrades, and feature work unless the user explicitly asks.

Good:

```text
Implement todo item 1 only.
```

Bad:

```text
Implement todo items 1, 2, and 3, refactor the router, and upgrade FastAPI.
```

---

## Before Starting

1. Run `git status` and confirm a clean working tree.
2. Confirm you are on the correct feature branch (not `main`).
3. Read the relevant source files before editing.

## After Finishing

1. Run the quality checks from `GEMINI.md`.
2. Summarize: files changed, what changed, tests run, suggested commit message.
3. Do not commit unless the user explicitly asks.

# Git Workflow Rules

Use this file whenever you are asked to make code, documentation, configuration, or workflow changes.

The goal is to keep the repository safe, avoid broken rebases, and make every change easy to review.

---

## Golden Rules

1. Never work directly on `main`.
2. Never start a rebase unless the user explicitly asks for it.
3. Never force-push unless the user explicitly asks for it.
4. Never delete branches unless the user explicitly asks for it.
5. Never mix unrelated work in the same branch.
6. Always check Git state before editing files.
7. If Git is in a rebase, merge, cherry-pick, or conflict state, stop and ask the user what to do.

---

## Step 1: Check the current Git state

Before making any change, run:

```bash
git status
git branch --show-current
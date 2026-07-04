# PR Review Mode

Use this mode before opening or merging a pull request.

Goal:

Check whether the branch is safe and understandable.

Review checklist:

- Branch is not `main`.
- Work is based on latest `main`.
- Changes match the intended task.
- No unrelated files are included.
- Tests/checks were run or skipped with reason.
- PR title is clear.
- PR description explains summary, changes, testing, and risks.

Output format:

1. PR title
2. PR description
3. Risk checklist
4. Testing notes
5. Merge readiness

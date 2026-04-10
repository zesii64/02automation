---
name: no-ipynb-git-push
description: Avoid pushing .ipynb files when preparing a git push or pushing to GitHub. Use when the user asks for `git push`, “push to GitHub”, or “提交到GitHub”.
---

# No ipynb on GitHub Push

## Instructions

When preparing to push to GitHub in this repository:

1. Check what is staged for commit:
   - Run `git diff --cached --name-only`
2. If any staged file ends with `.ipynb`:
   - Unstage those files (keep local copies):
     - For each `path.ipynb`, run `git restore --staged "path.ipynb"`
     - If `git restore --staged` is unavailable, use `git reset HEAD -- "path.ipynb"`
3. Re-check staged files (`git diff --cached --name-only`) and ensure no `.ipynb` remains.
4. Proceed with the push only after the `.ipynb` exclusion is satisfied.

## Examples

- User asks: “push to github”
  - The agent ensures `.ipynb` is not part of the staged changes before pushing.


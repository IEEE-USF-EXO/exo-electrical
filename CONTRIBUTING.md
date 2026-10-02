# Contributing

1. `git switch main` and `git pull`.
2. `git switch -c <prefix>/<short-name>`. Prefixes: `feat/`, `fix/`, `docs/`, `test/`.
3. Commit small, specific changes: "Add IMU calibration offsets", not "updates".
4. `git push -u origin <branch>` and open a pull request using the template.
5. One approval from the code owner, then merge and delete the branch.

Undo merged work with `git revert`, never a force push. If a password or key is committed, tell a Project Lead immediately so it can be replaced.

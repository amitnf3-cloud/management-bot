---
name: pre-deploy-check
description: Run before deploying the bot to the server or pushing to the public repo. Reviews the change for bugs and security issues and checks no secret or roster file is staged.
---

# Pre-deploy check

Run these steps in order and report the results to the user in Hebrew, with every command on its own line.

1. **Secrets and personal data.** Run `git status` and `git diff --cached --name-only`. Stop and warn if any of these is staged or tracked: `.env`, `*.db`, `*.csv`, `*.xlsx`, `*.pem`, a real name, a token, a password, a server hostname or IP.
2. **Syntax for Python 3.9.** Run:
   ```
   python -m py_compile bot/*.py db/*.py scripts/*.py cleanup_test_data.py
   ```
   Also search the change for `X | None` type hints and `match` statements, which break on the server's Python 3.9.
3. **Code review.** Use the built-in code-review skill on the current change. Focus on:
   - Every state change writes a `transactions` row and keeps `available = total - issued - missing` correct.
   - Actions that touch several tables commit once, in one connection.
   - Every conversation state accepts the "menu" button.
   - Undo buttons cancel exactly the action they show.
4. **Security review.** Use the built-in security-review skill. Focus on:
   - Permission checks in every handler that changes data (callback data can be forged).
   - SQL uses `%s` placeholders only.
   - Nothing sensitive is sent to the wrong chat.
5. **Deploy steps.** List the exact files that changed and the exact commands to copy them to the server and restart the service, saying which machine each command runs on.

End with a short verdict: ready to deploy, or the list of blockers.

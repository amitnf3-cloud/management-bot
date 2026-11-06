# CLAUDE.md

Guidance for Claude when working in this repository. Full background, decisions and history are in `PROJECT_CONTEXT.md`. Read it at the start of a new session.

## Communication rules (most important)

- **Talk to the user in Hebrew only.** Use masculine forms.
- Do not mix English words inside Hebrew sentences. Mixed right-to-left and left-to-right text renders badly for the user. When a technical term has no good Hebrew word, describe it in Hebrew instead.
- Put every command, file path, code snippet and identifier on its **own line or in a code block**, never inline inside a Hebrew sentence.
- Be short and natural. Do not over-explain.
- Give exact, copy-paste commands and say **where** each one runs: the local machine (PowerShell) or the server (EC2).
- When asked for the full list of commands, give the full list, not a shortened one.
- Be critical: look for edge cases and say plainly when something is a real bug.

## What the project is

A Telegram bot that tracks military equipment signed out in a paratroopers company (about 100 soldiers, 6 platoons). The owner is the company quartermaster. It must answer at any moment: who holds what, what is in the warehouse, and what is missing. It is also a hands-on AWS learning project.

Architecture:

```
Telegram  -->  Bot (Python 3.9, EC2, systemd service "tzanchanim-bot")  -->  PostgreSQL (AWS RDS)
```

## Code map

```
bot/main.py           Telegram conversation: menus, states, buttons, undo
bot/access.py         Permission levels: full, mefaleg, view_only
db/operations.py      All database functions (psycopg2, RealDictCursor)
db/excel_export.py    Excel reports (openpyxl, right-to-left sheets)
db/schema_postgres.sql  Base PostgreSQL schema and seed data
db/schema.sql         Old SQLite schema, history only
scripts/              Roster import and one-time migrations
cleanup_test_data.py  Deletes test data whose names start with "בדיקה"
```

## Rules for changing code

- **Python 3.9 on the server.** Use `typing.Optional` / `typing.Union`, not `str | None`. No `match` statements.
- All SQL uses `%s` placeholders (psycopg2). Never build SQL with f-strings from user input.
- Open a connection per function with `get_conn()` and close it in `finally`. A logical action that changes several tables must commit once, in one connection.
- **History is never deleted.** Every change of holdings writes a row to `transactions`. Soldiers are soft-deleted with `is_active = 0`.
- Warehouse math: `available = total - issued - missing`. Shortages do not return to stock. A battalion return also lowers `total_quantity`.
- For every state change, ask "where does the related data end up?" (example: removing a soldier must return his gear).
- Every new conversation state must accept the "menu" button first, so the user can always escape.
- Check permissions in every handler that changes data, not only in the menu. Callback data can be forged by a modified client.
- New equipment types should be addable by data, without code changes.
- Migrations must be idempotent (safe to run twice) and must not delete existing data.
- Keep `README .md` (note the space in the file name) and sections 6 and 10 of `PROJECT_CONTEXT.md` current when features change.

## Security (the repo is public)

- Never commit tokens, passwords, rosters, real names, `.env`, `*.db`, `*.csv`, `*.xlsx` or `*.pem`.
- Run `git status` before every commit and check that no such file is staged.
- Do not hardcode hostnames, IPs or account details of the real servers.
- Secrets live only in `.env` on the server.

## Deployment

Claude builds and tests. The user deploys to AWS and pushes to GitHub himself, following exact step-by-step commands. Never assume a change is live until the user confirms.

## Checks

There is no test suite yet. Before handing over a change:

```
python -m py_compile bot/*.py db/*.py scripts/*.py cleanup_test_data.py
```

Then think through the full user flow, including undo, the menu button and a view-only user. The project skill `pre-deploy-check` runs a code review and a security review before deploying.

# Project Context – Management Bot

A full summary of how this project was planned, built and deployed, and why each decision was made. Use it as the starting context for new sessions. It has no secrets, no real names and no roster data, so it is safe for a public repo.

## 1. Purpose

Track military equipment sign-out in a paratroopers company (about 100 soldiers, 6 platoons: platoon 1, 2, 3, recon-support, support, and the battalion-liaison platoon).

The owner is the company quartermaster (רס"פ). Before this system, tracking was manual and scattered. The goal is a single source of truth that answers, at any moment:

- Who is signed for what?
- What is in the warehouse?
- What is missing?

A second goal: get real hands-on AWS and cloud experience through a project that does a real job.

## 2. Core requirements (as they evolved)

1. **Speed under pressure.** Sign-out and return must be one or two taps away. Friction is the main enemy.
2. **Three layers of equipment:**
   - Personal gear signed to soldiers (the main layer, fully built).
   - Company gear signed to platoon sergeants (data model exists, UI not built).
   - Battalion layer: what the company is signed for versus the battalion, handled by the battalion-liaison people.
3. **Reports:** platoon report, shortage report, warehouse status.
4. **Excel export** of everything (one sheet per platoon, shortages, battalion inventory).
5. **Shortage reporting** that does not silently return missing items to stock.
6. **Permissions:** very few users (about 4). Levels: full, mefaleg (battalion layer), view-only.
7. **New equipment types must be easy to add** without code changes.
8. **History is kept.** Nothing is deleted; every action is a logged transaction.

## 3. How the decisions were made (thinking process)

- **Start simple, then grow.** The first version was a local bot with SQLite to prove the idea. Only after it worked in real use did it move to PostgreSQL on AWS. Do not build the cloud first.
- **Choose the interface people already use.** A web app was considered, but Telegram won: no installation, works on any phone, fast to use in the field, easy to restrict to a few users.
- **Build for the worst moment.** The design question was always "does this work when the user is tired and under pressure?" This led to the two-layer menu, kits, auto-quantity of 1, recent soldiers first, and undo buttons.
- **Prefer reversible actions.** Soft delete for soldiers, undo after every action, idempotent migrations that are safe to run twice.
- **Test critically before delivering.** Every change was tested in a sandbox with simulated flows and edge cases before the user deployed it. The user explicitly asked for a critical review, and it found real bugs.
- **Real bugs found by thinking through consequences,** not only by running code. Example: removing a soldier left his gear "issued" forever. The user caught it by asking "where does his gear go?". Lesson: for every state change, ask where the related data ends up.
- **Keep the human in control of deployment.** Claude builds and tests; the user deploys to AWS and pushes to GitHub, following exact step-by-step commands.
- **Security as a habit, not an afterthought.** See section 8.

## 4. Architecture

```
Telegram  -->  Bot (Python 3.9, EC2 t3.micro, systemd service)  -->  PostgreSQL (AWS RDS)
```

- EC2 (Amazon Linux 2023) runs the bot with `Restart=always`, so it survives crashes and reboots.
- RDS accepts connections on port 5432 only from the EC2 security group.
- Server access uses Systems Manager Session Manager, so no permanently open SSH is needed.
- Secrets live in a `.env` file on the server and are never committed.
- Budget alarm set to zero-spend; root account protected with MFA.

## 5. Data model

`platoons`, `soldiers` (soft delete via `is_active`), `equipment_types` (layer: personal / company / battalion, with `total_quantity`), `holders` (soldier / platoon sergeant / battalion), `current_holdings`, `transactions` (issue / return / missing), `shortages`, `bot_users` (full / mefaleg / view_only).

Key rule: `available = total - issued - missing`. Shortages do not return to stock. A battalion return also lowers the total, because the item has left the company.

## 6. What was built

- **Menu:** two layers. The main menu has sign-out, return and platoon report first. Shortages, soldier management, battalion layer and warehouse/reports are submenus. View-only users see only the platoon report.
- **Sign-out and return:** kits (rifleman kit, Negev/Mag kit) in one tap; quantity question only for magazines, thigh pouches and drums; "add another item to the same soldier"; recent soldiers first; return screen shows only what the soldier actually holds.
- **Undo:** a specific undo button after each action, with a clear message of what was cancelled.
- **Shortages:** report a missing item, undo, shortage report, Excel export.
- **Soldier management:** add, remove. Removing returns all his gear to the warehouse and logs it.
- **Battalion layer:** sign, return, inventory, Excel export; manual holder creation to avoid duplicates.
- **Reports:** sent privately; each new report replaces the previous one to avoid clutter.
- **Excel exports:** full report (sheet per platoon), shortage report, battalion inventory.
- **Permissions:** checked on every action; unregistered users get nothing.
- **Scripts:** roster import, one-time migrations (all idempotent), test-data cleanup.

## 7. Problems solved and lessons

| Problem | Fix | Lesson |
|---|---|---|
| Roster Excel leaked into a public repo | Rewrote git history, added ignore rules | Add `.gitignore` before the first commit |
| A CSV export was committed later | Removed from tracking, amended, force-pushed | Ignore `*.csv`, `*.xlsx`, `*.pem`, `.env`, `*.db` |
| Python 3.9 error on `str \| None` | Use `typing.Optional` | Match syntax to the server's Python version |
| EC2 could not reach RDS | Added a security-group rule for port 5432 | Check network rules first for connection timeouts |
| Old file still on the server after an update | Uploaded the new one | After deploying, confirm the right file is in place |
| "Back to menu" failed mid-flow | Menu handler first in every state | Test escape routes from every state |
| Removing a soldier left gear stuck as issued | Auto-return and log on removal | Think through what every state change does to related data |
| `scp` failing | Run it from the local machine, not inside SSH | Know which machine a command runs on |
| Env vars not loaded | Load `.env` inside the DB module | Do not rely on import order |

## 8. Security approach

- Repo is public: no tokens, passwords, rosters, real names or key files in it.
- `.gitignore` covers `.env`, `*.db`, `*.xlsx`, `*.csv`, `*.pem`, `__pycache__/`.
- Run `git status` before every push.
- Telegram access is limited to registered user IDs, with three permission levels.
- Secrets that were ever pasted into a chat must be rotated (bot token via BotFather `/revoke`, database password via RDS).
- Database is not public; only the bot's server can reach it.

## 9. Working style (for future sessions)

- Talk to the user in **Hebrew only**. Do not mix English words inside Hebrew sentences (mixed text renders badly). Put commands, paths and code on their own lines.
- In Hebrew, use masculine forms.
- Be concise and natural; do not over-explain.
- Give exact, copy-paste commands, and say where to run each one (local PowerShell vs. the server).
- Be critical: test, look for edge cases, and say when something is a real bug.
- Show the full command list when asked, not a shortened version.

## 10. Open items and roadmap

**Product**
- Button to see what a single soldier is signed for (the function `get_soldier_status` already exists).
- UI for company gear signed to sergeants.
- Block sign-out above warehouse stock.
- Low-stock alerts and a "close shortage" button.
- Confirm the mefaleg permission level in real use.

**Cloud and security**
- Rotate the exposed bot token and database password.
- Move secrets to AWS Secrets Manager.
- Tighten the SSH security-group rule (it was opened to everyone at one point), or use only Session Manager.
- Add an Elastic IP (the public IP changes on stop/start).
- Set up CloudWatch logs and alarms.
- Fix the IAM admin user login and stop using root.

**Repo**
- Keep the README current when features change.
- Consider moving to a private repo if real data ever gets near the code.

## 11. How to use this file

- Add it to the Claude Project knowledge so new sessions start with full context.
- Commit it to the repo as `PROJECT_CONTEXT.md` (it is safe: no secrets or personal data).
- Update sections 6 and 10 after each release.

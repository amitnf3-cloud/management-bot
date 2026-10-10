# Management Bot – Military Equipment Sign-Out Tracker

A Telegram bot that tracks equipment signed out to soldiers in a company (about 100 soldiers, 6 platoons). It is built for fast use under pressure: sign-out and return are always the first buttons.

The bot runs 24/7 on AWS. It is also a hands-on project for learning cloud work.

> This repository is public. It contains **no** real names, rosters, tokens or passwords. See [Security](#security).

## Architecture

```
Telegram  -->  Bot (Python, EC2, systemd service)  -->  PostgreSQL (AWS RDS)
```

- **EC2** (Amazon Linux 2023, t3.micro) runs the bot as a systemd service with `Restart=always`.
- **RDS PostgreSQL** stores all data. Only the EC2 security group can reach port 5432.
- **Systems Manager Session Manager** is used for server access (no open SSH needed).
- Secrets live in a `.env` file on the server and are never committed.

## Features

**Daily actions**
- 📤 Sign-out and 📥 return of equipment to a soldier
- Ready-made kits (full rifleman kit, Negev/Mag kit) in one tap
- Quantity question only for items that need it (magazines, thigh pouches, drums); everything else is quantity 1
- "Add another item to the same soldier" button
- Specific undo button after every action
- Recently used soldiers appear first

**Reports**
- 📊 Platoon report (one line per soldier)
- 📦 Warehouse status (total, issued, missing, available)
- 📥 Excel export: one sheet per platoon
- Reports are sent privately and replace the previous one

**Shortages**
- 🆘 Report a missing item, with undo
- 📊 Shortage report and 📥 Excel export
- Missing items do not return to warehouse stock

**Soldier management**
- ➕ Add soldier, 🗑️ remove soldier (soft delete)
- Removing a soldier automatically returns his gear to the warehouse and logs it

**Battalion layer**
- 🎖️ Track what the company is signed for versus the battalion
- Sign, return, inventory and Excel export
- Intended for the battalion logistics (mefaleg) staff

**Permissions**
- `full`: everything
- `mefaleg`: battalion layer
- `view_only`: platoon report only

## Project structure

```
bot/
  main.py            Telegram bot: menus, conversations, buttons
  access.py          Permission levels and user registration
db/
  operations.py      All database functions (psycopg2)
  excel_export.py    Excel report builders (openpyxl)
  schema_postgres.sql  PostgreSQL schema and seed data
  schema.sql         Old SQLite schema (kept for history)
scripts/
  import_soldiers.py       Import soldiers from an Excel file
  migrate_*.py             One-time, idempotent migrations
  cleanup_test_data.py     Remove test data (names starting with "בדיקה")
requirements.txt
```

## Data model

`platoons`, `soldiers`, `equipment_types` (layer: personal / company / battalion), `holders` (soldier / platoon sergeant / battalion), `current_holdings`, `transactions` (issue / return / missing), `shortages`, `bot_users`.

Warehouse math: `available = total - issued - missing`.

## Setup

Requires Python 3.9+.

```bash
pip install -r requirements.txt psycopg2-binary
```

Create a `.env` file (never commit it):

```
BOT_TOKEN=your_telegram_bot_token
DB_HOST=your-rds-endpoint
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=your_password
```

Prepare the database:

```bash
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -f db/schema_postgres.sql
python scripts/migrate_2026_07_31.py
python scripts/migrate_2026_08_09.py
python scripts/migrate_2026_08_09_merge.py
python scripts/migrate_2026_09_08.py
```

Import soldiers from a local Excel file (keep it out of git):

```bash
python scripts/import_soldiers.py "path/to/roster.xlsx"
```

Run the bot:

```bash
python bot/main.py
```

## Deploy to EC2

Run `scp` from your local machine, not inside the SSH session:

```bash
scp bot/main.py ec2-user@<EC2_IP>:~/
```

Then on the server:

```bash
sudo systemctl stop tzanchanim-bot
mv ~/main.py ~/bot/main.py
sudo systemctl start tzanchanim-bot
sudo systemctl status tzanchanim-bot
```

Logs: `sudo journalctl -u tzanchanim-bot -f`

## Security

- `.gitignore` blocks `.env`, `*.db`, `*.xlsx`, `*.csv`, `*.pem`.
- Before every push, run `git status` and check that no secret or roster file is listed.
- Rotate the bot token (BotFather `/revoke`) and the database password if they were ever exposed.
- Only registered Telegram users can use the bot.

## Roadmap

- Button to see what one soldier is signed for
- UI for company gear signed to sergeants
- Block sign-out above warehouse stock
- Low-stock alerts and a "close shortage" button
- Elastic IP, CloudWatch logs, Secrets Manager

---
name: anymail
description: Operate the AnyMail email CLI in E:\work\AnyMail to manage Gmail IMAP/SMTP profiles, auth (App Passwords via keyring), inbox listing/searching/reading, flags (seen/star/archive/trash), replying, sending email (with attachments), and auditing via invocation logs. Use when you need deterministic, scriptable email operations from the host (Windows) via the `anymail` CLI, including JSON/pipe workflows and troubleshooting with `anymail doctor`.
---

## Ground rules

- Treat AnyMail as the **single source of truth** for email operations.
- Prefer **read-only** commands first (inbox/search/read) before send/flag.
- Prefer **machine output**:
  - Use `--json` when available.
  - Use `--pipe` only when you need UIDs for chaining.

## Where it lives

- Project root: `E:\work\AnyMail`
- Skill scripts: `skills/anymail/scripts/`

## Recommended execution path (most reliable)

Use the wrapper script to run AnyMail with the project venv when present:

- `python skills/anymail/scripts/anymail_run.py -- <anymail args...>`

Examples:
- `python skills/anymail/scripts/anymail_run.py -- doctor`
- `python skills/anymail/scripts/anymail_run.py -- profile list --json`
- `python skills/anymail/scripts/anymail_run.py -- inbox personal --unread --limit 20 --json`

The wrapper:
- Uses `.venv\\Scripts\\python.exe` if it exists
- Otherwise falls back to `python` on PATH
- Runs `-m anymail.cli` from the repo (so you don’t rely on an installed console script)

## Common workflows

### 1) Setup / verify account (profile)

1. Add profile:
   - `... -- profile add <name> --email you@gmail.com`
2. Store app password (interactive):
   - `... -- auth set <name>`
3. Verify connectivity:
   - `... -- auth status --profile <name> --json`

### 2) Triage inbox (safe, read-only)

- List unread:
  - `... -- inbox <profile> --unread --limit 50 --json`
- Search:
  - `... -- search <profile> --subject "invoice" --since 90d --json`
- Read:
  - `... -- read <profile> <uid> --headers --json`
  - `... -- read <profile> <uid> --body --json`

### 3) Save attachments

- List:
  - `... -- read <profile> <uid> --attachments list --json`
- Save:
  - `... -- read <profile> <uid> --attachments save --out <dir> --json`

### 4) Mutate state (ask/confirm in chat before doing)

- Mark read/unread:
  - `... -- flag <profile> <uid> --seen true|false --json`
- Star/unstar:
  - `... -- flag <profile> <uid> --star true|false --json`
- Archive/trash:
  - `... -- flag <profile> <uid> --archive --json`
  - `... -- flag <profile> <uid> --trash --json`

### 5) Send email (be deliberate)

- Dry run first:
  - `... -- send <profile> --to person@example.com --subject "Hi" --body "..." --dry-run`
- Then send:
  - `... -- send <profile> --to ... --subject ... --body ... [--cc ...] [--bcc ...] [--attach <path>] --json`

## Monitoring / debugging

- Health check:
  - `... -- doctor`
- Invocation logs (audit what happened):
  - `... -- logs list --since 24h --json`
  - `... -- logs query --command inbox --limit 100 --json`

## If output looks wrong

- Re-run with `--json`.
- Run `doctor`.
- Inspect logs for errors (`logs list --outcome error --since 7d --json`).

## Reference

Read `skills/anymail/references/cli.md` for the command map + JSON shapes.

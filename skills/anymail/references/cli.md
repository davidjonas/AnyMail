# AnyMail CLI reference (agent-facing)

This file is a quick command map for the AnyMail CLI as implemented in this repo.
Prefer `--json` outputs for automation.

## Wrapper

Use the wrapper so you don’t depend on a globally-installed console script:

```powershell
python skills/anymail/scripts/anymail_run.py -- <args>
```

## Profiles

- Add: `profile add <name> --email <addr> [--imap ... --smtp ... --imap-port ...]`
- List: `profile list --json`
- Show: `profile show <name> --json`
- Set: `profile set <name> [flags...] --json`
- Remove: `profile rm <name> --yes --json` (if implemented)

## Auth

- Set (interactive): `auth set <profile>`
- Clear: `auth clear <profile> --json`
- Status: `auth status [--profile <name>] --json`

## Inbox / search

- Inbox: `inbox <profile> [--unread] [--limit N] [--since 7d] [--from addr] [--folder name] --json`
- UIDs only: `inbox <profile> ... --pipe`
- Search: `search <profile> [--from addr] [--subject text] [--since 90d] [--unread] --json`

## Read

- `read <profile> <uid> --headers --json`
- `read <profile> <uid> --body --json`
- Attachments:
  - list: `read <profile> <uid> --attachments list --json`
  - save: `read <profile> <uid> --attachments save --out <dir> --json`

## Flags / actions

- Seen: `flag <profile> <uid> --seen true|false --json`
- Star: `flag <profile> <uid> --star true|false --json`
- Archive: `flag <profile> <uid> --archive --json`
- Trash: `flag <profile> <uid> --trash --json`

## Reply helper

- `reply <profile> <uid> [--to-all true|false] [--include-quote true|false] --format json`

## Send

- `send <profile> --to <addr> [--cc <addr>] [--bcc <addr>] --subject <text> --body <text> [--attach <path>] [--dry-run] [--json]`

## Doctor

- `doctor`

## Logs

- `logs list [--since 24h|7d|<date>] [--until <date>] [--command <name>] [--outcome success|error] [--profile <name>] [--limit N] --json`
- `logs query ... --offset N --json`

## Notes

- Config: `%USERPROFILE%\\.anymail\\config.json`
- Logs DB: `%USERPROFILE%\\.anymail\\anymail.db`
- Passwords are stored via OS keyring.

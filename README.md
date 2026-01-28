# AnyMail

A Windows-friendly email CLI (Python + Click) focused on **Gmail IMAP/SMTP with App Passwords**, supporting **multiple accounts** ("profiles"), and designed to be easy for an agent (and humans) to drive.

## Features

- **Profile-based**: Everything is namespaced by a profile (e.g., `personal`, `work`)
- **Safe defaults**: Read-only commands don't require SMTP config
- **Idempotent**: Commands are re-runnable
- **Scriptable**: `--json` outputs machine-readable data; `--pipe` outputs IDs
- **Minimal prompts**: Only prompts when needed
- **Invocation logging**: All CLI calls are logged to a local SQLite DB for agent monitoring and debugging

## Installation

```bash
pip install -e .
```

Or install dependencies directly:

```bash
pip install -r requirements.txt
```

## Quick Start

### 1. Add a Profile

```bash
anymail profile add personal --email you@gmail.com
```

(Gmail defaults are used when only `--email` is provided. To override: `--imap`, `--smtp`, `--imap-port`, etc.)

### 2. Set App Password
generate app password at: https://myaccount.google.com/apppasswords

```bash
anymail auth set personal
# Enter your Gmail App Password when prompted
```

### 3. List Inbox

```bash
anymail inbox --unread --limit 20
anymail inbox --json  # JSON output
anymail inbox --pipe  # UIDs only
```

### 4. Read a Message

```bash
anymail read <uid>
anymail read <uid> --headers
anymail read <uid> --body
anymail read <uid> --attachments list
anymail read <uid> --attachments save --out ./downloads
```

### 5. Send Email

```bash
anymail send --to person@example.com --subject "Hi" --body "Hello!"
anymail send --to ... --cc ... --attach ./file.pdf
```

## Commands

### Profile Management

- `anymail profile add <name>` - Add a new profile
- `anymail profile list` - List all profiles
- `anymail profile show <name>` - Show profile details
- `anymail profile set <name>` - Update profile settings
- `anymail profile rm <name>` - Remove a profile

### Authentication

- `anymail auth set <profile>` - Store app password
- `anymail auth clear <profile>` - Clear stored password
- `anymail auth status [--profile <name>]` - Check connection status

### Reading Emails

- `anymail inbox [options]` - List inbox messages
  - `--unread` - Show only unread
  - `--limit <n>` - Limit results
  - `--since <n>d` - Show messages since N days ago
  - `--from <email>` - Filter by sender
  - `--folder <name>` - Specify folder
  - `--json` - JSON output
  - `--pipe` - Output UIDs only

- `anymail search [options]` - Search messages
  - `--from <email>` - Filter by sender
  - `--subject <text>` - Filter by subject
  - `--since <n>d` - Search since N days ago
  - `--unread` - Search unread only

- `anymail read <uid> [options]` - Read a message
  - `--headers` - Show headers only
  - `--body` - Show body only
  - `--attachments list` - List attachments
  - `--attachments save --out <dir>` - Save attachments

### Managing Messages

- `anymail flag <uid> [options]` - Set flags
  - `--seen true/false` - Mark as read/unread
  - `--star true/false` - Star/unstar
  - `--archive` - Archive message
  - `--trash` - Move to trash

- `anymail reply <uid> [options]` - Get reply information
  - `--to-all true/false` - Reply to all
  - `--include-quote true/false` - Include quoted text
  - `--format json` - JSON output

### Sending Emails

- `anymail send [options]` - Send an email
  - `--to <email>` - Recipient (can specify multiple)
  - `--cc <email>` - CC recipient
  - `--bcc <email>` - BCC recipient
  - `--subject <text>` - Subject
  - `--body <text>` - Body
  - `--attach <file>` - Attachment (can specify multiple)
  - `--dry-run` - Print MIME without sending

### Utilities

- `anymail doctor` - Check system health

### Logs (agent monitoring)

All CLI invocations are logged to a local SQLite database so you can monitor agent behaviour and debug when something goes wrong.

- `anymail logs list [options]` - List recent invocation logs
  - `--since <date|7d|24h>` - Only entries since
  - `--until <date>` - Only entries until
  - `--command <name>` - Filter by command (e.g. `inbox`, `send`, `profile add`)
  - `--outcome success|error` - Filter by outcome
  - `--profile <name>` - Filter by profile
  - `--limit <n>` - Max entries (default 50)
  - `--json` - Output JSON

- `anymail logs query [options]` - Query logs with filters and pagination
  - Same filters as `list`, plus `--offset` for pagination
  - `--json` - Output full log rows as JSON

Log database path: same config dir as `config.json` (e.g. `%USERPROFILE%\.anymail\anymail.db`). Sensitive values (e.g. `--body`, `--attach` content) are redacted in stored args.

## Gmail Setup

To use Gmail IMAP/SMTP with app passwords:

1. Enable 2FA on your Google account
2. Create an App Password: https://myaccount.google.com/apppasswords
3. Ensure IMAP is enabled in Gmail settings
4. Use the `--gmail` flag when adding a profile for automatic folder configuration

## Configuration

Config is stored in:
- Windows: `%USERPROFILE%\.anymail\config.json`
- Other: `~/.anymail/config.json`

Passwords are stored in the OS keychain via `keyring`:
- Windows: Windows Credential Manager
- macOS: Keychain
- Linux: Secret Service API

## Examples

### List unread emails from last 7 days

```bash
anymail inbox --unread --since 7d
```

### Search for invoices

```bash
anymail search --subject "invoice" --since 90d --json
```

### Archive a message

```bash
anymail flag 12345 --archive
```

### Send with attachment

```bash
anymail send --to user@example.com \
  --subject "Report" \
  --body "Please find attached." \
  --attach report.pdf
```

### Pipe UIDs to read command

```bash
anymail inbox --unread --pipe | xargs -I {} anymail read {}
```

## License

MIT

# AnyMail — CLI Spec & Plan

## Goal
Build a **Windows-friendly** email CLI (Python + Click) focused on **Gmail IMAP/SMTP with App Passwords**, supporting **multiple accounts** (“profiles”), and designed to be easy for an agent (and humans) to drive.

Non-goals (for v1):
- Full Gmail API parity (labels, threads, history/watch). IMAP is good enough.
- Fancy TUI.

---

## Why IMAP/SMTP (vs Gmail API)
- Avoids OAuth verification/testing-mode token expiry issues.
- Works on personal Gmail accounts without Workspace.
- Stable automation path.

---

## UX Principles
- **Profiles**: everything is namespaced by a profile (e.g. `personal`, `sineways`).
- **Safe defaults**: read-only commands don’t require SMTP config.
- **Idempotent**: commands should be re-runnable.
- **Scriptable**: `--json` outputs machine-readable data; `--pipe` outputs IDs.
- **Minimal prompts**: only prompt when needed (like PostLockerCLI).

---

## Storage & Security

### Config
Store non-secret config in:
- Windows: `%USERPROFILE%\.anymail\config.json`
- (Cross-platform fallback: `~/.anymail/config.json`)

Config includes:
- profiles: email, imap host/port, smtp host/port, default folders, default from-name.

### Secrets
Store passwords in **OS keychain** via `keyring`.
- Key name format: `anymail:{profile}`
- Stored value: app password (or future: OAuth refresh token)

Rationale:
- Avoid rolling our own encryption.
- Works well on Windows via Credential Manager.

---

## Technology Choices
- Python 3.11+ (3.12 ok)
- `click` for CLI
- `keyring` for secret storage
- `imapclient` + `email` stdlib for IMAP + parsing
- `smtplib` / `email.message.EmailMessage` for SMTP
- Optional:
  - `rich` for nicer output (keep optional)
  - `python-dateutil` for date parsing

---

## CLI Command Surface

Binary name: `anymail` (package `anymail`).

### Top-level global options
- `--profile, -p <name>`: select profile (optional if only 1 exists)
- `--host <imap-host>`: override (debug)
- `--json`: output JSON
- `--quiet`: reduce logs

---

## Commands

### 1) `anymail profile` (profile management)

**Create/update profiles**
```bash
anymail profile add personal --email you@gmail.com \
  --imap imap.gmail.com --imap-port 993 --imap-ssl \
  --smtp smtp.gmail.com --smtp-port 587 --smtp-starttls

anymail profile set personal --folder-inbox INBOX --folder-sent "[Gmail]/Sent Mail"

anymail profile list
anymail profile show personal
anymail profile rm personal
```

Spec:
- `profile add` creates profile entry; does NOT store secrets.
- `profile set` modifies fields.

### 2) `anymail auth` (credentials)
```bash
anymail auth set personal         # prompts for app password, stores in keyring
anymail auth clear personal
anymail auth status [--profile X] # can we connect? (IMAP), show masked info
```

Spec:
- `auth set` uses hidden input.
- `auth status` should not leak secrets.

### 3) `anymail inbox` (quick listing)
```bash
anymail inbox --unread --limit 20
anymail inbox --since 7d --from "stripe.com" --limit 50
anymail inbox --folder INBOX
anymail inbox --json
anymail inbox --pipe             # output message ids only
```

Output fields (JSON):
- `id` (IMAP UID)
- `message_id` (RFC Message-ID)
- `from`, `to`, `subject`
- `date` (ISO)
- `snippet` (best-effort from first text/plain chunk)
- `flags` (seen/answered/flagged)

### 4) `anymail search`
Gmail-style search is not standard IMAP, but we can implement:
- basic IMAP criteria: FROM/SUBJECT/SINCE/BEFORE/UNSEEN
- optional `--raw-imap "(OR FROM ... SUBJECT ...)"`

```bash
anymail search --from "billing@" --since 30d --unread
anymail search --subject "invoice" --since 90d
```

### 5) `anymail read`
```bash
anymail read <uid>
anymail read <uid> --headers
anymail read <uid> --body
anymail read <uid> --attachments list
anymail read <uid> --attachments save --out ./downloads
```

Spec:
- Provide clear separation between headers/body.
- Attachments: list filenames, content-type, size. Save to disk on request.

### 6) `anymail flag` (state changes)
```bash
anymail flag <uid> --seen true
anymail flag <uid> --star true
anymail flag <uid> --archive true     # Gmail maps to move out of INBOX
anymail flag <uid> --trash true
```

Notes:
- Gmail folder mapping:
  - Archive: remove INBOX label → IMAP: move from INBOX to "[Gmail]/All Mail" or just remove INBOX depending on server.
  - Trash: move to "[Gmail]/Trash".

### 7) `anymail draft` / `anymail reply` (agent-friendly)
We want a command that returns:
- a clean **quoted context** (minimal)
- a suggested reply skeleton (optional for now)

```bash
anymail reply <uid> --to-all false --include-quote true
anymail reply <uid> --format json
```

v1 spec:
- Outputs a JSON object with:
  - `to`, `cc`, `subject`
  - `in_reply_to`, `references`
  - `quoted_plaintext`
  - `original_summary` (optional: heuristic)

### 8) `anymail send`
```bash
anymail send --to person@example.com --subject "Hi" --body "..."
anymail send --to ... --cc ... --bcc ... --attach ./file.pdf
```

Safety:
- Add `--dry-run` to print MIME without sending.
- Consider `--confirm` for interactive sends.

### 9) `anymail doctor`
```bash
anymail doctor
```

Checks:
- can read config
- can access keyring
- can connect to IMAP (login)
- folder existence checks

---

## Gmail Profile Defaults
When `--gmail` flag is used in `profile add`, default folders:
- inbox: `INBOX`
- sent: `[Gmail]/Sent Mail`
- trash: `[Gmail]/Trash`
- allmail: `[Gmail]/All Mail`

---

## Output & Interop

### JSON mode
All list/search operations should support `--json`.

### Pipe mode
For list/search operations:
- `--pipe` outputs UIDs (one per line)

Example:
```bash
anymail inbox --unread --pipe | anymail read
```

(If we want this, `anymail read` must accept stdin UIDs.)

---

## Internal Modules

- `anymail/cli.py` — Click entrypoint
- `anymail/config.py` — load/save config
- `anymail/keychain.py` — keyring get/set
- `anymail/imap.py` — IMAP client wrapper (connect, search, fetch)
- `anymail/parse.py` — MIME parsing helpers, snippet extraction
- `anymail/smtp.py` — send mail
- `anymail/types.py` — typed dicts / dataclasses for responses

---

## Milestones

### M1 (Read-only MVP)
- profile add/list/show
- auth set/status
- inbox list (--unread, --limit, --json, --pipe)
- read message (headers + body)
- doctor

### M2 (Triage)
- search
- flag seen/star
- archive/trash (Gmail mapping)

### M3 (Send)
- send with attachments
- reply JSON builder (agent-friendly)

### M4 (Nice-to-have)
- rich formatting
- caching (local) for faster listing
- pluggable backends (future Gmail API)

---

## Open Questions
1. Do you want the CLI to support **multiple simultaneous inboxes** (merge view), or keep it strictly per-profile?
Answer: Per profile
2. For archive semantics on Gmail IMAP: do you prefer **remove INBOX** or **move to All Mail** explicitly?
Answer: remove INBOX
3. Should `anymail send` require an explicit `--yes` when not in `--dry-run`?
Answer: no
---

## Notes (setup reminders)
To use Gmail IMAP/SMTP with app passwords:
- Enable 2FA
- Create App Password
- Ensure IMAP is enabled in Gmail settings

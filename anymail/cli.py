"""Click CLI entrypoint for AnyMail."""

import click
import json
import sys
import time
from pathlib import Path
from typing import Any, Optional
from datetime import datetime, timedelta
import getpass

from .config import (
    load_config,
    add_profile,
    remove_profile,
    get_profile,
    Profile,
)
from .keychain import (
    get_password,
    set_password,
    clear_password,
    has_password,
)
from .imap import IMAPClientWrapper
from .parse import (
    parse_message,
    get_plaintext_body,
    get_html_body,
    get_attachments,
    get_attachment_content,
    get_reply_headers,
    format_addresses,
)
from .smtp import send_email
from .types import MessageSummary
from . import db as log_db


# Global options
def add_global_options(f):
    """Add global options to a command."""
    f = click.option("--profile", "-p", help="Profile name")(f)
    f = click.option("--host", help="Override IMAP host (debug)")(f)
    f = click.option("--json", "output_json", is_flag=True, help="Output JSON")(f)
    f = click.option("--quiet", is_flag=True, help="Reduce logs")(f)
    return f


class LoggingGroup(click.Group):
    """Click Group that logs every invocation to SQLite for agent monitoring."""

    def invoke(self, ctx: click.Context) -> Any:
        argv = list(sys.argv[1:])
        start = time.perf_counter()
        outcome = "success"
        error_message = None
        try:
            result = super().invoke(ctx)
            return result
        except Exception as e:
            outcome = "error"
            error_message = str(e)
            raise
        finally:
            duration_ms = int((time.perf_counter() - start) * 1000)
            # Command path from argv: e.g. "inbox", "profile add", "logs list"
            try:
                path = "unknown"
                if argv:
                    path = argv[0]
                    if path == "profile" and len(argv) > 1:
                        path = f"profile {argv[1]}"
                    elif path == "logs" and len(argv) > 1:
                        path = f"logs {argv[1]}"
                    elif path == "auth" and len(argv) > 1:
                        path = f"auth {argv[1]}"
                if not path or path == "unknown":
                    path = (getattr(ctx, "command_path", None) or "").replace("cli ", "").strip() or "unknown"
                profile_used = ctx.params.get("profile") if ctx.params else None
                args_sanitized = log_db.sanitize_argv(argv)
                args_json = json.dumps(args_sanitized, ensure_ascii=False)
                log_db.init_db()
                log_db.insert_log(
                    command=path,
                    args_json=args_json,
                    profile=profile_used,
                    outcome=outcome,
                    error_message=error_message,
                    duration_ms=duration_ms,
                )
            except Exception:
                pass


@click.group(cls=LoggingGroup)
@click.version_option()
def cli():
    """AnyMail - A Windows-friendly email CLI for Gmail IMAP/SMTP."""
    pass


# Profile management
@cli.group()
def profile():
    """Manage email profiles."""
    pass


# Gmail defaults when using --gmail or when only --email is provided
GMAIL_IMAP_HOST = "imap.gmail.com"
GMAIL_IMAP_PORT = 993
GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 587


@profile.command("add")
@click.argument("name")
@click.option("--email", required=True, help="Email address")
@click.option("--imap", default=None, help="IMAP host (default: imap.gmail.com when using Gmail defaults)")
@click.option("--imap-port", type=int, default=None, help="IMAP port (default: 993)")
@click.option("--imap-ssl/--no-imap-ssl", default=None, help="Use SSL for IMAP (default: true)")
@click.option("--smtp", default=None, help="SMTP host (default: smtp.gmail.com when using Gmail defaults)")
@click.option("--smtp-port", type=int, default=None, help="SMTP port (default: 587)")
@click.option("--smtp-starttls/--no-smtp-starttls", default=None, help="Use STARTTLS for SMTP (default: true)")
@click.option("--gmail", is_flag=True, help="Use Gmail defaults (default: true when --imap/--smtp omitted)")
def profile_add(name, email, imap, imap_port, imap_ssl, smtp, smtp_port, smtp_starttls, gmail):
    """Add a new profile. With only --email (and name), Gmail defaults are used."""
    use_gmail_defaults = gmail or (imap is None and smtp is None)
    if use_gmail_defaults:
        imap_host = imap or GMAIL_IMAP_HOST
        imap_port_val = imap_port if imap_port is not None else GMAIL_IMAP_PORT
        imap_ssl_val = imap_ssl if imap_ssl is not None else True
        smtp_host = smtp or GMAIL_SMTP_HOST
        smtp_port_val = smtp_port if smtp_port is not None else GMAIL_SMTP_PORT
        smtp_starttls_val = smtp_starttls if smtp_starttls is not None else True
        folder_inbox = "INBOX"
        folder_sent = "[Gmail]/Sent Mail"
        folder_trash = "[Gmail]/Trash"
        folder_allmail = "[Gmail]/All Mail"
    else:
        if imap is None or smtp is None:
            click.echo("Error: --imap and --smtp are required when not using Gmail defaults.", err=True)
            sys.exit(1)
        imap_host = imap
        imap_port_val = imap_port if imap_port is not None else 993
        imap_ssl_val = imap_ssl if imap_ssl is not None else True
        smtp_host = smtp
        smtp_port_val = smtp_port if smtp_port is not None else 587
        smtp_starttls_val = smtp_starttls if smtp_starttls is not None else True
        folder_inbox = "INBOX"
        folder_sent = "[Gmail]/Sent Mail"
        folder_trash = "[Gmail]/Trash"
        folder_allmail = "[Gmail]/All Mail"
    profile = Profile(
        name=name,
        email=email,
        imap_host=imap_host,
        imap_port=imap_port_val,
        imap_ssl=imap_ssl_val,
        smtp_host=smtp_host,
        smtp_port=smtp_port_val,
        smtp_starttls=smtp_starttls_val,
        folder_inbox=folder_inbox,
        folder_sent=folder_sent,
        folder_trash=folder_trash,
        folder_allmail=folder_allmail,
    )
    add_profile(profile)
    click.echo(f"Profile '{name}' added.")


@profile.command("set")
@click.argument("name")
@click.option("--folder-inbox", help="Inbox folder name")
@click.option("--folder-sent", help="Sent folder name")
@click.option("--folder-trash", help="Trash folder name")
@click.option("--folder-allmail", help="All Mail folder name")
@click.option("--default-from-name", help="Default from name")
def profile_set(name, folder_inbox, folder_sent, folder_trash, folder_allmail, default_from_name):
    """Update profile settings."""
    profiles = load_config()
    if name not in profiles:
        click.echo(f"Profile '{name}' not found.", err=True)
        sys.exit(1)
    
    profile = profiles[name]
    if folder_inbox:
        profile.folder_inbox = folder_inbox
    if folder_sent:
        profile.folder_sent = folder_sent
    if folder_trash:
        profile.folder_trash = folder_trash
    if folder_allmail:
        profile.folder_allmail = folder_allmail
    if default_from_name:
        profile.default_from_name = default_from_name
    
    add_profile(profile)
    click.echo(f"Profile '{name}' updated.")


@profile.command("list")
def profile_list():
    """List all profiles."""
    profiles = load_config()
    if not profiles:
        click.echo("No profiles configured.")
        return
    
    for name, profile in profiles.items():
        click.echo(f"{name}: {profile.email}")


@profile.command("show")
@click.argument("name")
def profile_show(name):
    """Show profile details."""
    profiles = load_config()
    if name not in profiles:
        click.echo(f"Profile '{name}' not found.", err=True)
        sys.exit(1)
    
    profile = profiles[name]
    click.echo(f"Name: {profile.name}")
    click.echo(f"Email: {profile.email}")
    click.echo(f"IMAP: {profile.imap_host}:{profile.imap_port} (SSL: {profile.imap_ssl})")
    click.echo(f"SMTP: {profile.smtp_host}:{profile.smtp_port} (STARTTLS: {profile.smtp_starttls})")
    click.echo(f"Folders:")
    click.echo(f"  Inbox: {profile.folder_inbox}")
    click.echo(f"  Sent: {profile.folder_sent}")
    click.echo(f"  Trash: {profile.folder_trash}")
    click.echo(f"  All Mail: {profile.folder_allmail}")


@profile.command("rm")
@click.argument("name")
@click.confirmation_option(prompt="Are you sure you want to remove this profile?")
def profile_rm(name):
    """Remove a profile."""
    if remove_profile(name):
        click.echo(f"Profile '{name}' removed.")
    else:
        click.echo(f"Profile '{name}' not found.", err=True)
        sys.exit(1)


# Auth management
@cli.group()
def auth():
    """Manage credentials."""
    pass


@auth.command("set")
@click.argument("profile_name")
def auth_set(profile_name):
    """Set app password for a profile."""
    profiles = load_config()
    if profile_name not in profiles:
        click.echo(f"Profile '{profile_name}' not found.", err=True)
        sys.exit(1)
    
    password = getpass.getpass("App password: ")
    set_password(profile_name, password)
    click.echo(f"Password stored for profile '{profile_name}'.")


@auth.command("clear")
@click.argument("profile_name")
def auth_clear(profile_name):
    """Clear stored password for a profile."""
    if clear_password(profile_name):
        click.echo(f"Password cleared for profile '{profile_name}'.")
    else:
        click.echo(f"No password found for profile '{profile_name}'.", err=True)
        sys.exit(1)


@auth.command("status")
@click.option("--profile", "-p", help="Profile name")
def auth_status(profile):
    """Check authentication status."""
    try:
        profile_obj = get_profile(profile)
        if not profile_obj:
            click.echo("No profile found.", err=True)
            sys.exit(1)
        
        has_pwd = has_password(profile_obj.name)
        click.echo(f"Profile: {profile_obj.name}")
        click.echo(f"Email: {profile_obj.email}")
        click.echo(f"Password stored: {'Yes' if has_pwd else 'No'}")
        
        if has_pwd:
            # Try to connect
            password = get_password(profile_obj.name)
            try:
                with IMAPClientWrapper(profile_obj, password) as client:
                    click.echo("Connection: OK")
            except Exception as e:
                click.echo(f"Connection: FAILED - {e}", err=True)
    except ValueError as e:
        click.echo(str(e), err=True)
        sys.exit(1)


# Inbox listing
@cli.command("inbox")
@add_global_options
@click.option("--unread", is_flag=True, help="Show only unread")
@click.option("--limit", type=int, help="Limit number of results")
@click.option("--since", help="Show messages since (e.g., 7d, 30d)")
@click.option("--from", "from_addr", help="Filter by sender")
@click.option("--folder", help="Folder to list (default: inbox)")
@click.option("--pipe", is_flag=True, help="Output UIDs only (one per line)")
def inbox_cmd(profile, host, output_json, quiet, unread, limit, since, from_addr, folder, pipe):
    """List messages in inbox."""
    try:
        profile_obj = get_profile(profile)
        if not profile_obj:
            click.echo("No profile found.", err=True)
            sys.exit(1)
        
        if host:
            profile_obj.imap_host = host
        
        password = get_password(profile_obj.name)
        if not password:
            click.echo("No password stored. Use 'anymail auth set' first.", err=True)
            sys.exit(1)
        
        # Parse since date
        since_date = None
        if since:
            try:
                days = int(since.rstrip("d"))
                since_date = datetime.now() - timedelta(days=days)
            except ValueError:
                click.echo(f"Invalid --since format: {since}. Use format like '7d' or '30d'.", err=True)
                sys.exit(1)
        
        with IMAPClientWrapper(profile_obj, password) as client:
            uids = client.search_messages(
                folder=folder,
                unread=unread if unread else None,
                since=since_date,
                from_addr=from_addr,
            )
            
            if limit:
                uids = uids[:limit]
            
            if pipe:
                for uid in uids:
                    click.echo(str(uid))
                return
            
            messages = client.fetch_messages(uids, folder=folder)
            
            if output_json:
                result = [msg.to_dict() for msg in messages.values()]
                click.echo(json.dumps(result, indent=2))
            else:
                for uid in uids:
                    if uid in messages:
                        msg = messages[uid]
                        status = "U" if not msg.flags.get("seen") else " "
                        flagged = "*" if msg.flags.get("flagged") else " "
                        click.echo(f"{status}{flagged} {uid:6d}  {msg.from_addr:30s}  {msg.subject}")
    except Exception as e:
        if not quiet:
            click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# Search
@cli.command("search")
@add_global_options
@click.option("--unread", is_flag=True, help="Search unread only")
@click.option("--since", help="Search since (e.g., 7d, 30d)")
@click.option("--before", help="Search before (e.g., 2024-01-01)")
@click.option("--from", "from_addr", help="Filter by sender")
@click.option("--subject", help="Filter by subject")
@click.option("--raw-imap", help="Raw IMAP search criteria")
@click.option("--limit", type=int, help="Limit number of results")
@click.option("--folder", help="Folder to search")
@click.option("--pipe", is_flag=True, help="Output UIDs only")
def search_cmd(profile, host, output_json, quiet, unread, since, before, from_addr, subject, raw_imap, limit, folder, pipe):
    """Search for messages."""
    try:
        profile_obj = get_profile(profile)
        if not profile_obj:
            click.echo("No profile found.", err=True)
            sys.exit(1)
        
        if host:
            profile_obj.imap_host = host
        
        password = get_password(profile_obj.name)
        if not password:
            click.echo("No password stored. Use 'anymail auth set' first.", err=True)
            sys.exit(1)
        
        # Parse dates
        since_date = None
        if since:
            try:
                days = int(since.rstrip("d"))
                since_date = datetime.now() - timedelta(days=days)
            except ValueError:
                click.echo(f"Invalid --since format: {since}. Use format like '7d' or '30d'.", err=True)
                sys.exit(1)
        
        before_date = None
        if before:
            try:
                before_date = datetime.fromisoformat(before)
            except ValueError:
                click.echo(f"Invalid --before format: {before}. Use ISO format like '2024-01-01'.", err=True)
                sys.exit(1)
        
        with IMAPClientWrapper(profile_obj, password) as client:
            uids = client.search_messages(
                folder=folder,
                unread=unread if unread else None,
                since=since_date,
                before=before_date,
                from_addr=from_addr,
                subject=subject,
                raw_criteria=raw_imap,
            )
            
            if limit:
                uids = uids[:limit]
            
            if pipe:
                for uid in uids:
                    click.echo(str(uid))
                return
            
            messages = client.fetch_messages(uids, folder=folder)
            
            if output_json:
                result = [msg.to_dict() for msg in messages.values()]
                click.echo(json.dumps(result, indent=2))
            else:
                for uid in uids:
                    if uid in messages:
                        msg = messages[uid]
                        status = "U" if not msg.flags.get("seen") else " "
                        flagged = "*" if msg.flags.get("flagged") else " "
                        click.echo(f"{status}{flagged} {uid:6d}  {msg.from_addr:30s}  {msg.subject}")
    except Exception as e:
        if not quiet:
            click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# Read message
@cli.command("read")
@add_global_options
@click.argument("uid", type=int, required=False)
@click.option("--headers", is_flag=True, help="Show headers only")
@click.option("--body", is_flag=True, help="Show body only")
@click.option("--attachments", type=click.Choice(["list", "save"]), help="List or save attachments")
@click.option("--out", type=click.Path(), help="Output directory for attachments")
@click.option("--folder", help="Folder to read from")
def read_cmd(profile, host, output_json, quiet, uid, headers, body, attachments, out, folder):
    """Read a message. UID can be provided as argument or read from stdin (one per line)."""
    try:
        # Read UIDs from stdin if not provided
        uids_to_read = []
        if uid is not None:
            uids_to_read = [uid]
        else:
            # Try to read from stdin
            if not sys.stdin.isatty():
                for line in sys.stdin:
                    line = line.strip()
                    if line:
                        try:
                            uids_to_read.append(int(line))
                        except ValueError:
                            if not quiet:
                                click.echo(f"Invalid UID: {line}", err=True)
                            continue
            else:
                click.echo("Error: UID required (provide as argument or pipe from stdin)", err=True)
                sys.exit(1)
        
        if not uids_to_read:
            click.echo("No UIDs to read", err=True)
            sys.exit(1)
        
        profile_obj = get_profile(profile)
        if not profile_obj:
            click.echo("No profile found.", err=True)
            sys.exit(1)
        
        if host:
            profile_obj.imap_host = host
        
        password = get_password(profile_obj.name)
        if not password:
            click.echo("No password stored. Use 'anymail auth set' first.", err=True)
            sys.exit(1)
        
        with IMAPClientWrapper(profile_obj, password) as client:
            # Process each UID
            for uid in uids_to_read:
                if len(uids_to_read) > 1 and not output_json:
                    click.echo(f"\n--- Message {uid} ---\n")
                
                raw_message = client.fetch_message(uid, folder=folder)
                message = parse_message(raw_message)
                
                if attachments == "list":
                    atts = get_attachments(message)
                    if output_json:
                        click.echo(json.dumps([att.to_dict() for att in atts], indent=2))
                    else:
                        for att in atts:
                            click.echo(f"{att.filename or '(no filename)'}  {att.content_type}  {att.size} bytes")
                    continue
                
                if attachments == "save":
                    if not out:
                        click.echo("--out required when saving attachments", err=True)
                        sys.exit(1)
                    out_path = Path(out)
                    out_path.mkdir(parents=True, exist_ok=True)
                    atts = get_attachments(message)
                    for att in atts:
                        content, content_type = get_attachment_content(message, filename=att.filename)
                        if content:
                            filename = att.filename or f"attachment_{att.content_id or 'unknown'}"
                            filepath = out_path / filename
                            with open(filepath, "wb") as f:
                                f.write(content)
                            click.echo(f"Saved: {filepath}")
                    continue
                
                # Default: show headers and body
                show_headers = not body
                show_body = not headers
                
                if output_json:
                    result = {
                        "uid": uid,
                        "message_id": message.get("Message-ID"),
                        "headers": dict(message.items()),
                        "body_plain": get_plaintext_body(message),
                        "body_html": get_html_body(message),
                        "attachments": [att.to_dict() for att in get_attachments(message)],
                    }
                    click.echo(json.dumps(result, indent=2))
                else:
                    if show_headers:
                        click.echo("Headers:")
                        click.echo("-" * 80)
                        for key, value in message.items():
                            click.echo(f"{key}: {value}")
                        click.echo("-" * 80)
                    
                    if show_body:
                        plain = get_plaintext_body(message)
                        if plain:
                            click.echo("\nBody:")
                            click.echo("-" * 80)
                            click.echo(plain)
                        else:
                            html = get_html_body(message)
                            if html:
                                click.echo("\nBody (HTML):")
                                click.echo("-" * 80)
                                click.echo(html)
    except Exception as e:
        if not quiet:
            click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# Flag management
@cli.command("flag")
@add_global_options
@click.argument("uid", type=int)
@click.option("--seen", type=bool, help="Set seen flag")
@click.option("--star", type=bool, help="Set starred/flagged flag")
@click.option("--archive", is_flag=True, help="Archive message (remove from INBOX)")
@click.option("--trash", is_flag=True, help="Move to trash")
@click.option("--folder", help="Folder containing the message")
def flag_cmd(profile, host, output_json, quiet, uid, seen, star, archive, trash, folder):
    """Set flags on a message."""
    try:
        profile_obj = get_profile(profile)
        if not profile_obj:
            click.echo("No profile found.", err=True)
            sys.exit(1)
        
        if host:
            profile_obj.imap_host = host
        
        password = get_password(profile_obj.name)
        if not password:
            click.echo("No password stored. Use 'anymail auth set' first.", err=True)
            sys.exit(1)
        
        with IMAPClientWrapper(profile_obj, password) as client:
            if archive:
                client.archive_message(uid, folder=folder)
                click.echo(f"Message {uid} archived.")
            elif trash:
                client.delete_message(uid, folder=folder)
                click.echo(f"Message {uid} moved to trash.")
            else:
                if seen is not None:
                    if seen:
                        client.set_flags(uid, ["\\Seen"], folder=folder)
                    else:
                        client.remove_flags(uid, ["\\Seen"], folder=folder)
                
                if star is not None:
                    if star:
                        client.set_flags(uid, ["\\Flagged"], folder=folder)
                    else:
                        client.remove_flags(uid, ["\\Flagged"], folder=folder)
                
                click.echo(f"Flags updated for message {uid}.")
    except Exception as e:
        if not quiet:
            click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# Reply helper
@cli.command("reply")
@add_global_options
@click.argument("uid", type=int)
@click.option("--to-all", type=bool, default=False, help="Reply to all")
@click.option("--include-quote", type=bool, default=True, help="Include quoted text")
@click.option("--format", type=click.Choice(["json"]), help="Output format")
@click.option("--folder", help="Folder containing the message")
def reply_cmd(profile, host, output_json, quiet, uid, to_all, include_quote, format, folder):
    """Get reply information for a message."""
    try:
        profile_obj = get_profile(profile)
        if not profile_obj:
            click.echo("No profile found.", err=True)
            sys.exit(1)
        
        if host:
            profile_obj.imap_host = host
        
        password = get_password(profile_obj.name)
        if not password:
            click.echo("No password stored. Use 'anymail auth set' first.", err=True)
            sys.exit(1)
        
        with IMAPClientWrapper(profile_obj, password) as client:
            raw_message = client.fetch_message(uid, folder=folder)
            message = parse_message(raw_message)
            
            reply_headers = get_reply_headers(message)
            plain_body = get_plaintext_body(message)
            
            # Build reply addresses
            to_addr = reply_headers["to"]
            cc_addrs = []
            if to_all:
                original_cc = message.get("CC", "")
                original_to = message.get("To", "")
                cc_addrs.extend(format_addresses(original_cc))
                cc_addrs.extend(format_addresses(original_to))
                # Remove self from CC
                cc_addrs = [addr for addr in cc_addrs if addr != profile_obj.email]
            
            # Build subject
            subject = reply_headers["subject"]
            if not subject.lower().startswith("re:"):
                subject = f"Re: {subject}"
            
            result = {
                "to": to_addr,
                "cc": ", ".join(cc_addrs) if cc_addrs else None,
                "subject": subject,
                "in_reply_to": reply_headers["in_reply_to"],
                "references": reply_headers["references"],
                "quoted_plaintext": plain_body if include_quote and plain_body else None,
            }
            
            if format == "json" or output_json:
                click.echo(json.dumps(result, indent=2))
            else:
                click.echo(f"To: {result['to']}")
                if result["cc"]:
                    click.echo(f"Cc: {result['cc']}")
                click.echo(f"Subject: {result['subject']}")
                if result["quoted_plaintext"]:
                    click.echo("\nQuoted text:")
                    click.echo("-" * 80)
                    click.echo(result["quoted_plaintext"])
    except Exception as e:
        if not quiet:
            click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# Send email
@cli.command("send")
@add_global_options
@click.option("--to", multiple=True, required=True, help="Recipient email address")
@click.option("--cc", multiple=True, help="CC email address")
@click.option("--bcc", multiple=True, help="BCC email address")
@click.option("--subject", required=True, help="Email subject")
@click.option("--body", required=True, help="Email body")
@click.option("--attach", multiple=True, type=click.Path(exists=True), help="Attachment file")
@click.option("--dry-run", is_flag=True, help="Print MIME without sending")
def send_cmd(profile, host, output_json, quiet, to, cc, bcc, subject, body, attach, dry_run):
    """Send an email."""
    try:
        profile_obj = get_profile(profile)
        if not profile_obj:
            click.echo("No profile found.", err=True)
            sys.exit(1)
        
        if host:
            profile_obj.smtp_host = host
        
        password = get_password(profile_obj.name)
        if not password:
            click.echo("No password stored. Use 'anymail auth set' first.", err=True)
            sys.exit(1)
        
        attachments = [Path(a) for a in attach] if attach else None
        
        msg = send_email(
            profile=profile_obj,
            password=password,
            to=list(to),
            subject=subject,
            body=body,
            cc=list(cc) if cc else None,
            bcc=list(bcc) if bcc else None,
            attachments=attachments,
            dry_run=dry_run,
        )
        
        if dry_run:
            click.echo("Dry run - MIME message:")
            click.echo("-" * 80)
            click.echo(msg.as_string())
        else:
            click.echo("Email sent successfully.")
    except Exception as e:
        if not quiet:
            click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# Doctor command
@cli.command("doctor")
@add_global_options
def doctor_cmd(profile, host, output_json, quiet):
    """Check system health."""
    issues = []
    
    # Check config
    try:
        profiles = load_config()
        if not profiles:
            issues.append("No profiles configured")
        else:
            click.echo(f"✓ Config readable ({len(profiles)} profile(s))")
    except Exception as e:
        issues.append(f"Config error: {e}")
    
    # Check keyring
    try:
        import keyring
        test_key = "anymail:__test__"
        keyring.set_password("anymail", "__test__", "test")
        keyring.delete_password("anymail", "__test__")
        click.echo("✓ Keyring accessible")
    except Exception as e:
        issues.append(f"Keyring error: {e}")
    
    # Check profile and connection
    try:
        profile_obj = get_profile(profile)
        if profile_obj:
            click.echo(f"✓ Profile '{profile_obj.name}' found")
            
            password = get_password(profile_obj.name)
            if password:
                click.echo("✓ Password stored")
                
                # Try connection
                try:
                    with IMAPClientWrapper(profile_obj, password) as client:
                        folders = client.list_folders()
                        click.echo(f"✓ IMAP connection successful ({len(folders)} folders)")
                        
                        # Check folder existence
                        required_folders = [
                            profile_obj.folder_inbox,
                            profile_obj.folder_sent,
                            profile_obj.folder_trash,
                        ]
                        for folder in required_folders:
                            if folder in folders:
                                click.echo(f"✓ Folder '{folder}' exists")
                            else:
                                issues.append(f"Folder '{folder}' not found")
                except Exception as e:
                    issues.append(f"IMAP connection failed: {e}")
            else:
                issues.append("No password stored for profile")
        else:
            issues.append("No profile available")
    except ValueError as e:
        issues.append(str(e))
    except Exception as e:
        issues.append(f"Profile check error: {e}")
    
    if issues:
        click.echo("\nIssues found:", err=True)
        for issue in issues:
            click.echo(f"  ✗ {issue}", err=True)
        sys.exit(1)
    else:
        click.echo("\n✓ All checks passed")


# Logs (agent monitoring)
@cli.group("logs")
def logs_group():
    """List and query CLI invocation logs (for agent monitoring)."""
    pass


@logs_group.command("list")
@click.option("--since", help="Only entries since (ISO date or e.g. 7d, 24h)")
@click.option("--until", help="Only entries until (ISO date)")
@click.option("--command", help="Filter by command (e.g. inbox, send, profile add)")
@click.option("--outcome", type=click.Choice(["success", "error"]), help="Filter by outcome")
@click.option("--profile", help="Filter by profile name")
@click.option("--limit", type=int, default=50, help="Max entries to show (default 50)")
@click.option("--json", "output_json", is_flag=True, help="Output JSON")
def logs_list(since, until, command, outcome, profile, limit, output_json):
    """List recent CLI invocation logs."""
    since_dt = _parse_date_option(since) if since else None
    until_dt = _parse_date_option(until) if until else None
    rows = log_db.query_logs(
        since=since_dt,
        until=until_dt,
        command=command,
        outcome=outcome,
        profile=profile,
        limit=limit,
    )
    if output_json:
        click.echo(json.dumps(rows, indent=2))
        return
    if not rows:
        click.echo("No log entries found.")
        return
    for r in rows:
        err = f"  error: {r['error_message']}" if r["error_message"] else ""
        dur = f"  {r['duration_ms']}ms" if r["duration_ms"] is not None else ""
        click.echo(f"{r['ts']}  {r['command']:20s}  {r['outcome']:7s}  profile={r['profile'] or '-'}{dur}{err}")


@logs_group.command("query")
@click.option("--since", help="Only entries since (ISO date or e.g. 7d)")
@click.option("--until", help="Only entries until (ISO date)")
@click.option("--command", help="Filter by command")
@click.option("--outcome", type=click.Choice(["success", "error"]), help="Filter by outcome")
@click.option("--profile", help="Filter by profile")
@click.option("--limit", type=int, default=100, help="Max entries (default 100)")
@click.option("--offset", type=int, default=0, help="Offset for pagination")
@click.option("--json", "output_json", is_flag=True, help="Output JSON")
def logs_query(since, until, command, outcome, profile, limit, offset, output_json):
    """Query CLI logs with filters (same as list with pagination and JSON)."""
    since_dt = _parse_date_option(since) if since else None
    until_dt = _parse_date_option(until) if until else None
    rows = log_db.query_logs(
        since=since_dt,
        until=until_dt,
        command=command,
        outcome=outcome,
        profile=profile,
        limit=limit,
        offset=offset,
    )
    if output_json:
        click.echo(json.dumps(rows, indent=2))
        return
    if not rows:
        click.echo("No log entries found.")
        return
    for r in rows:
        err = f"  error: {r['error_message']}" if r["error_message"] else ""
        dur = f"  {r['duration_ms']}ms" if r["duration_ms"] is not None else ""
        args = r.get("args_json") or ""
        if len(args) > 60:
            args = args[:57] + "..."
        click.echo(f"{r['id']}  {r['ts']}  {r['command']:20s}  {r['outcome']:7s}  {r['profile'] or '-'}  {dur}  {args}{err}")


def _parse_date_option(s: str) -> Optional[datetime]:
    """Parse --since/--until: ISO date or relative like 7d, 24h."""
    if not s:
        return None
    s = s.strip().lower()
    now = datetime.utcnow()
    if s.endswith("d"):
        try:
            days = int(s[:-1])
            return now - timedelta(days=days)
        except ValueError:
            pass
    if s.endswith("h"):
        try:
            hours = int(s[:-1])
            return now - timedelta(hours=hours)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        click.echo(f"Invalid date format: {s}. Use ISO date or e.g. 7d, 24h.", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()

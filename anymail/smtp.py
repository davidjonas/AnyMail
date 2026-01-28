"""SMTP sending functionality."""

import smtplib
from email.message import EmailMessage
from typing import List, Optional
from pathlib import Path
from .types import Profile


def send_email(
    profile: Profile,
    password: str,
    to: List[str],
    subject: str,
    body: str,
    cc: Optional[List[str]] = None,
    bcc: Optional[List[str]] = None,
    attachments: Optional[List[Path]] = None,
    in_reply_to: Optional[str] = None,
    references: Optional[str] = None,
    dry_run: bool = False,
) -> EmailMessage:
    """Send an email. Returns the EmailMessage object."""
    msg = EmailMessage()
    
    # Set headers
    msg["From"] = profile.email
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Subject"] = subject
    
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references
    
    # Set body
    msg.set_content(body)
    
    # Add attachments
    if attachments:
        for attachment_path in attachments:
            if attachment_path.exists():
                with open(attachment_path, "rb") as f:
                    file_data = f.read()
                    file_name = attachment_path.name
                    msg.add_attachment(
                        file_data,
                        maintype="application",
                        subtype="octet-stream",
                        filename=file_name,
                    )
    
    if dry_run:
        return msg
    
    # Send via SMTP
    if profile.smtp_starttls:
        server = smtplib.SMTP(profile.smtp_host, profile.smtp_port)
        server.starttls()
    else:
        server = smtplib.SMTP_SSL(profile.smtp_host, profile.smtp_port)
    
    try:
        server.login(profile.email, password)
        recipients = to[:]
        if cc:
            recipients.extend(cc)
        if bcc:
            recipients.extend(bcc)
        server.send_message(msg, to_addrs=recipients)
    finally:
        server.quit()
    
    return msg

"""MIME parsing and message extraction utilities."""

import email
from email.message import EmailMessage, Message
from typing import Optional, List, Tuple
from datetime import datetime
from .types import AttachmentInfo


def parse_message(raw_message: bytes) -> EmailMessage:
    """Parse raw email bytes into EmailMessage."""
    return email.message_from_bytes(raw_message, policy=email.policy.default)


def extract_snippet(message: Message, max_length: int = 200) -> str:
    """Extract a text snippet from a message."""
    # Try to get plain text body
    body = get_plaintext_body(message)
    if body:
        # Clean up whitespace
        snippet = " ".join(body.split())
        if len(snippet) > max_length:
            snippet = snippet[:max_length] + "..."
        return snippet
    return ""


def get_plaintext_body(message: Message) -> Optional[str]:
    """Extract plain text body from a message."""
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == "text/plain":
                try:
                    return part.get_content()
                except Exception:
                    continue
    else:
        if message.get_content_type() == "text/plain":
            try:
                return message.get_content()
            except Exception:
                pass
    return None


def get_html_body(message: Message) -> Optional[str]:
    """Extract HTML body from a message."""
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == "text/html":
                try:
                    return part.get_content()
                except Exception:
                    continue
    else:
        if message.get_content_type() == "text/html":
            try:
                return message.get_content()
            except Exception:
                pass
    return None


def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse an email date string to datetime."""
    if not date_str:
        return None
    
    try:
        # Use email.utils.parsedate_to_datetime for RFC 2822 dates
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(date_str)
    except Exception:
        return None


def get_attachments(message: Message) -> List[AttachmentInfo]:
    """Extract attachment information from a message."""
    attachments = []
    
    if message.is_multipart():
        for part in message.walk():
            content_disposition = part.get("Content-Disposition", "")
            if "attachment" in content_disposition or "inline" in content_disposition:
                filename = part.get_filename()
                content_type = part.get_content_type()
                size = len(part.get_payload(decode=True) or b"")
                content_id = part.get("Content-ID")
                
                attachments.append(
                    AttachmentInfo(
                        filename=filename,
                        content_type=content_type,
                        size=size,
                        content_id=content_id,
                    )
                )
    
    return attachments


def get_attachment_content(message: Message, filename: Optional[str] = None, content_id: Optional[str] = None) -> Optional[Tuple[bytes, str]]:
    """Get attachment content by filename or content_id. Returns (content, content_type)."""
    if message.is_multipart():
        for part in message.walk():
            content_disposition = part.get("Content-Disposition", "")
            if "attachment" in content_disposition or "inline" in content_disposition:
                part_filename = part.get_filename()
                part_content_id = part.get("Content-ID")
                
                if filename and part_filename == filename:
                    try:
                        content = part.get_payload(decode=True)
                        return (content, part.get_content_type()) if content else None
                    except Exception:
                        continue
                
                if content_id and part_content_id == content_id:
                    try:
                        content = part.get_payload(decode=True)
                        return (content, part.get_content_type()) if content else None
                    except Exception:
                        continue
    
    return None


def format_addresses(addresses: Optional[str]) -> List[str]:
    """Parse and format email addresses from a header value."""
    if not addresses:
        return []
    
    try:
        from email.utils import getaddresses
        parsed = getaddresses([addresses])
        return [addr[1] for addr in parsed if addr[1]]  # Return email addresses only
    except Exception:
        return []


def get_reply_headers(message: Message) -> dict:
    """Extract headers needed for reply."""
    in_reply_to = message.get("Message-ID", "")
    references = message.get("References", "")
    if references:
        references = f"{references} {in_reply_to}"
    else:
        references = in_reply_to
    
    return {
        "in_reply_to": in_reply_to,
        "references": references,
        "subject": message.get("Subject", ""),
        "to": message.get("From", ""),
        "cc": message.get("CC", ""),
    }

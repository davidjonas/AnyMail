"""Type definitions for AnyMail."""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass
class Profile:
    """Email profile configuration."""
    name: str
    email: str
    imap_host: str
    imap_port: int
    imap_ssl: bool
    smtp_host: str
    smtp_port: int
    smtp_starttls: bool
    folder_inbox: str = "INBOX"
    folder_sent: str = "[Gmail]/Sent Mail"
    folder_trash: str = "[Gmail]/Trash"
    folder_allmail: str = "[Gmail]/All Mail"
    default_from_name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert profile to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "email": self.email,
            "imap_host": self.imap_host,
            "imap_port": self.imap_port,
            "imap_ssl": self.imap_ssl,
            "smtp_host": self.smtp_host,
            "smtp_port": self.smtp_port,
            "smtp_starttls": self.smtp_starttls,
            "folder_inbox": self.folder_inbox,
            "folder_sent": self.folder_sent,
            "folder_trash": self.folder_trash,
            "folder_allmail": self.folder_allmail,
            "default_from_name": self.default_from_name,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Profile":
        """Create profile from dictionary."""
        return cls(
            name=data["name"],
            email=data["email"],
            imap_host=data["imap_host"],
            imap_port=data["imap_port"],
            imap_ssl=data.get("imap_ssl", True),
            smtp_host=data["smtp_host"],
            smtp_port=data["smtp_port"],
            smtp_starttls=data.get("smtp_starttls", True),
            folder_inbox=data.get("folder_inbox", "INBOX"),
            folder_sent=data.get("folder_sent", "[Gmail]/Sent Mail"),
            folder_trash=data.get("folder_trash", "[Gmail]/Trash"),
            folder_allmail=data.get("folder_allmail", "[Gmail]/All Mail"),
            default_from_name=data.get("default_from_name"),
        )


@dataclass
class MessageSummary:
    """Summary of an email message."""
    uid: int
    message_id: Optional[str]
    from_addr: str
    to: List[str]
    subject: str
    date: datetime
    snippet: str
    flags: Dict[str, bool]  # seen, answered, flagged, etc.

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON output."""
        return {
            "id": self.uid,
            "message_id": self.message_id,
            "from": self.from_addr,
            "to": self.to,
            "subject": self.subject,
            "date": self.date.isoformat() if self.date is not None else None,
            "snippet": self.snippet,
            "flags": self.flags,
        }


@dataclass
class AttachmentInfo:
    """Information about an email attachment."""
    filename: Optional[str]
    content_type: str
    size: int
    content_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "filename": self.filename,
            "content_type": self.content_type,
            "size": self.size,
            "content_id": self.content_id,
        }

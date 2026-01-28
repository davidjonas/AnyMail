"""IMAP client wrapper."""

import imapclient
from imapclient import IMAPClient
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from .types import Profile, MessageSummary
from .parse import parse_message, extract_snippet, parse_date, format_addresses


class IMAPClientWrapper:
    """Wrapper around IMAPClient for easier use."""
    
    def __init__(self, profile: Profile, password: str):
        self.profile = profile
        self.password = password
        self.client: Optional[IMAPClient] = None
    
    def connect(self) -> None:
        """Connect to IMAP server."""
        self.client = IMAPClient(
            self.profile.imap_host,
            port=self.profile.imap_port,
            ssl=self.profile.imap_ssl,
        )
        self.client.login(self.profile.email, self.password)
    
    def disconnect(self) -> None:
        """Disconnect from IMAP server."""
        if self.client:
            try:
                self.client.logout()
            except Exception:
                pass
            self.client = None
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
    
    def select_folder(self, folder: str = None) -> Dict:
        """Select a folder. Returns folder info."""
        folder = folder or self.profile.folder_inbox
        return self.client.select_folder(folder)
    
    def search_messages(
        self,
        folder: Optional[str] = None,
        unread: Optional[bool] = None,
        since: Optional[datetime] = None,
        before: Optional[datetime] = None,
        from_addr: Optional[str] = None,
        subject: Optional[str] = None,
        raw_criteria: Optional[str] = None,
    ) -> List[int]:
        """Search for messages matching criteria."""
        self.select_folder(folder)
        
        criteria = []
        
        if raw_criteria:
            # Parse raw IMAP criteria (simplified - just pass through)
            # For now, we'll build criteria manually
            pass
        
        if unread is True:
            criteria.append("UNSEEN")
        elif unread is False:
            criteria.append("SEEN")
        
        if since:
            criteria.append(imapclient.SEARCH_SINCE(since))
        
        if before:
            criteria.append(imapclient.SEARCH_BEFORE(before))
        
        if from_addr:
            criteria.append(["FROM", from_addr])
        
        if subject:
            criteria.append(["SUBJECT", subject])
        
        if not criteria:
            criteria = ["ALL"]
        
        uids = self.client.search(criteria)
        return list(uids)
    
    def fetch_messages(
        self,
        uids: List[int],
        folder: Optional[str] = None,
    ) -> Dict[int, MessageSummary]:
        """Fetch message summaries."""
        self.select_folder(folder)
        
        # Fetch envelope data and flags
        messages_data = self.client.fetch(
            uids,
            ["ENVELOPE", "FLAGS", "RFC822"],
        )
        
        summaries = {}
        for uid, data in messages_data.items():
            envelope = data.get(b"ENVELOPE")
            flags = data.get(b"FLAGS", [])
            raw_message = data.get(b"RFC822")
            
            if not envelope:
                continue
            
            # Parse flags
            flags_dict = {
                "seen": b"\\Seen" in flags,
                "answered": b"\\Answered" in flags,
                "flagged": b"\\Flagged" in flags,
                "deleted": b"\\Deleted" in flags,
            }
            
            # Extract envelope data
            from_addr = ""
            if envelope.from_:
                from_addr = envelope.from_[0].mailbox.decode() + "@" + envelope.from_[0].host.decode()
            
            to_addrs = []
            if envelope.to:
                to_addrs = [
                    addr.mailbox.decode() + "@" + addr.host.decode()
                    for addr in envelope.to
                ]
            
            subject = envelope.subject.decode() if envelope.subject else ""
            parsed = parse_date(envelope.date) if envelope.date else None
            date = parsed if parsed is not None else datetime.now()
            
            # Extract snippet from raw message
            snippet = ""
            if raw_message:
                try:
                    message = parse_message(raw_message)
                    snippet = extract_snippet(message)
                except Exception:
                    pass
            
            message_id = None
            if raw_message:
                try:
                    message = parse_message(raw_message)
                    message_id = message.get("Message-ID")
                except Exception:
                    pass
            
            summaries[uid] = MessageSummary(
                uid=uid,
                message_id=message_id,
                from_addr=from_addr,
                to=to_addrs,
                subject=subject,
                date=date,
                snippet=snippet,
                flags=flags_dict,
            )
        
        return summaries
    
    def fetch_message(self, uid: int, folder: Optional[str] = None) -> bytes:
        """Fetch full message content."""
        self.select_folder(folder)
        messages = self.client.fetch([uid], ["RFC822"])
        if uid in messages:
            return messages[uid].get(b"RFC822", b"")
        raise ValueError(f"Message {uid} not found")
    
    def set_flags(self, uid: int, flags: List[str], folder: Optional[str] = None) -> None:
        """Set flags on a message."""
        self.select_folder(folder)
        self.client.set_flags([uid], flags)
    
    def remove_flags(self, uid: int, flags: List[str], folder: Optional[str] = None) -> None:
        """Remove flags from a message."""
        self.select_folder(folder)
        self.client.remove_flags([uid], flags)
    
    def move_message(self, uid: int, destination_folder: str, folder: Optional[str] = None) -> None:
        """Move a message to another folder."""
        self.select_folder(folder)
        self.client.move([uid], destination_folder)
    
    def copy_message(self, uid: int, destination_folder: str, folder: Optional[str] = None) -> None:
        """Copy a message to another folder."""
        self.select_folder(folder)
        self.client.copy([uid], destination_folder)
    
    def delete_message(self, uid: int, folder: Optional[str] = None) -> None:
        """Delete a message (move to trash for Gmail)."""
        self.move_message(uid, self.profile.folder_trash, folder)
    
    def archive_message(self, uid: int, folder: Optional[str] = None) -> None:
        """Archive a message (remove from INBOX for Gmail)."""
        # Gmail archive: remove INBOX label
        # For IMAP, we move from INBOX to All Mail, or just remove INBOX
        # Actually, Gmail's archive is removing the INBOX label
        # We'll move to All Mail as a safe approach
        if folder == "INBOX" or folder == self.profile.folder_inbox:
            self.move_message(uid, self.profile.folder_allmail, folder)
        else:
            # If not in INBOX, just move to All Mail
            self.move_message(uid, self.profile.folder_allmail, folder)
    
    def list_folders(self) -> List[str]:
        """List all folders."""
        folders = self.client.list_folders()
        return [folder[2] for folder in folders]

"""Keychain/secret management using keyring."""

import keyring
from typing import Optional


def get_password(profile: str) -> Optional[str]:
    """Get app password for a profile."""
    try:
        password = keyring.get_password("anymail", profile)
        return password
    except Exception:
        return None


def set_password(profile: str, password: str) -> None:
    """Store app password for a profile."""
    keyring.set_password("anymail", profile, password)


def clear_password(profile: str) -> bool:
    """Clear app password for a profile. Returns True if cleared."""
    try:
        keyring.delete_password("anymail", profile)
        return True
    except keyring.errors.PasswordDeleteError:
        return False


def has_password(profile: str) -> bool:
    """Check if a password exists for a profile."""
    return get_password(profile) is not None

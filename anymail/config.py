"""Configuration management for AnyMail."""

import json
import os
from pathlib import Path
from typing import Dict, Optional
from .types import Profile


def get_config_dir() -> Path:
    """Get the configuration directory path."""
    # Windows: %USERPROFILE%\.anymail
    if os.name == "nt":
        userprofile = os.environ.get("USERPROFILE")
        if userprofile:
            return Path(userprofile) / ".anymail"
    # Cross-platform fallback: ~/.anymail
    return Path.home() / ".anymail"


def get_config_path() -> Path:
    """Get the path to the config file."""
    config_dir = get_config_dir()
    return config_dir / "config.json"


def ensure_config_dir() -> None:
    """Ensure the configuration directory exists."""
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)


def load_config() -> Dict[str, Profile]:
    """Load profiles from config file."""
    config_path = get_config_path()
    if not config_path.exists():
        return {}
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        profiles = {}
        for name, profile_data in data.get("profiles", {}).items():
            profiles[name] = Profile.from_dict(profile_data)
        
        return profiles
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        raise ValueError(f"Invalid config file: {e}")


def save_config(profiles: Dict[str, Profile]) -> None:
    """Save profiles to config file."""
    ensure_config_dir()
    config_path = get_config_path()
    
    data = {
        "profiles": {name: profile.to_dict() for name, profile in profiles.items()}
    }
    
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_profile(name: Optional[str] = None) -> Optional[Profile]:
    """Get a profile by name, or the only profile if name is None."""
    profiles = load_config()
    
    if name:
        return profiles.get(name)
    
    if len(profiles) == 1:
        return list(profiles.values())[0]
    
    if len(profiles) == 0:
        return None
    
    # Multiple profiles but no name specified
    raise ValueError(
        f"Multiple profiles found: {', '.join(profiles.keys())}. "
        "Please specify --profile"
    )


def add_profile(profile: Profile) -> None:
    """Add or update a profile."""
    profiles = load_config()
    profiles[profile.name] = profile
    save_config(profiles)


def remove_profile(name: str) -> bool:
    """Remove a profile. Returns True if removed, False if not found."""
    profiles = load_config()
    if name in profiles:
        del profiles[name]
        save_config(profiles)
        return True
    return False

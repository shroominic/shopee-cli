"""Configuration and credential storage for shopee-cli."""

import json
import os
import stat
import time
from pathlib import Path


def get_config_dir() -> Path:
    """Get XDG-compliant config directory."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        base = Path(xdg)
    else:
        base = Path.home() / ".config"
    config_dir = base / "shopee-cli"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_cookies_path() -> Path:
    return get_config_dir() / "cookies.json"


def get_profile_dir() -> Path:
    """Get persistent Chrome profile directory."""
    profile = get_config_dir() / "chrome-profile"
    profile.mkdir(parents=True, exist_ok=True)
    return profile


def save_cookies(cookies: list[dict]) -> Path:
    """Save cookies to config dir with restricted permissions."""
    path = get_cookies_path()
    data = {
        "cookies": cookies,
        "saved_at": time.time(),
    }
    path.write_text(json.dumps(data, indent=2))
    # Restrict to owner read/write only
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return path


def load_cookies() -> list[dict] | None:
    """Load saved cookies. Returns None if no cookies or expired."""
    path = get_cookies_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, KeyError):
        return None
    saved_at = data.get("saved_at", 0)
    # Consider cookies stale after 24 hours
    if time.time() - saved_at > 86400:
        return None
    return data.get("cookies")


def clear_cookies() -> None:
    """Remove saved cookies."""
    path = get_cookies_path()
    if path.exists():
        path.unlink()

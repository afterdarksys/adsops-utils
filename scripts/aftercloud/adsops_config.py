#!/usr/bin/env python3
"""
AfterCloud Centralized Configuration Module

Manages all API keys, tokens, and credentials in a single secure location.
Config stored at: ~/.adsops_config/config.json

Usage:
    from adsops_config import Config

    config = Config()
    api_key = config.get("cloudflare", "api_token")
    config.set("cloudflare", "api_token", "my-token")

CLI Usage:
    adsops_config.py init                    # Create config file
    adsops_config.py show                    # Show config (masked)
    adsops_config.py set cloudflare.api_token <value>
    adsops_config.py get cloudflare.api_token
    adsops_config.py delete neon.api_key
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


# Centralized config location - NOT in repo
CONFIG_DIR = Path.home() / ".adsops_config"
CONFIG_FILE = CONFIG_DIR / "config.json"


def speak(message: str):
    """Print message with timestamp."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")
    sys.stdout.flush()


def speak_plain(message: str):
    """Print without timestamp."""
    print(message)
    sys.stdout.flush()


class Config:
    """Centralized configuration manager for AfterCloud tools."""

    # Default config structure
    DEFAULT_CONFIG = {
        "_comment": "AfterCloud Tools Configuration - DO NOT COMMIT TO GIT",
        "_location": "~/.adsops_config/config.json",
        "oci": {
            "profile": "DEFAULT",
            "compartment_id": "",
            "tenancy_id": ""
        },
        "cloudflare": {
            "api_token": "",
            "account_id": ""
        },
        "neon": {
            "api_key": ""
        },
        "vastai": {
            "api_key": ""
        },
        "runpod": {
            "api_key": ""
        },
        "ticketing": {
            "api_url": "https://changes.afterdarksys.com",
            "api_token": "",
            "org_id": ""
        },
        "ssh": {
            "default_key": "~/.ssh/id_rsa",
            "default_user": "opc"
        }
    }

    # Fields that should be masked when displayed
    SENSITIVE_FIELDS = [
        "api_token", "api_key", "password", "secret",
        "private_key", "auth_token", "credential"
    ]

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize config manager."""
        self.config_path = config_path or CONFIG_FILE
        self.config_dir = self.config_path.parent
        self._config = None

    def _ensure_dir(self):
        """Ensure config directory exists with secure permissions."""
        if not self.config_dir.exists():
            self.config_dir.mkdir(parents=True, mode=0o700)
        else:
            # Ensure restrictive permissions
            self.config_dir.chmod(0o700)

    def _load(self) -> dict:
        """Load configuration from file."""
        if self._config is not None:
            return self._config

        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    self._config = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                speak(f"Warning: Could not load config: {e}")
                self._config = self.DEFAULT_CONFIG.copy()
        else:
            self._config = self.DEFAULT_CONFIG.copy()

        return self._config

    def _save(self):
        """Save configuration to file with secure permissions."""
        self._ensure_dir()

        with open(self.config_path, "w") as f:
            json.dump(self._config, f, indent=2)

        # Secure the config file
        self.config_path.chmod(0o600)

    def get(self, section: str, key: str, default: Any = None) -> Any:
        """
        Get a config value.

        Also checks environment variables in format:
        ADSOPS_<SECTION>_<KEY> (e.g., ADSOPS_CLOUDFLARE_API_TOKEN)
        """
        # Check environment variable first
        env_key = f"ADSOPS_{section.upper()}_{key.upper()}"
        env_value = os.environ.get(env_key)
        if env_value:
            return env_value

        # Fall back to config file
        config = self._load()
        section_data = config.get(section, {})

        if isinstance(section_data, dict):
            return section_data.get(key, default)
        return default

    def set(self, section: str, key: str, value: Any):
        """Set a config value."""
        config = self._load()

        if section not in config:
            config[section] = {}

        config[section][key] = value
        self._config = config
        self._save()

    def delete(self, section: str, key: Optional[str] = None):
        """Delete a config key or entire section."""
        config = self._load()

        if key is None:
            # Delete entire section
            if section in config:
                del config[section]
        else:
            # Delete specific key
            if section in config and key in config[section]:
                del config[section][key]

        self._config = config
        self._save()

    def get_section(self, section: str) -> dict:
        """Get an entire config section."""
        config = self._load()
        return config.get(section, {})

    def init(self):
        """Initialize config file with defaults."""
        self._ensure_dir()

        if self.config_path.exists():
            return False  # Already exists

        self._config = self.DEFAULT_CONFIG.copy()
        self._save()
        return True

    def exists(self) -> bool:
        """Check if config file exists."""
        return self.config_path.exists()

    def mask_value(self, key: str, value: Any) -> str:
        """Mask sensitive values for display."""
        if value is None or value == "":
            return "(not set)"

        # Check if this is a sensitive field
        is_sensitive = any(s in key.lower() for s in self.SENSITIVE_FIELDS)

        if is_sensitive and isinstance(value, str) and len(value) > 8:
            return f"{value[:4]}...{value[-4:]}"
        elif is_sensitive and isinstance(value, str):
            return "****"

        return str(value)

    def show(self, show_secrets: bool = False) -> dict:
        """Get config for display (with masked secrets)."""
        config = self._load()

        if show_secrets:
            return config

        def mask_dict(d: dict, parent_key: str = "") -> dict:
            result = {}
            for k, v in d.items():
                full_key = f"{parent_key}.{k}" if parent_key else k
                if isinstance(v, dict):
                    result[k] = mask_dict(v, full_key)
                else:
                    result[k] = self.mask_value(k, v)
            return result

        return mask_dict(config)


# Convenience functions for use by other modules
_default_config = None


def get_config() -> Config:
    """Get the default config instance."""
    global _default_config
    if _default_config is None:
        _default_config = Config()
    return _default_config


def get(section: str, key: str, default: Any = None) -> Any:
    """Convenience function to get a config value."""
    return get_config().get(section, key, default)


def set_value(section: str, key: str, value: Any):
    """Convenience function to set a config value."""
    get_config().set(section, key, value)


# CLI functionality
def cmd_init(args):
    """Initialize config file."""
    config = Config()

    if config.exists() and not args.force:
        speak_plain(f"Config already exists at: {config.config_path}")
        speak_plain("Use --force to overwrite.")
        return

    config.init()
    speak(f"Created config file at: {config.config_path}")
    speak_plain("")
    speak_plain("Edit this file to add your API keys and credentials.")
    speak_plain("Or use: adsops_config.py set <section>.<key> <value>")
    speak_plain("")
    speak_plain("Environment variables also work:")
    speak_plain("  ADSOPS_CLOUDFLARE_API_TOKEN")
    speak_plain("  ADSOPS_NEON_API_KEY")
    speak_plain("  ADSOPS_TICKETING_API_TOKEN")


def cmd_show(args):
    """Show current config."""
    config = Config()

    if not config.exists():
        speak_plain("No config file found.")
        speak_plain(f"Run 'adsops_config.py init' to create one at {CONFIG_FILE}")
        return

    speak_plain("")
    speak_plain(f"Config file: {config.config_path}")
    speak_plain("=" * 60)
    speak_plain("")

    data = config.show(show_secrets=args.show_secrets)

    for section, values in data.items():
        if section.startswith("_"):
            continue
        speak_plain(f"[{section}]")
        if isinstance(values, dict):
            for k, v in values.items():
                speak_plain(f"  {k}: {v}")
        else:
            speak_plain(f"  {values}")
        speak_plain("")

    if not args.show_secrets:
        speak_plain("(Secrets masked. Use --show-secrets to reveal)")


def cmd_get(args):
    """Get a config value."""
    config = Config()

    parts = args.key.split(".", 1)
    if len(parts) != 2:
        print("Error: Key format should be section.key (e.g., cloudflare.api_token)")
        sys.exit(1)

    section, key = parts
    value = config.get(section, key)

    if value is None or value == "":
        speak_plain("(not set)")
    elif args.raw:
        print(value)
    else:
        speak_plain(config.mask_value(key, value))


def cmd_set(args):
    """Set a config value."""
    config = Config()

    parts = args.key.split(".", 1)
    if len(parts) != 2:
        print("Error: Key format should be section.key (e.g., cloudflare.api_token)")
        sys.exit(1)

    section, key = parts
    config.set(section, key, args.value)
    speak(f"Set {section}.{key}")


def cmd_delete(args):
    """Delete a config key."""
    config = Config()

    parts = args.key.split(".", 1)
    section = parts[0]
    key = parts[1] if len(parts) > 1 else None

    if key:
        config.delete(section, key)
        speak(f"Deleted {section}.{key}")
    else:
        config.delete(section)
        speak(f"Deleted section [{section}]")


def cmd_path(args):
    """Show config path."""
    speak_plain(str(CONFIG_FILE))


def main():
    parser = argparse.ArgumentParser(
        description="AfterCloud Configuration Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    adsops_config.py init                         # Create config file
    adsops_config.py show                         # Show config (masked)
    adsops_config.py show --show-secrets          # Show with secrets
    adsops_config.py set cloudflare.api_token XXX # Set value
    adsops_config.py get cloudflare.api_token     # Get value
    adsops_config.py get cloudflare.api_token --raw  # Get raw value
    adsops_config.py delete neon.api_key          # Delete key
    adsops_config.py path                         # Show config path

Config Location:
    ~/.adsops_config/config.json

Environment Variables:
    ADSOPS_<SECTION>_<KEY> overrides config file values
    Example: ADSOPS_CLOUDFLARE_API_TOKEN
"""
    )

    subparsers = parser.add_subparsers(dest="command")

    # init
    init_parser = subparsers.add_parser("init", help="Create config file")
    init_parser.add_argument("--force", "-f", action="store_true", help="Overwrite existing")
    init_parser.set_defaults(func=cmd_init)

    # show
    show_parser = subparsers.add_parser("show", help="Show config")
    show_parser.add_argument("--show-secrets", "-s", action="store_true", help="Show secret values")
    show_parser.set_defaults(func=cmd_show)

    # get
    get_parser = subparsers.add_parser("get", help="Get config value")
    get_parser.add_argument("key", help="Key in format section.key")
    get_parser.add_argument("--raw", "-r", action="store_true", help="Output raw value only")
    get_parser.set_defaults(func=cmd_get)

    # set
    set_parser = subparsers.add_parser("set", help="Set config value")
    set_parser.add_argument("key", help="Key in format section.key")
    set_parser.add_argument("value", help="Value to set")
    set_parser.set_defaults(func=cmd_set)

    # delete
    del_parser = subparsers.add_parser("delete", help="Delete config key")
    del_parser.add_argument("key", help="Key in format section.key or just section")
    del_parser.set_defaults(func=cmd_delete)

    # path
    path_parser = subparsers.add_parser("path", help="Show config file path")
    path_parser.set_defaults(func=cmd_path)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()

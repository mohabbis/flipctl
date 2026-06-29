#!/usr/bin/env python3
"""
Setup script for FlipCTL configuration.
Helps users initialize configuration for API keys, rate limits, etc.
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import ConfigManager


def setup_interactive():
    """Interactive setup of FlipCTL configuration."""
    print("=== FlipCTL Configuration Setup ===")
    print()

    config = ConfigManager()

    # API Key setup
    print("1. API Authentication Setup")
    enable_auth = input("Enable API key authentication? [y/N]: ").lower().strip()
    if enable_auth in ('y', 'yes'):
        config.set("api.enabled", True)
        api_key = input("Enter API key (or leave empty to generate one): ").strip()
        if not api_key:
            import secrets
            api_key = secrets.token_urlsafe(32)
            print(f"Generated API key: {api_key}")
            print("Save this key - you'll need it to access the API!")
        config.set("api.key", api_key)
    else:
        config.set("api.enabled", False)

    # Rate limiting setup
    print("\n2. Rate Limiting Setup")
    enable_rl = input("Enable rate limiting? [Y/n]: ").lower().strip()
    if enable_rl not in ('n', 'no'):
        try:
            requests = int(input("Requests per window [10]: ") or "10")
            window = int(input("Window size in seconds [60]: ") or "60")
            config.set("api.rate_limit_requests", max(1, requests))
            config.set("api.rate_limit_window", max(1, window))
            print(f"Rate limit set to {requests} requests per {window} seconds")
        except ValueError:
            print("Invalid input, using defaults (10 req/60s)")
            config.set("api.rate_limit_requests", 10)
            config.set("api.rate_limit_window", 60)
    else:
        config.set("api.rate_limit_requests", 0)  # Disable rate limiting
        config.set("api.rate_limit_window", 60)

    # Logging setup
    print("\n3. Logging Setup")
    log_level = input("Log level (DEBUG/INFO/WARNING/ERROR) [INFO]: ").upper().strip()
    if log_level not in ("DEBUG", "INFO", "WARNING", "ERROR"):
        log_level = "INFO"
    config.set("logging.level", log_level)

    log_to_file = input("Log to file? [Y/n]: ").lower().strip()
    if log_to_file not in ('n', 'no'):
        log_file = input(f"Log file path [{config.get('logging.file')}] ").strip()
        if not log_file:
            log_file = config.get("logging.file")
        config.set("logging.file", log_file)

    # Save configuration
    config._save()
    print("\n✓ Configuration saved successfully!")
    print(f"Config file: {config.config_file}")

    # Show summary
    print("\n=== Configuration Summary ===")
    print(f"API Authentication: {'Enabled' if config.get('api.enabled') else 'Disabled'}")
    if config.get('api.enabled'):
        key_preview = config.get('api.key', '')[:8] + "..." if config.get('api.key') else "Not set"
        print(f"API Key: {key_preview}")
    print(f"Rate Limiting: {config.get('api.rate_limit_requests', 0)} req/{config.get('api.rate_limit_window', 60)}s")
    print(f"Log Level: {config.get('logging.level', 'INFO')}")
    print(f"Log File: {config.get('logging.file', 'console only')}")


def show_current():
    """Show current configuration."""
    config = ConfigManager()
    print("=== Current FlipCTL Configuration ===")
    print(f"Config file: {config.config_file}")
    print(f"File exists: {config.config_file.exists()}")
    print()

    print("API Settings:")
    print(f"  Enabled: {config.get('api.enabled', False)}")
    if config.get('api.enabled'):
        key = config.get('api.key', '')
        if key:
            print(f"  Key: {key[:8]}...{key[-4:] if len(key) > 12 else ''} (length: {len(key)})")
        else:
            print("  Key: Not set")
    print(f"  Rate limit: {config.get('api.rate_limit_requests', 0)} req/{config.get('api.rate_limit_window', 60)}s")
    print()

    print("Logging Settings:")
    print(f"  Level: {config.get('logging.level', 'INFO')}")
    print(f"  File: {config.get('logging.file', 'None (console only)')}")
    print()

    print("Plugin Settings:")
    print(f"  Default timeout: {config.get('plugin.timeout_default', 30)}s")
    print(f"  Max concurrent: {config.get('plugin.max_concurrent', 5)}")
    print()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "show":
        show_current()
    else:
        setup_interactive()
"""
Configuration management for FlipCTL.
Handles loading, saving, and accessing configuration settings.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


class Config:
    """Configuration manager for FlipCTL."""

    def __init__(self, config_dir: Optional[str] = None):
        """
        Initialize configuration manager.

        Args:
            config_dir: Directory to store config files (defaults to ~/.flipctl)
        """
        if config_dir is None:
            # Use ~/.flipctl on Unix/Linux/macOS, or appropriate local dir on Windows
            home = os.path.expanduser("~")
            if os.name == 'nt':  # Windows
                config_dir = os.path.join(os.getenv('APPDATA', home), 'FlipCTL')
            else:
                config_dir = os.path.join(home, '.flipctl')

        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self.config_file = self.config_dir / "config.json"
        self._config: Dict[str, Any] = self._load_defaults()
        self.load()

    def _load_defaults(self) -> Dict[str, Any]:
        """Load default configuration values."""
        return {
            # API settings
            "api_key": "",
            "enable_auth": False,
            "enable_rate_limit": True,
            "rate_limit_requests": 10,
            "rate_limit_window": 60,

            # Logging settings
            "log_level": "INFO",
            "log_file": "",
            "log_max_size_mb": 10,
            "log_backup_count": 5,

            # Plugin settings
            "plugin_timeout": 30,
            "plugin_sandbox": False,

            # Server settings
            "host": "0.0.0.0",
            "port": 8000,

            # Security settings
            "allowed_origins": [],  # For CORS
            "trusted_proxies": [],  # For IP forwarding
        }

    def load(self) -> bool:
        """
        Load configuration from file.

        Returns:
            True if config was loaded, False if file didn't exist
        """
        if not self.config_file.exists():
            return False

        try:
            with open(self.config_file, 'r') as f:
                loaded_config = json.load(f)
                # Update only existing keys to preserve defaults for new settings
                for key, value in loaded_config.items():
                    if key in self._config:
                        self._config[key] = value
            return True
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load config file: {e}")
            return False

    def save(self) -> bool:
        """
        Save configuration to file.

        Returns:
            True if successful, False otherwise
        """
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self._config, f, indent=2, sort_keys=True)
            return True
        except IOError as e:
            print(f"Error: Could not save config file: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value
        """
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value.

        Args:
            key: Configuration key
            value: Value to set
        """
        self._config[key] = value

    def update(self, updates: Dict[str, Any]) -> None:
        """
        Update multiple configuration values.

        Args:
            updates: Dictionary of key-value pairs to update
        """
        self._config.update(updates)

    def delete(self, key: str) -> bool:
        """
        Delete a configuration key.

        Args:
            key: Key to delete

        Returns:
            True if key existed and was deleted, False otherwise
        """
        if key in self._config:
            del self._config[key]
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Get a copy of the entire configuration."""
        return self._config.copy()

    def reset_to_defaults(self) -> None:
        """Reset configuration to default values."""
        self._config = self._load_defaults()


# Global config instance
config = Config()
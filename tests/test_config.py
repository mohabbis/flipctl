"""Tests for configuration management system."""

import json
import os
import tempfile
from pathlib import Path

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.config import ConfigManager


def test_config_creation():
    """Test that config manager creates default values."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ConfigManager(tmpdir)

        # Check that defaults are set
        assert config.get("api.enabled") == False
        assert config.get("api.key") == ""
        assert config.get("api.rate_limit_requests") == 10
        assert config.get("api.rate_limit_window") == 60
        assert config.get("logging.level") == "INFO"


def test_config_get_set():
    """Test getting and setting configuration values."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ConfigManager(tmpdir)

        # Test setting and getting
        config.set("test.value", 42)
        assert config.get("test.value") == 42

        config.set("api.key", "test-key-123")
        assert config.get("api.key") == "test-key-123"

        # Test default value
        assert config.get("nonexistent.key", "default") == "default"


def test_config_update():
    """Test updating multiple configuration values."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ConfigManager(tmpdir)

        updates = {
            "api.enabled": True,
            "api.key": "new-key",
            "logging.level": "DEBUG"
        }
        config.update(updates)

        assert config.get("api.enabled") == True
        assert config.get("api.key") == "new-key"
        assert config.get("logging.level") == "DEBUG"


def test_config_save_load():
    """Test saving and loading configuration."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "test_config.json"

        # Create config and set values
        config1 = ConfigManager(tmpdir)
        config1.set("api.enabled", True)
        config1.set("api.key", "test-key-456")
        config1.set("logging.level", "DEBUG")
        config1._save()  # Force save

        # Create new config instance and load
        config2 = ConfigManager(tmpdir)
        assert config2.get("api.enabled") == True
        assert config2.get("api.key") == "test-key-456"
        assert config2.get("logging.level") == "DEBUG"


def test_config_reset():
    """Test resetting configuration to defaults."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ConfigManager(tmpdir)

        # Modify some values
        config.set("api.enabled", True)
        config.set("api.key", "modified-key")
        config.set("logging.level", "WARNING")

        # Verify changes
        assert config.get("api.enabled") == True
        assert config.get("api.key") == "modified-key"
        assert config.get("logging.level") == "WARNING"

        # Reset to defaults
        config.reset_to_defaults()

        # Check that values are back to defaults
        assert config.get("api.enabled") == False
        assert config.get("api.key") == ""
        assert config.get("logging.level") == "INFO"


def test_env_var_override():
    """Test that environment variables can override config (conceptual test)."""
    # This would be implemented in the actual application layer
    # For now, we just test that the config system works
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ConfigManager(tmpdir)

        # Set a value
        config.set("test.env_test", "original")
        assert config.get("test.env_test") == "original"

        # In real implementation, we'd check os.environ here
        # But for unit test, we just verify the storage works
        assert config.get("test.env_test") == "original"


if __name__ == "__main__":
    # Run tests
    test_config_creation()
    print("✓ test_config_creation passed")

    test_config_get_set()
    print("✓ test_config_get_set passed")

    test_config_update()
    print("✓ test_config_update passed")

    test_config_save_load()
    print("✓ test_config_save_load passed")

    test_config_reset()
    print("✓ test_config_reset passed")

    test_env_var_override()
    print("✓ test_env_var_override passed")

    print("\nAll tests passed! 🎉")
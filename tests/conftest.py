"""Pytest configuration and fixtures for flipctl tests."""

import pytest
import tempfile
import os
from unittest.mock import Mock, patch

# Add the project root to the Python path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir

@pytest.fixture
def mock_plugin_manager():
    """Mock plugin manager for testing."""
    with patch('core.plugin_manager.PluginManager') as mock:
        yield mock

@pytest.fixture
def test_client():
    """Create a test client for the FastAPI app."""
    from fastapi.testclient import TestClient
    from server import app
    return TestClient(app)
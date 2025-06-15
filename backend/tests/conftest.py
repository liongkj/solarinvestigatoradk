"""Test configuration and fixtures"""

import pytest
from fastapi.testclient import TestClient
import sys
import os

# Add src to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture
def test_client():
    """Create a test client for the FastAPI app"""
    from main import app

    return TestClient(app)


@pytest.fixture
def sample_project_data():
    """Sample project data for testing"""
    return {
        "id": "test-project-1",
        "name": "Test Solar Installation",
        "address": "123 Test Street, Test City, TC 12345",
        "customer": "Test Customer",
        "status": "planning",
        "type": "residential",
    }
